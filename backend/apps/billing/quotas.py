from __future__ import annotations

from dataclasses import dataclass
from datetime import timezone as dt_timezone

from django.conf import settings
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.exceptions import ValidationError

from apps.authentication.models import User
from apps.candidates.models import CandidateEnrollment
from apps.campaigns.models import VettingCampaign
from apps.core.authz import get_user_default_organization, get_user_organization_ids
from apps.governance.models import Organization, OrganizationMembership

from .models import BillingSubscription


@dataclass(frozen=True)
class CandidateQuotaSnapshot:
    enforced: bool
    scope: str
    reason: str | None
    plan_id: str | None
    plan_name: str | None
    limit: int | None
    used: int
    remaining: int | None
    period_start: timezone.datetime
    period_end: timezone.datetime


@dataclass(frozen=True)
class OrganizationSeatQuotaSnapshot:
    enforced: bool
    organization_id: str
    reason: str | None
    plan_id: str | None
    plan_name: str | None
    limit: int | None
    used: int
    remaining: int | None


@dataclass(frozen=True)
class VettingOperationQuotaSnapshot:
    enforced: bool
    operation: str
    scope: str
    reason: str | None
    plan_id: str | None
    plan_name: str | None
    limit: int | None
    used: int
    remaining: int | None
    period_start: timezone.datetime
    period_end: timezone.datetime


VETTING_OPERATION_DOCUMENT_VERIFICATION = "document_verification"
VETTING_OPERATION_SOCIAL_PROFILE_CHECK = "social_profile_check"
VETTING_OPERATION_INTERVIEW_ANALYSIS = "interview_analysis"
VETTING_OPERATION_RUBRIC_EVALUATION = "rubric_evaluation"
VETTING_OPERATION_BACKGROUND_CHECK_SUBMISSION = "background_check_submission"

VETTING_OPERATION_KEYS = {
    VETTING_OPERATION_DOCUMENT_VERIFICATION,
    VETTING_OPERATION_SOCIAL_PROFILE_CHECK,
    VETTING_OPERATION_INTERVIEW_ANALYSIS,
    VETTING_OPERATION_RUBRIC_EVALUATION,
    VETTING_OPERATION_BACKGROUND_CHECK_SUBMISSION,
}


def _month_window(now: timezone.datetime | None = None) -> tuple[timezone.datetime, timezone.datetime]:
    anchor = now or timezone.now()
    period_start = anchor.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if period_start.month == 12:
        period_end = period_start.replace(year=period_start.year + 1, month=1)
    else:
        period_end = period_start.replace(month=period_start.month + 1)
    return period_start, period_end


def _normalized_email(value: str | None) -> str:
    return str(value or "").strip().lower()


def _is_platform_admin_like(user) -> bool:
    return bool(
        getattr(user, "is_staff", False)
        or getattr(user, "is_superuser", False)
        or getattr(user, "user_type", None) == "admin"
    )


def _organization_name_for_id(organization_id: str | None) -> str:
    normalized_org_id = str(organization_id or "").strip()
    if not normalized_org_id:
        return ""
    organization = Organization.objects.filter(id=normalized_org_id).only("name").first()
    return str(getattr(organization, "name", "") or "").strip().lower()


def _active_org_member_emails(*, organization_id: str) -> set[str]:
    normalized_org_id = str(organization_id or "").strip()
    if not normalized_org_id:
        return set()
    return {
        _normalized_email(email)
        for email in User.objects.filter(
            organization_memberships__organization_id=normalized_org_id,
            organization_memberships__is_active=True,
            organization_memberships__organization__is_active=True,
        ).values_list("email", flat=True)
        if _normalized_email(email)
    }


def _active_membership_org_ids_for_user(user, *, cache: dict[str, set[str]]) -> set[str]:
    if user is None or getattr(user, "id", None) is None:
        return set()
    cache_key = str(user.id)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    org_ids = {
        str(value)
        for value in OrganizationMembership.objects.filter(user=user, is_active=True).values_list("organization_id", flat=True)
        if value
    }
    cache[cache_key] = org_ids
    return org_ids


def _user_is_unambiguously_scoped_to_org(
    *,
    user,
    organization_id: str,
    organization_name: str,
    membership_cache: dict[str, set[str]],
) -> bool:
    if user is None:
        return False
    user_memberships = _active_membership_org_ids_for_user(user, cache=membership_cache)
    if user_memberships:
        return user_memberships == {organization_id}
    legacy_organization_name = str(getattr(user, "organization", "") or "").strip().lower()
    return bool(legacy_organization_name and organization_name and legacy_organization_name == organization_name)


def _legacy_subscription_ids_for_organization(*, organization_id: str, emails: list[str]) -> list[str]:
    normalized_org_id = str(organization_id or "").strip()
    normalized_emails = sorted({_normalized_email(email) for email in emails if _normalized_email(email)})
    if not normalized_org_id or not normalized_emails:
        return []

    organization_name = _organization_name_for_id(normalized_org_id)
    membership_cache: dict[str, set[str]] = {}
    user_cache: dict[str, User | None] = {}

    safe_subscription_ids: list[str] = []
    candidates = (
        BillingSubscription.objects.filter(
            organization_id__isnull=True,
            registration_consumed_by_email__in=normalized_emails,
        )
        .order_by("-updated_at", "-created_at")
    )
    for subscription in candidates.iterator(chunk_size=100):
        metadata = subscription.metadata if isinstance(subscription.metadata, dict) else {}
        metadata_org_id = str(metadata.get("organization_id", "") or "").strip()
        if metadata_org_id:
            if metadata_org_id == normalized_org_id:
                safe_subscription_ids.append(str(subscription.id))
            continue

        registration_email = _normalized_email(getattr(subscription, "registration_consumed_by_email", ""))
        if not registration_email:
            continue

        if registration_email not in user_cache:
            user_cache[registration_email] = User.objects.filter(email__iexact=registration_email).only("id", "organization").first()
        registration_user = user_cache[registration_email]
        if _user_is_unambiguously_scoped_to_org(
            user=registration_user,
            organization_id=normalized_org_id,
            organization_name=organization_name,
            membership_cache=membership_cache,
        ):
            safe_subscription_ids.append(str(subscription.id))

    return safe_subscription_ids


def _legacy_candidate_usage_count_for_organization(
    *,
    organization_id: str,
    period_start,
    period_end,
) -> int:
    normalized_org_id = str(organization_id or "").strip()
    if not normalized_org_id:
        return 0

    organization_name = _organization_name_for_id(normalized_org_id)
    membership_cache: dict[str, set[str]] = {}
    eligibility_cache: dict[str, bool] = {}
    count = 0

    enrollments = CandidateEnrollment.objects.filter(
        campaign__organization_id__isnull=True,
        created_at__gte=period_start,
        created_at__lt=period_end,
    ).select_related("campaign__initiated_by")

    for enrollment in enrollments.iterator(chunk_size=500):
        campaign_owner = getattr(getattr(enrollment, "campaign", None), "initiated_by", None)
        owner_id = str(getattr(campaign_owner, "id", "") or "")
        if not owner_id:
            continue
        if owner_id not in eligibility_cache:
            eligibility_cache[owner_id] = _user_is_unambiguously_scoped_to_org(
                user=campaign_owner,
                organization_id=normalized_org_id,
                organization_name=organization_name,
                membership_cache=membership_cache,
            )
        if eligibility_cache[owner_id]:
            count += 1

    return count


def _scope_for_user(user, *, organization_id: str | None = None) -> tuple[str, list[str], str, str | None]:
    requested_org_id = str(organization_id or "").strip()
    allowed_org_ids = set(get_user_organization_ids(user))
    default_organization = get_user_default_organization(user)
    default_org_id = str(default_organization.get("id", "")).strip() if isinstance(default_organization, dict) else ""
    selected_org_id = None
    if requested_org_id and (requested_org_id in allowed_org_ids or _is_platform_admin_like(user)):
        selected_org_id = requested_org_id
    elif requested_org_id and default_org_id:
        selected_org_id = default_org_id
    elif default_org_id:
        selected_org_id = default_org_id

    if selected_org_id:
        org_member_emails = _active_org_member_emails(organization_id=selected_org_id)
        return f"organization:{selected_org_id}", sorted(org_member_emails), "", selected_org_id

    fallback_emails: set[str] = set()
    current_email = _normalized_email(getattr(user, "email", ""))
    if current_email:
        fallback_emails.add(current_email)

    legacy_organization_name = str(getattr(user, "organization", "") or "").strip()
    if legacy_organization_name:
        matched_org = Organization.objects.filter(name__iexact=legacy_organization_name).only("id").first()
        matched_org_id = str(getattr(matched_org, "id", "") or "").strip() or None
        if matched_org_id:
            org_member_emails = _active_org_member_emails(organization_id=matched_org_id)
            fallback_emails.update(org_member_emails)
        org_users = User.objects.filter(organization__iexact=legacy_organization_name).only("email")
        fallback_emails.update(
            _normalized_email(member.email)
            for member in org_users
            if getattr(member, "email", "")
        )
        if not fallback_emails and current_email:
            fallback_emails.add(current_email)
        scope_label = f"organization:{matched_org_id}" if matched_org_id else f"organization:{legacy_organization_name.lower()}"
        return (
            scope_label,
            sorted(value for value in fallback_emails if value),
            legacy_organization_name,
            matched_org_id,
        )

    fallback_scope = current_email or f"user:{getattr(user, 'pk', 'unknown')}"
    return f"user:{fallback_scope}", sorted(value for value in fallback_emails if value), "", None


def _is_subscription_effectively_active(subscription: BillingSubscription | None) -> bool:
    if subscription is None:
        return False
    if subscription.status in {"canceled", "failed", "expired"}:
        return False
    if subscription.payment_status in {"unpaid"} and subscription.status != "complete":
        return False
    return True


def _active_subscription_for_queryset(queryset) -> BillingSubscription | None:
    latest_any = queryset.order_by("-updated_at", "-created_at").first()
    if latest_any is not None:
        latest_any = _normalize_subscription_runtime_state(latest_any)
        if not _is_subscription_effectively_active(latest_any):
            return None

    candidates = queryset.filter(
        status="complete",
        payment_status__in={"paid", "no_payment_required"},
    ).order_by("-updated_at", "-created_at")
    now = timezone.now()
    for subscription in candidates:
        normalized = _normalize_subscription_runtime_state(subscription, now=now)
        if normalized.status == "complete" and normalized.payment_status in {"paid", "no_payment_required"}:
            return normalized
    return None


def _active_subscription_for_scope(*, emails: list[str], organization_id: str | None = None) -> BillingSubscription | None:
    if organization_id:
        organization_scope = BillingSubscription.objects.filter(organization_id=organization_id)
        if organization_scope.exists():
            return _active_subscription_for_queryset(organization_scope)
        # Legacy fallback during migration: allow null-org subscriptions only when they map
        # unambiguously to the selected organization context.
        scoped_emails = emails or sorted(_active_org_member_emails(organization_id=str(organization_id)))
        legacy_ids = _legacy_subscription_ids_for_organization(
            organization_id=str(organization_id),
            emails=scoped_emails,
        )
        if legacy_ids:
            return _active_subscription_for_queryset(BillingSubscription.objects.filter(id__in=legacy_ids))
        return None

    if not emails:
        return None
    return _active_subscription_for_queryset(
        BillingSubscription.objects.filter(
            registration_consumed_by_email__in=emails,
        )
    )


def _metadata_datetime(metadata: dict, key: str):
    raw_value = metadata.get(key)
    if not raw_value:
        return None
    if isinstance(raw_value, timezone.datetime):
        value = raw_value
    else:
        value = parse_datetime(str(raw_value))
    if value is None:
        return None
    if timezone.is_naive(value):
        value = timezone.make_aware(value, dt_timezone.utc)
    return value


def _subscription_cancellation_effective_at(subscription: BillingSubscription):
    metadata = subscription.metadata or {}
    effective_at = _metadata_datetime(metadata, "cancellation_effective_at")
    if effective_at is not None:
        return effective_at

    raw_payload = subscription.raw_last_payload or {}
    period_end_ts = raw_payload.get("current_period_end")
    if period_end_ts is not None:
        try:
            return timezone.datetime.fromtimestamp(int(period_end_ts), tz=dt_timezone.utc)
        except Exception:
            return None
    return None


def _normalize_subscription_runtime_state(
    subscription: BillingSubscription,
    *,
    now: timezone.datetime | None = None,
) -> BillingSubscription:
    metadata = dict(subscription.metadata or {})
    if not bool(metadata.get("cancel_at_period_end")):
        return subscription

    effective_at = _subscription_cancellation_effective_at(subscription)
    if effective_at is None:
        return subscription

    anchor = now or timezone.now()
    if effective_at > anchor:
        return subscription

    if subscription.status == "canceled":
        return subscription

    metadata["cancel_at_period_end"] = True
    metadata.setdefault("cancellation_effective_at", effective_at.isoformat())
    metadata.setdefault("canceled_at", anchor.isoformat())
    metadata.setdefault("cancellation_reason", "payment_method_removed")
    subscription.status = "canceled"
    subscription.payment_status = "canceled"
    subscription.metadata = metadata
    subscription.save(update_fields=["status", "payment_status", "metadata", "updated_at"])
    return subscription


def _plan_candidate_limit(plan_id: str | None) -> int | None:
    normalized_plan = str(plan_id or "").strip().lower()
    default_limit = int(getattr(settings, "BILLING_PLAN_DEFAULT_CANDIDATES_PER_MONTH", 0))
    plan_limits = {
        "starter": int(getattr(settings, "BILLING_PLAN_STARTER_CANDIDATES_PER_MONTH", 150)),
        "growth": int(getattr(settings, "BILLING_PLAN_GROWTH_CANDIDATES_PER_MONTH", 600)),
        "enterprise": int(getattr(settings, "BILLING_PLAN_ENTERPRISE_CANDIDATES_PER_MONTH", 0)),
    }

    raw_limit = plan_limits.get(normalized_plan, default_limit)
    if raw_limit <= 0:
        return None
    return raw_limit


def _plan_organization_seat_limit(plan_id: str | None) -> int | None:
    normalized_plan = str(plan_id or "").strip().lower()
    default_limit = int(getattr(settings, "BILLING_PLAN_DEFAULT_ORG_SEATS", 0))
    plan_limits = {
        "starter": int(getattr(settings, "BILLING_PLAN_STARTER_ORG_SEATS", 25)),
        "growth": int(getattr(settings, "BILLING_PLAN_GROWTH_ORG_SEATS", 100)),
        "enterprise": int(getattr(settings, "BILLING_PLAN_ENTERPRISE_ORG_SEATS", 0)),
    }

    raw_limit = plan_limits.get(normalized_plan, default_limit)
    if raw_limit <= 0:
        return None
    return raw_limit


def _organization_active_membership_count(*, organization_id: str) -> int:
    normalized_org_id = str(organization_id or "").strip()
    if not normalized_org_id:
        return 0
    return OrganizationMembership.objects.filter(
        organization_id=normalized_org_id,
        is_active=True,
    ).count()


def _candidate_usage_count(
    *,
    user,
    organization_id: str | None,
    legacy_organization_name: str,
    period_start,
    period_end,
) -> int:
    campaign_scope = VettingCampaign.objects.all()
    if organization_id:
        org_scoped_count = CandidateEnrollment.objects.filter(
            campaign__organization_id=organization_id,
            created_at__gte=period_start,
            created_at__lt=period_end,
        ).count()
        legacy_scoped_count = _legacy_candidate_usage_count_for_organization(
            organization_id=organization_id,
            period_start=period_start,
            period_end=period_end,
        )
        return org_scoped_count + legacy_scoped_count
    elif legacy_organization_name:
        campaign_scope = campaign_scope.filter(
            Q(organization__name__iexact=legacy_organization_name)
            | Q(organization_id__isnull=True, initiated_by__organization__iexact=legacy_organization_name)
        )
    else:
        campaign_scope = campaign_scope.filter(initiated_by=user)

    return CandidateEnrollment.objects.filter(
        campaign__in=campaign_scope,
        created_at__gte=period_start,
        created_at__lt=period_end,
    ).count()


def resolve_subscription_scope(user, *, organization_id: str | None = None) -> tuple[str, list[str], str, str | None]:
    return _scope_for_user(user, organization_id=organization_id)


def get_active_subscription_for_user(user, *, organization_id: str | None = None) -> BillingSubscription | None:
    _, emails, _, resolved_org_id = _scope_for_user(user, organization_id=organization_id)
    return _active_subscription_for_scope(emails=emails, organization_id=resolved_org_id)


def get_latest_subscription_for_user(user, *, organization_id: str | None = None) -> BillingSubscription | None:
    _, emails, _, resolved_org_id = _scope_for_user(user, organization_id=organization_id)
    subscription = None

    if resolved_org_id:
        subscription = (
            BillingSubscription.objects.filter(organization_id=resolved_org_id)
            .order_by("-updated_at", "-created_at")
            .first()
        )
        if subscription is None:
            legacy_ids = _legacy_subscription_ids_for_organization(
                organization_id=str(resolved_org_id),
                emails=emails,
            )
            if legacy_ids:
                subscription = (
                    BillingSubscription.objects.filter(id__in=legacy_ids)
                    .order_by("-updated_at", "-created_at")
                    .first()
                )
    elif emails:
        subscription = (
            BillingSubscription.objects.filter(
                registration_consumed_by_email__in=emails,
            )
            .order_by("-updated_at", "-created_at")
            .first()
        )

    if subscription is None:
        return None
    return _normalize_subscription_runtime_state(subscription)


def get_candidate_quota_snapshot(user, *, organization_id: str | None = None) -> CandidateQuotaSnapshot:
    period_start, period_end = _month_window()
    scope, emails, legacy_organization_name, resolved_org_id = _scope_for_user(
        user,
        organization_id=organization_id,
    )
    used = _candidate_usage_count(
        user=user,
        organization_id=resolved_org_id,
        legacy_organization_name=legacy_organization_name,
        period_start=period_start,
        period_end=period_end,
    )

    if not bool(getattr(settings, "BILLING_QUOTA_ENFORCEMENT_ENABLED", True)):
        return CandidateQuotaSnapshot(
            enforced=False,
            scope=scope,
            reason="quota_enforcement_disabled",
            plan_id=None,
            plan_name=None,
            limit=None,
            used=used,
            remaining=None,
            period_start=period_start,
            period_end=period_end,
        )

    subscription = _active_subscription_for_scope(emails=emails, organization_id=resolved_org_id)
    if subscription is None:
        return CandidateQuotaSnapshot(
            enforced=True,
            scope=scope,
            reason="subscription_required",
            plan_id=None,
            plan_name=None,
            limit=0,
            used=used,
            remaining=0,
            period_start=period_start,
            period_end=period_end,
        )

    limit = _plan_candidate_limit(subscription.plan_id)
    remaining = None if limit is None else max(limit - used, 0)
    return CandidateQuotaSnapshot(
        enforced=True,
        scope=scope,
        reason=None,
        plan_id=str(subscription.plan_id or "").strip().lower() or None,
        plan_name=str(subscription.plan_name or "").strip() or None,
        limit=limit,
        used=used,
        remaining=remaining,
        period_start=period_start,
        period_end=period_end,
    )


def enforce_candidate_quota(
    user,
    *,
    additional: int = 1,
    organization_id: str | None = None,
) -> CandidateQuotaSnapshot:
    snapshot = get_candidate_quota_snapshot(user, organization_id=organization_id)

    try:
        additional_count = int(additional)
    except Exception:
        additional_count = 0
    additional_count = max(additional_count, 0)

    if not snapshot.enforced or additional_count == 0:
        return snapshot

    if snapshot.limit is None:
        return snapshot

    projected = snapshot.used + additional_count
    if projected <= snapshot.limit:
        return snapshot

    if snapshot.reason == "subscription_required":
        raise ValidationError(
            {
                "detail": (
                    "No active paid subscription found for this workspace. "
                    "Complete subscription setup before adding candidates."
                ),
                "code": "subscription_required",
                "quota": {
                    "scope": snapshot.scope,
                    "used": snapshot.used,
                    "limit": snapshot.limit,
                    "remaining": snapshot.remaining,
                    "period_start": snapshot.period_start.isoformat(),
                    "period_end": snapshot.period_end.isoformat(),
                },
            }
        )

    raise ValidationError(
        {
            "detail": (
                f"Candidate quota exceeded for plan '{snapshot.plan_name or snapshot.plan_id or 'unknown'}'. "
                f"Monthly limit {snapshot.limit}, current usage {snapshot.used}, requested additional {additional_count}."
            ),
            "code": "quota_exceeded",
            "quota": {
                "scope": snapshot.scope,
                "plan_id": snapshot.plan_id,
                "plan_name": snapshot.plan_name,
                "used": snapshot.used,
                "limit": snapshot.limit,
                "remaining": snapshot.remaining,
                "requested_additional": additional_count,
                "projected_total": projected,
                "period_start": snapshot.period_start.isoformat(),
                "period_end": snapshot.period_end.isoformat(),
            },
        }
    )


def get_organization_seat_quota_snapshot(
    *,
    organization_id: str,
    subscription: BillingSubscription | None,
) -> OrganizationSeatQuotaSnapshot:
    normalized_org_id = str(organization_id or "").strip()
    if not normalized_org_id:
        return OrganizationSeatQuotaSnapshot(
            enforced=False,
            organization_id="",
            reason="missing_organization",
            plan_id=None,
            plan_name=None,
            limit=None,
            used=0,
            remaining=None,
        )

    enabled = bool(getattr(settings, "BILLING_ORG_MEMBER_QUOTA_ENFORCEMENT_ENABLED", True))
    if not enabled:
        return OrganizationSeatQuotaSnapshot(
            enforced=False,
            organization_id=normalized_org_id,
            reason="enforcement_disabled",
            plan_id=getattr(subscription, "plan_id", None),
            plan_name=getattr(subscription, "plan_name", None),
            limit=None,
            used=_organization_active_membership_count(organization_id=normalized_org_id),
            remaining=None,
        )

    if subscription is None:
        return OrganizationSeatQuotaSnapshot(
            enforced=True,
            organization_id=normalized_org_id,
            reason="missing_subscription",
            plan_id=None,
            plan_name=None,
            limit=0,
            used=_organization_active_membership_count(organization_id=normalized_org_id),
            remaining=0,
        )

    limit = _plan_organization_seat_limit(getattr(subscription, "plan_id", None))
    used = _organization_active_membership_count(organization_id=normalized_org_id)
    if limit is None:
        return OrganizationSeatQuotaSnapshot(
            enforced=True,
            organization_id=normalized_org_id,
            reason=None,
            plan_id=subscription.plan_id,
            plan_name=subscription.plan_name,
            limit=None,
            used=used,
            remaining=None,
        )

    remaining = max(limit - used, 0)
    return OrganizationSeatQuotaSnapshot(
        enforced=True,
        organization_id=normalized_org_id,
        reason=None,
        plan_id=subscription.plan_id,
        plan_name=subscription.plan_name,
        limit=limit,
        used=used,
        remaining=remaining,
    )


def enforce_organization_seat_quota(
    *,
    organization_id: str,
    subscription: BillingSubscription | None,
    additional: int = 1,
) -> OrganizationSeatQuotaSnapshot:
    snapshot = get_organization_seat_quota_snapshot(
        organization_id=organization_id,
        subscription=subscription,
    )
    if not snapshot.enforced:
        return snapshot

    try:
        additional_count = int(additional)
    except Exception as exc:
        raise ValidationError("Invalid organization seat reservation amount.") from exc

    if additional_count <= 0:
        return snapshot

    if snapshot.limit is None:
        return snapshot

    projected = snapshot.used + additional_count
    if projected <= snapshot.limit:
        return snapshot

    raise ValidationError(
        {
            "detail": "Organization member seat quota exceeded for the active subscription plan.",
            "code": "ORG_SEAT_QUOTA_EXCEEDED",
            "organization_id": snapshot.organization_id,
            "plan_id": snapshot.plan_id,
            "plan_name": snapshot.plan_name,
            "limit": snapshot.limit,
            "used": snapshot.used,
            "requested_additional": additional_count,
        }
    )


def _vetting_operation_multiplier(operation: str) -> int:
    normalized_operation = str(operation or "").strip().lower()
    default_multipliers = {
        VETTING_OPERATION_DOCUMENT_VERIFICATION: 10,
        VETTING_OPERATION_SOCIAL_PROFILE_CHECK: 2,
        VETTING_OPERATION_INTERVIEW_ANALYSIS: 20,
        VETTING_OPERATION_RUBRIC_EVALUATION: 5,
        VETTING_OPERATION_BACKGROUND_CHECK_SUBMISSION: 5,
    }
    setting_key = f"BILLING_OPERATION_{normalized_operation.upper()}_CANDIDATE_MULTIPLIER"
    configured = int(getattr(settings, setting_key, default_multipliers.get(normalized_operation, 0)) or 0)
    return max(configured, 0)


def _plan_vetting_operation_limit(plan_id: str | None, operation: str) -> int | None:
    normalized_plan = str(plan_id or "").strip().lower()
    normalized_operation = str(operation or "").strip().lower()
    if normalized_operation not in VETTING_OPERATION_KEYS:
        return None

    if normalized_plan in {"starter", "growth", "enterprise"}:
        plan_prefix = normalized_plan.upper()
    else:
        plan_prefix = "DEFAULT"

    setting_key = f"BILLING_PLAN_{plan_prefix}_{normalized_operation.upper()}_PER_MONTH"
    raw_explicit_limit = getattr(settings, setting_key, None)
    if raw_explicit_limit is not None:
        explicit_limit = int(raw_explicit_limit)
        if explicit_limit <= 0:
            return None
        return explicit_limit

    candidate_limit = _plan_candidate_limit(plan_id)
    if candidate_limit is None:
        return None
    multiplier = _vetting_operation_multiplier(normalized_operation)
    if multiplier <= 0:
        return None
    return candidate_limit * multiplier


def _scope_has_subscription_history(*, organization_id: str | None, emails: list[str]) -> bool:
    normalized_org_id = str(organization_id or "").strip()
    if normalized_org_id:
        if BillingSubscription.objects.filter(organization_id=normalized_org_id).exists():
            return True
        scoped_emails = emails or sorted(_active_org_member_emails(organization_id=normalized_org_id))
        legacy_ids = _legacy_subscription_ids_for_organization(
            organization_id=normalized_org_id,
            emails=scoped_emails,
        )
        return bool(legacy_ids)

    if emails:
        return BillingSubscription.objects.filter(registration_consumed_by_email__in=emails).exists()
    return False


def _operation_usage_count_for_org(
    *,
    operation: str,
    organization_id: str,
    period_start,
    period_end,
) -> int:
    normalized_operation = str(operation or "").strip().lower()
    normalized_org_id = str(organization_id or "").strip()
    if not normalized_org_id:
        return 0

    if normalized_operation == VETTING_OPERATION_DOCUMENT_VERIFICATION:
        from apps.applications.models import Document

        # Reserve verification capacity at upload time to fail fast before async work.
        return Document.objects.filter(
            case__organization_id=normalized_org_id,
            uploaded_at__gte=period_start,
            uploaded_at__lt=period_end,
        ).count()

    if normalized_operation == VETTING_OPERATION_SOCIAL_PROFILE_CHECK:
        try:
            from apps.fraud.models import SocialProfileCheckResult
        except Exception:
            return 0
        return SocialProfileCheckResult.objects.filter(
            application__organization_id=normalized_org_id,
            checked_at__gte=period_start,
            checked_at__lt=period_end,
        ).count()

    if normalized_operation == VETTING_OPERATION_INTERVIEW_ANALYSIS:
        from apps.interviews.models import InterviewResponse

        # Reserve analysis capacity when a response is answered/created, not only after processing.
        return InterviewResponse.objects.filter(
            session__case__organization_id=normalized_org_id,
            answered_at__isnull=False,
            answered_at__gte=period_start,
            answered_at__lt=period_end,
        ).count()

    if normalized_operation == VETTING_OPERATION_RUBRIC_EVALUATION:
        from apps.rubrics.models import RubricEvaluation

        return RubricEvaluation.objects.filter(
            case__organization_id=normalized_org_id,
            created_at__gte=period_start,
            created_at__lt=period_end,
        ).count()

    if normalized_operation == VETTING_OPERATION_BACKGROUND_CHECK_SUBMISSION:
        try:
            from apps.background_checks.models import BackgroundCheck
        except Exception:
            return 0
        return BackgroundCheck.objects.filter(
            case__organization_id=normalized_org_id,
            created_at__gte=period_start,
            created_at__lt=period_end,
        ).count()

    return 0


def _operation_usage_count_for_legacy_scope(
    *,
    operation: str,
    emails: list[str],
    period_start,
    period_end,
) -> int:
    normalized_operation = str(operation or "").strip().lower()
    normalized_emails = sorted({_normalized_email(email) for email in emails if _normalized_email(email)})
    if not normalized_emails:
        return 0

    if normalized_operation == VETTING_OPERATION_DOCUMENT_VERIFICATION:
        from apps.applications.models import Document

        return (
            Document.objects.filter(
                case__organization_id__isnull=True,
                uploaded_at__gte=period_start,
                uploaded_at__lt=period_end,
            )
            .filter(
                Q(case__applicant__email__in=normalized_emails)
                | Q(case__assigned_to__email__in=normalized_emails)
                | Q(case__candidate_enrollment__campaign__initiated_by__email__in=normalized_emails)
            )
            .distinct()
            .count()
        )

    if normalized_operation == VETTING_OPERATION_SOCIAL_PROFILE_CHECK:
        try:
            from apps.fraud.models import SocialProfileCheckResult
        except Exception:
            return 0
        return (
            SocialProfileCheckResult.objects.filter(
                application__organization_id__isnull=True,
                checked_at__gte=period_start,
                checked_at__lt=period_end,
            )
            .filter(
                Q(application__applicant__email__in=normalized_emails)
                | Q(application__assigned_to__email__in=normalized_emails)
                | Q(application__candidate_enrollment__campaign__initiated_by__email__in=normalized_emails)
            )
            .distinct()
            .count()
        )

    if normalized_operation == VETTING_OPERATION_INTERVIEW_ANALYSIS:
        from apps.interviews.models import InterviewResponse

        return (
            InterviewResponse.objects.filter(
                session__case__organization_id__isnull=True,
                answered_at__isnull=False,
                answered_at__gte=period_start,
                answered_at__lt=period_end,
            )
            .filter(
                Q(session__case__applicant__email__in=normalized_emails)
                | Q(session__case__assigned_to__email__in=normalized_emails)
                | Q(session__case__candidate_enrollment__campaign__initiated_by__email__in=normalized_emails)
            )
            .distinct()
            .count()
        )

    if normalized_operation == VETTING_OPERATION_RUBRIC_EVALUATION:
        from apps.rubrics.models import RubricEvaluation

        return (
            RubricEvaluation.objects.filter(
                case__organization_id__isnull=True,
                created_at__gte=period_start,
                created_at__lt=period_end,
            )
            .filter(
                Q(case__applicant__email__in=normalized_emails)
                | Q(case__assigned_to__email__in=normalized_emails)
                | Q(case__candidate_enrollment__campaign__initiated_by__email__in=normalized_emails)
            )
            .distinct()
            .count()
        )

    if normalized_operation == VETTING_OPERATION_BACKGROUND_CHECK_SUBMISSION:
        try:
            from apps.background_checks.models import BackgroundCheck
        except Exception:
            return 0
        return (
            BackgroundCheck.objects.filter(
                case__organization_id__isnull=True,
                created_at__gte=period_start,
                created_at__lt=period_end,
            )
            .filter(
                Q(case__applicant__email__in=normalized_emails)
                | Q(case__assigned_to__email__in=normalized_emails)
                | Q(case__candidate_enrollment__campaign__initiated_by__email__in=normalized_emails)
            )
            .distinct()
            .count()
        )

    return 0


def resolve_case_organization_id(case, *, actor=None) -> str | None:
    if case is None:
        if actor is None:
            return None
        scope, _emails, _legacy_org_name, resolved_org_id = _scope_for_user(actor, organization_id=None)
        if scope.startswith("organization:") and resolved_org_id:
            return str(resolved_org_id)
        return None

    direct_org_id = str(getattr(case, "organization_id", "") or "").strip()
    if direct_org_id:
        return direct_org_id

    enrollment = getattr(case, "candidate_enrollment", None)
    if enrollment is not None:
        campaign = getattr(enrollment, "campaign", None)
        campaign_org_id = str(getattr(campaign, "organization_id", "") or "").strip()
        if campaign_org_id:
            return campaign_org_id
        campaign_owner = getattr(campaign, "initiated_by", None)
        owner_scope, _owner_emails, _owner_legacy_org_name, owner_org_id = _scope_for_user(
            campaign_owner,
            organization_id=None,
        )
        if owner_scope.startswith("organization:") and owner_org_id:
            return str(owner_org_id)

    assigned_to = getattr(case, "assigned_to", None)
    scope, _emails, _legacy_org_name, resolved_org_id = _scope_for_user(assigned_to, organization_id=None)
    if scope.startswith("organization:") and resolved_org_id:
        return str(resolved_org_id)
    applicant = getattr(case, "applicant", None)
    applicant_scope, _applicant_emails, _applicant_legacy_org_name, applicant_org_id = _scope_for_user(
        applicant,
        organization_id=None,
    )
    if applicant_scope.startswith("organization:") and applicant_org_id:
        return str(applicant_org_id)
    if actor is not None:
        actor_scope, _actor_emails, _actor_legacy_org_name, actor_org_id = _scope_for_user(actor, organization_id=None)
        if actor_scope.startswith("organization:") and actor_org_id:
            return str(actor_org_id)
    return None


def get_vetting_operation_quota_snapshot(
    *,
    operation: str,
    user=None,
    organization_id: str | None = None,
) -> VettingOperationQuotaSnapshot:
    normalized_operation = str(operation or "").strip().lower()
    if normalized_operation not in VETTING_OPERATION_KEYS:
        raise ValidationError({"detail": f"Unsupported vetting operation '{operation}'."})

    period_start, period_end = _month_window()

    scope = "legacy"
    emails: list[str] = []
    resolved_org_id = str(organization_id or "").strip() or None
    if user is not None:
        scope, emails, _legacy_org_name, resolved_from_user = _scope_for_user(
            user,
            organization_id=organization_id,
        )
        resolved_org_id = resolved_from_user
    elif resolved_org_id:
        scope = f"organization:{resolved_org_id}"

    if not resolved_org_id:
        used = _operation_usage_count_for_legacy_scope(
            operation=normalized_operation,
            emails=emails,
            period_start=period_start,
            period_end=period_end,
        )
        active_subscription = _active_subscription_for_scope(
            emails=emails,
            organization_id=None,
        )
        has_history = _scope_has_subscription_history(
            organization_id=None,
            emails=emails,
        )
        if active_subscription is None:
            if has_history:
                return VettingOperationQuotaSnapshot(
                    enforced=True,
                    operation=normalized_operation,
                    scope=scope,
                    reason="subscription_required",
                    plan_id=None,
                    plan_name=None,
                    limit=0,
                    used=used,
                    remaining=0,
                    period_start=period_start,
                    period_end=period_end,
                )
            return VettingOperationQuotaSnapshot(
                enforced=False,
                operation=normalized_operation,
                scope=scope,
                reason="legacy_scope_no_org_context",
                plan_id=None,
                plan_name=None,
                limit=None,
                used=used,
                remaining=None,
                period_start=period_start,
                period_end=period_end,
            )
        limit = _plan_vetting_operation_limit(active_subscription.plan_id, normalized_operation)
        remaining = None if limit is None else max(limit - used, 0)
        return VettingOperationQuotaSnapshot(
            enforced=True,
            operation=normalized_operation,
            scope=scope,
            reason=None,
            plan_id=str(active_subscription.plan_id or "").strip().lower() or None,
            plan_name=str(active_subscription.plan_name or "").strip() or None,
            limit=limit,
            used=used,
            remaining=remaining,
            period_start=period_start,
            period_end=period_end,
        )

    used = _operation_usage_count_for_org(
        operation=normalized_operation,
        organization_id=resolved_org_id,
        period_start=period_start,
        period_end=period_end,
    )

    if not bool(getattr(settings, "BILLING_VETTING_OPERATION_QUOTA_ENFORCEMENT_ENABLED", True)):
        return VettingOperationQuotaSnapshot(
            enforced=False,
            operation=normalized_operation,
            scope=f"organization:{resolved_org_id}",
            reason="vetting_operation_enforcement_disabled",
            plan_id=None,
            plan_name=None,
            limit=None,
            used=used,
            remaining=None,
            period_start=period_start,
            period_end=period_end,
        )

    active_subscription = _active_subscription_for_scope(
        emails=emails,
        organization_id=resolved_org_id,
    )
    has_history = _scope_has_subscription_history(
        organization_id=resolved_org_id,
        emails=emails,
    )
    if active_subscription is None:
        if not has_history:
            return VettingOperationQuotaSnapshot(
                enforced=False,
                operation=normalized_operation,
                scope=f"organization:{resolved_org_id}",
                reason="legacy_no_billing_history",
                plan_id=None,
                plan_name=None,
                limit=None,
                used=used,
                remaining=None,
                period_start=period_start,
                period_end=period_end,
            )

        return VettingOperationQuotaSnapshot(
            enforced=True,
            operation=normalized_operation,
            scope=f"organization:{resolved_org_id}",
            reason="subscription_required",
            plan_id=None,
            plan_name=None,
            limit=0,
            used=used,
            remaining=0,
            period_start=period_start,
            period_end=period_end,
        )

    limit = _plan_vetting_operation_limit(active_subscription.plan_id, normalized_operation)
    remaining = None if limit is None else max(limit - used, 0)
    return VettingOperationQuotaSnapshot(
        enforced=True,
        operation=normalized_operation,
        scope=f"organization:{resolved_org_id}",
        reason=None,
        plan_id=str(active_subscription.plan_id or "").strip().lower() or None,
        plan_name=str(active_subscription.plan_name or "").strip() or None,
        limit=limit,
        used=used,
        remaining=remaining,
        period_start=period_start,
        period_end=period_end,
    )


def enforce_vetting_operation_quota(
    *,
    operation: str,
    user=None,
    organization_id: str | None = None,
    additional: int = 1,
) -> VettingOperationQuotaSnapshot:
    snapshot = get_vetting_operation_quota_snapshot(
        operation=operation,
        user=user,
        organization_id=organization_id,
    )

    try:
        additional_count = int(additional)
    except Exception as exc:
        raise ValidationError("Invalid vetting operation reservation amount.") from exc
    additional_count = max(additional_count, 0)

    if snapshot.reason == "subscription_required":
        raise ValidationError(
            {
                "detail": (
                    "No active paid subscription found for this organization. "
                    "Complete subscription setup before running this vetting operation."
                ),
                "code": "subscription_required",
                "quota": {
                    "operation": snapshot.operation,
                    "scope": snapshot.scope,
                    "used": snapshot.used,
                    "limit": snapshot.limit,
                    "remaining": snapshot.remaining,
                    "period_start": snapshot.period_start.isoformat(),
                    "period_end": snapshot.period_end.isoformat(),
                },
            }
        )

    if not snapshot.enforced or additional_count == 0:
        return snapshot
    if snapshot.limit is None:
        return snapshot

    projected = snapshot.used + additional_count
    if projected <= snapshot.limit:
        return snapshot

    raise ValidationError(
        {
            "detail": (
                f"Vetting operation quota exceeded for '{snapshot.operation}'. "
                f"Monthly limit {snapshot.limit}, current usage {snapshot.used}, requested additional {additional_count}."
            ),
            "code": "vetting_operation_quota_exceeded",
            "quota": {
                "operation": snapshot.operation,
                "scope": snapshot.scope,
                "plan_id": snapshot.plan_id,
                "plan_name": snapshot.plan_name,
                "used": snapshot.used,
                "limit": snapshot.limit,
                "remaining": snapshot.remaining,
                "requested_additional": additional_count,
                "projected_total": projected,
                "period_start": snapshot.period_start.isoformat(),
                "period_end": snapshot.period_end.isoformat(),
            },
        }
    )
