from __future__ import annotations

from dataclasses import dataclass
from datetime import timezone as dt_timezone

from django.conf import settings
from django.utils.dateparse import parse_datetime
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.authentication.models import User
from apps.candidates.models import CandidateEnrollment
from apps.campaigns.models import VettingCampaign

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


def _scope_for_user(user) -> tuple[str, list[str], str]:
    organization = str(getattr(user, "organization", "") or "").strip()
    if organization:
        org_users = User.objects.filter(organization__iexact=organization).only("email")
        emails = sorted({_normalized_email(member.email) for member in org_users if member.email})
        if not emails:
            emails = [_normalized_email(getattr(user, "email", ""))]
        return f"organization:{organization.lower()}", emails, organization

    email = _normalized_email(getattr(user, "email", ""))
    fallback_scope = email or f"user:{getattr(user, 'pk', 'unknown')}"
    return f"user:{fallback_scope}", ([email] if email else []), ""


def _active_subscription_for_scope(emails: list[str]) -> BillingSubscription | None:
    if not emails:
        return None
    latest_any = (
        BillingSubscription.objects.filter(
            registration_consumed_by_email__in=emails,
        )
        .order_by("-updated_at", "-created_at")
        .first()
    )
    if latest_any is not None:
        latest_any = _normalize_subscription_runtime_state(latest_any)
        if latest_any.status in {"canceled", "failed", "expired"}:
            return None
        if latest_any.payment_status in {"unpaid"} and latest_any.status != "complete":
            return None

    candidates = (
        BillingSubscription.objects.filter(
            registration_consumed_by_email__in=emails,
            status="complete",
            payment_status__in={"paid", "no_payment_required"},
        )
        .order_by("-updated_at", "-created_at")
    )
    now = timezone.now()
    for subscription in candidates:
        normalized = _normalize_subscription_runtime_state(subscription, now=now)
        if normalized.status == "complete" and normalized.payment_status in {"paid", "no_payment_required"}:
            return normalized
    return None


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


def _candidate_usage_count(user, organization: str, period_start, period_end) -> int:
    campaign_scope = VettingCampaign.objects.all()
    if organization:
        campaign_scope = campaign_scope.filter(initiated_by__organization__iexact=organization)
    else:
        campaign_scope = campaign_scope.filter(initiated_by=user)

    return CandidateEnrollment.objects.filter(
        campaign__in=campaign_scope,
        created_at__gte=period_start,
        created_at__lt=period_end,
    ).count()


def resolve_subscription_scope(user) -> tuple[str, list[str], str]:
    return _scope_for_user(user)


def get_active_subscription_for_user(user) -> BillingSubscription | None:
    _, emails, _ = _scope_for_user(user)
    return _active_subscription_for_scope(emails)


def get_latest_subscription_for_user(user) -> BillingSubscription | None:
    _, emails, _ = _scope_for_user(user)
    if not emails:
        return None
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


def get_candidate_quota_snapshot(user) -> CandidateQuotaSnapshot:
    period_start, period_end = _month_window()
    scope, emails, organization = _scope_for_user(user)
    used = _candidate_usage_count(
        user=user,
        organization=organization,
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

    subscription = _active_subscription_for_scope(emails)
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


def enforce_candidate_quota(user, *, additional: int = 1) -> CandidateQuotaSnapshot:
    snapshot = get_candidate_quota_snapshot(user)

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
