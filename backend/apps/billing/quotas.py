from __future__ import annotations

from dataclasses import dataclass
from datetime import timezone as dt_timezone

from django.conf import settings
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.exceptions import ValidationError

from django.db import connection

from apps.users.models import User
from apps.tenants.models import Organization
from apps.candidates.models import CandidateEnrollment
from apps.campaigns.models import VettingCampaign
from apps.core.authz import get_user_default_organization, get_user_organization_ids
from apps.governance.models import OrganizationMembership

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
    # In django-tenants the current tenant IS the organization.
    return str(getattr(connection.tenant, "name", "") or "").strip().lower()


def _active_org_member_emails() -> set[str]:
    # All membership records in this schema belong to the current tenant.
    return {
        _normalized_email(email)
        for email in User.objects.filter(
            organization_memberships__is_active=True,
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
    has_membership = OrganizationMembership.objects.filter(user=user, is_active=True).exists()
    org_ids = {str(connection.tenant.id)} if has_membership else set()
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
    # In django-tenants any user with an active membership belongs to this tenant's org.
    user_memberships = _active_membership_org_ids_for_user(user, cache=membership_cache)
    if user_memberships:
        return True
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
    # In django-tenants all candidate enrollments in this schema belong to the current tenant.
    return CandidateEnrollment.objects.filter(
        created_at__gte=period_start,
        created_at__lt=period_end,
    ).count()


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


def _trial_subscription_for_tenant() -> BillingSubscription | None:
    """Return an unsaved synthetic BillingSubscription for trial-tier tenants.

    When an Organization has ``tier='trial'`` but no BillingSubscription record
    yet exists, the quota system would otherwise block all operations with
    ``subscription_required``.  This helper synthesises a virtual subscription
    so that trial orgs receive their configured (small) limits immediately upon
    creation, with no payment step required.
    """
    try:
        tenant = connection.tenant
    except Exception:
        return None
    tier = getattr(tenant, "tier", None)
    if tier != "trial":
        return None
    sub = BillingSubscription(
        plan_id="trial",
        plan_name="Trial",
        status="complete",
        payment_status="no_payment_required",
    )
    return sub


def _active_subscription_for_scope(*, emails: list[str], organization_id: str | None = None) -> BillingSubscription | None:
    # organization_id param kept for API compatibility; schema isolation handles tenant scoping.
    qs = BillingSubscription.objects.all()
    if qs.exists():
        return _active_subscription_for_queryset(qs)
    if not emails:
        return _trial_subscription_for_tenant()
    result = _active_subscription_for_queryset(
        BillingSubscription.objects.filter(registration_consumed_by_email__in=emails)
    )
    if result is None:
        return _trial_subscription_for_tenant()
    return result


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
        "trial": int(getattr(settings, "BILLING_PLAN_TRIAL_CANDIDATES_PER_MONTH", 15)),
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
        "trial": int(getattr(settings, "BILLING_PLAN_TRIAL_ORG_SEATS", 5)),
        "starter": int(getattr(settings, "BILLING_PLAN_STARTER_ORG_SEATS", 25)),
        "growth": int(getattr(settings, "BILLING_PLAN_GROWTH_ORG_SEATS", 100)),
        "enterprise": int(getattr(settings, "BILLING_PLAN_ENTERPRISE_ORG_SEATS", 0)),
    }

    raw_limit = plan_limits.get(normalized_plan, default_limit)
    if raw_limit <= 0:
        return None
    return raw_limit


def _organization_active_membership_count() -> int:
    # All memberships in this schema belong to the current tenant.
    return OrganizationMembership.objects.filter(is_active=True).count()


def _candidate_usage_count(
    *,
    user,
    organization_id: str | None,
    legacy_organization_name: str,
    period_start,
    period_end,
) -> int:
    # In django-tenants all campaigns/enrollments are scoped to this tenant.
    return CandidateEnrollment.objects.filter(
        created_at__gte=period_start,
        created_at__lt=period_end,
    ).count()


def _scope_for_user(user, *, organization_id: str | None = None) -> tuple[str, list[str], str, str | None]:
    # In django-tenants the scope is always the current tenant.
    tenant = connection.tenant
    org_id = str(tenant.id)
    org_member_emails = _active_org_member_emails()
    return f"organization:{org_id}", sorted(org_member_emails), str(getattr(tenant, "name", "") or ""), org_id


def resolve_subscription_scope(user, *, organization_id: str | None = None) -> tuple[str, list[str], str, str | None]:
    return _scope_for_user(user, organization_id=organization_id)


def get_active_subscription_for_user(user, *, organization_id: str | None = None) -> BillingSubscription | None:
    _, emails, _, resolved_org_id = _scope_for_user(user, organization_id=organization_id)
    return _active_subscription_for_scope(emails=emails, organization_id=resolved_org_id)


def get_latest_subscription_for_user(user, *, organization_id: str | None = None) -> BillingSubscription | None:
    # organization_id param kept for API compatibility; schema isolation handles tenant scoping.
    subscription = (
        BillingSubscription.objects.all()
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
            used=_organization_active_membership_count(),
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
            used=_organization_active_membership_count(),
            remaining=0,
        )

    limit = _plan_organization_seat_limit(getattr(subscription, "plan_id", None))
    used = _organization_active_membership_count()
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


def enforce_membership_activation_seat_quota(
    *,
    organization_id: str,
    additional: int = 1,
) -> OrganizationSeatQuotaSnapshot | None:
    """
    Enforce organization seat quota for membership activation/reactivation.

    Caller is expected to run inside ``transaction.atomic`` so row locks remain
    held until the membership state change is committed.
    """
    normalized_org_id = str(organization_id or "").strip()
    if not normalized_org_id:
        return None

    # In django-tenants, the current schema IS the organization.  Verify that
    # the requested org ID matches the current tenant and that it is active.
    current_tenant = getattr(connection, "tenant", None)
    tenant_id = str(getattr(current_tenant, "id", "") or "")
    if tenant_id != normalized_org_id:
        # Mismatched org — use public-schema lock as fallback.
        locked_org_exists = Organization.objects.select_for_update().filter(
            id=normalized_org_id, is_active=True
        ).exists()
    else:
        locked_org_exists = getattr(current_tenant, "is_active", True)
    if not locked_org_exists:
        return None

    from .services import get_active_subscription_for_organization

    # First try org-FK-filtered lookup; fall back to schema-scoped (no filter)
    # so legacy subscriptions without an explicit org FK are still honoured.
    active_subscription = get_active_subscription_for_organization(
        organization_id=normalized_org_id
    )
    if active_subscription is None:
        active_subscription = get_active_subscription_for_organization()

    has_billing_history = BillingSubscription.objects.exists()

    # Backward-safe: do not block legacy organizations with no billing history.
    if active_subscription is None and not has_billing_history:
        return None

    return enforce_organization_seat_quota(
        organization_id=normalized_org_id,
        subscription=active_subscription,
        additional=additional,
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

    if normalized_plan in {"trial", "starter", "growth", "enterprise"}:
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
        # BillingSubscription no longer has an organization FK; schema
        # isolation already scopes this to the current tenant.
        if BillingSubscription.objects.exists():
            return True
        scoped_emails = emails or sorted(_active_org_member_emails())
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
    # In django-tenants all records in this schema belong to the current tenant;
    # no organization_id filter is required.
    normalized_operation = str(operation or "").strip().lower()

    if normalized_operation == VETTING_OPERATION_DOCUMENT_VERIFICATION:
        from apps.applications.models import Document

        return Document.objects.filter(
            uploaded_at__gte=period_start,
            uploaded_at__lt=period_end,
        ).count()

    if normalized_operation == VETTING_OPERATION_SOCIAL_PROFILE_CHECK:
        try:
            from apps.fraud.models import SocialProfileCheckResult
        except Exception:
            return 0
        return SocialProfileCheckResult.objects.filter(
            checked_at__gte=period_start,
            checked_at__lt=period_end,
        ).count()

    if normalized_operation == VETTING_OPERATION_INTERVIEW_ANALYSIS:
        from apps.interviews.models import InterviewResponse

        return InterviewResponse.objects.filter(
            answered_at__isnull=False,
            answered_at__gte=period_start,
            answered_at__lt=period_end,
        ).count()

    if normalized_operation == VETTING_OPERATION_RUBRIC_EVALUATION:
        from apps.rubrics.models import RubricEvaluation

        return RubricEvaluation.objects.filter(
            created_at__gte=period_start,
            created_at__lt=period_end,
        ).count()

    if normalized_operation == VETTING_OPERATION_BACKGROUND_CHECK_SUBMISSION:
        try:
            from apps.background_checks.models import BackgroundCheck
        except Exception:
            return 0
        return BackgroundCheck.objects.filter(
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
    # In django-tenants all records in this schema belong to the current tenant.
    # Delegate to the org-scoped counter which already handles schema isolation.
    return _operation_usage_count_for_org(
        operation=operation,
        organization_id="",
        period_start=period_start,
        period_end=period_end,
    )


def resolve_case_organization_id(case, *, actor=None) -> str | None:
    """Return the current tenant's organization ID.

    In django-tenants every record in the active schema belongs to the current
    tenant; there is no per-row organization FK to resolve.
    """
    tenant_id = str(getattr(getattr(connection, "tenant", None), "id", "") or "").strip()
    return tenant_id or None


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
            strict_scope_resolution = bool(
                getattr(settings, "BILLING_VETTING_REQUIRE_SCOPE_RESOLUTION", True)
            ) and bool(getattr(settings, "BILLING_VETTING_OPERATION_QUOTA_ENFORCEMENT_ENABLED", True))
            if strict_scope_resolution:
                return VettingOperationQuotaSnapshot(
                    enforced=True,
                    operation=normalized_operation,
                    scope=scope,
                    reason="organization_context_required",
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
    if snapshot.reason == "organization_context_required":
        raise ValidationError(
            {
                "detail": (
                    "Organization context could not be resolved for this vetting operation. "
                    "Assign the record to an organization-scoped actor or set organization ownership before retrying."
                ),
                "code": "organization_context_required",
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
