from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta, timezone as dt_timezone
import hashlib
import hmac
import secrets
from urllib.parse import urlencode

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .models import BillingSubscription, OrganizationOnboardingToken


ONBOARDING_TOKEN_PREFIX = "org_onb"
ONBOARDING_TOKEN_DEFAULT_TTL_HOURS = 72
ONBOARDING_TOKEN_DEFAULT_MAX_USES = 25


@dataclass
class OnboardingTokenValidationResult:
    valid: bool
    reason: str
    token_record: OrganizationOnboardingToken | None = None
    subscription: BillingSubscription | None = None
    remaining_uses: int | None = None


def _token_pepper() -> str:
    configured = str(getattr(settings, "BILLING_ORG_ONBOARDING_TOKEN_PEPPER", "") or "").strip()
    return configured or str(getattr(settings, "SECRET_KEY", "") or "")


def _normalized_email_domain(value: str | None) -> str:
    normalized = str(value or "").strip().lower()
    if normalized.startswith("@"):
        normalized = normalized[1:]
    return normalized


def token_hash(raw_token: str) -> str:
    normalized = str(raw_token or "").strip()
    digest = hashlib.sha256()
    digest.update(f"{_token_pepper()}:{normalized}".encode("utf-8"))
    return digest.hexdigest()


def token_preview(raw_token: str) -> str:
    normalized = str(raw_token or "").strip()
    if not normalized:
        return ""
    return f"h_{token_hash(normalized)[:12]}"


def generate_raw_onboarding_token() -> str:
    return f"{ONBOARDING_TOKEN_PREFIX}_{secrets.token_urlsafe(48)}"


def build_onboarding_link(raw_token: str) -> str:
    frontend_base = str(getattr(settings, "FRONTEND_URL", "") or "").strip().rstrip("/")
    if not frontend_base:
        return ""
    query = urlencode({"onboarding_token": raw_token})
    return f"{frontend_base}/register?{query}"


def is_subscription_active(subscription: BillingSubscription | None, *, now=None) -> bool:
    if subscription is None:
        return False

    moment = now or timezone.now()
    if subscription.status != "complete":
        return False
    if subscription.payment_status not in {"paid", "no_payment_required"}:
        return False
    if subscription.status in {"failed", "canceled", "expired"}:
        return False
    if subscription.ticket_expires_at and subscription.ticket_expires_at <= moment:
        return False

    metadata = subscription.metadata if isinstance(subscription.metadata, dict) else {}
    cancellation_effective_raw = metadata.get("cancellation_effective_at")
    cancellation_effective = parse_datetime(str(cancellation_effective_raw or "")) if cancellation_effective_raw else None
    if cancellation_effective and timezone.is_naive(cancellation_effective):
        cancellation_effective = timezone.make_aware(cancellation_effective, timezone=dt_timezone.utc)
    if cancellation_effective and cancellation_effective <= moment:
        return False
    return True


def get_active_subscription_for_organization(*, organization_id: str | None) -> BillingSubscription | None:
    normalized_org_id = str(organization_id or "").strip()
    if not normalized_org_id:
        return None

    candidates = (
        BillingSubscription.objects.filter(organization_id=normalized_org_id)
        .order_by("-updated_at", "-created_at")
    )
    for subscription in candidates.iterator(chunk_size=100):
        if is_subscription_active(subscription):
            return subscription
    return None


def deactivate_active_onboarding_tokens(
    *,
    organization_id: str,
    reason: str,
    revoked_by=None,
    when=None,
) -> int:
    normalized_org_id = str(organization_id or "").strip()
    if not normalized_org_id:
        return 0
    now = when or timezone.now()
    update_kwargs = {
        "is_active": False,
        "revoked_at": now,
        "revoked_reason": str(reason or "")[:255],
        "updated_at": now,
    }
    if revoked_by is not None:
        update_kwargs["created_by"] = revoked_by
    return (
        OrganizationOnboardingToken.objects.filter(
            organization_id=normalized_org_id,
            is_active=True,
        )
        .update(**update_kwargs)
    )


def create_organization_onboarding_token(
    *,
    organization,
    subscription: BillingSubscription,
    created_by=None,
    expires_at=None,
    max_uses: int | None = None,
    allowed_email_domain: str = "",
    rotate: bool = True,
    metadata: dict | None = None,
) -> tuple[OrganizationOnboardingToken, str]:
    if organization is None:
        raise ValueError("organization is required")
    if subscription is None:
        raise ValueError("subscription is required")
    if str(getattr(subscription, "organization_id", "") or "") != str(getattr(organization, "id", "") or ""):
        raise ValueError("subscription does not belong to organization")
    if not is_subscription_active(subscription):
        raise ValueError("organization subscription is not active")

    now = timezone.now()
    if rotate:
        deactivate_active_onboarding_tokens(
            organization_id=str(organization.id),
            reason="rotated",
            revoked_by=created_by,
            when=now,
        )

    default_max_uses = int(
        getattr(settings, "BILLING_ORG_ONBOARDING_DEFAULT_MAX_USES", ONBOARDING_TOKEN_DEFAULT_MAX_USES)
    )
    resolved_max_uses = default_max_uses if max_uses is None else int(max_uses)
    if resolved_max_uses <= 0:
        raise ValueError("max_uses must be greater than zero")

    if expires_at is None:
        ttl_hours = int(getattr(settings, "BILLING_ORG_ONBOARDING_DEFAULT_TTL_HOURS", ONBOARDING_TOKEN_DEFAULT_TTL_HOURS))
        ttl_hours = max(1, ttl_hours)
        expires_at = now + timedelta(hours=ttl_hours)

    normalized_domain = _normalized_email_domain(allowed_email_domain)
    payload_metadata = metadata if isinstance(metadata, dict) else {}

    for _ in range(5):
        raw_token = generate_raw_onboarding_token()
        hashed = token_hash(raw_token)
        preview = token_preview(raw_token)
        try:
            token_record = OrganizationOnboardingToken.objects.create(
                organization=organization,
                subscription=subscription,
                token_hash=hashed,
                token_prefix=preview,
                is_active=True,
                expires_at=expires_at,
                max_uses=resolved_max_uses,
                uses=0,
                allowed_email_domain=normalized_domain,
                created_by=created_by,
                metadata=payload_metadata,
            )
            return token_record, raw_token
        except IntegrityError:
            continue

    raise RuntimeError("Unable to generate a unique onboarding token")


def get_active_onboarding_token_for_organization(*, organization_id: str | None) -> OrganizationOnboardingToken | None:
    normalized_org_id = str(organization_id or "").strip()
    if not normalized_org_id:
        return None
    return (
        OrganizationOnboardingToken.objects.filter(
            organization_id=normalized_org_id,
            is_active=True,
        )
        .order_by("-created_at")
        .first()
    )


def validate_organization_onboarding_token(
    *,
    raw_token: str,
    email: str = "",
    consume: bool = False,
    expected_organization_id: str | None = None,
    now=None,
) -> OnboardingTokenValidationResult:
    if consume and not transaction.get_connection().in_atomic_block:
        raise RuntimeError(
            "validate_organization_onboarding_token(consume=True) must run inside transaction.atomic()."
        )

    normalized_token = str(raw_token or "").strip()
    if not normalized_token:
        return OnboardingTokenValidationResult(valid=False, reason="missing_token")

    token_qs = OrganizationOnboardingToken.objects.filter(token_hash=token_hash(normalized_token))
    token_record = token_qs.select_for_update().first() if consume else token_qs.first()
    if token_record is None:
        return OnboardingTokenValidationResult(valid=False, reason="not_found")

    moment = now or timezone.now()
    expected_org_id = str(expected_organization_id or "").strip()
    token_org_id = str(token_record.organization_id or "")
    if expected_org_id and token_org_id != expected_org_id:
        return OnboardingTokenValidationResult(valid=False, reason="organization_mismatch", token_record=token_record)

    if not token_record.is_active:
        return OnboardingTokenValidationResult(valid=False, reason="inactive", token_record=token_record)

    if token_record.expires_at and token_record.expires_at <= moment:
        return OnboardingTokenValidationResult(valid=False, reason="expired", token_record=token_record)

    max_uses = token_record.max_uses
    if max_uses is not None and token_record.uses >= max_uses:
        if token_record.is_active:
            token_record.is_active = False
            token_record.revoked_at = moment
            token_record.revoked_reason = "max_uses_reached"
            token_record.save(update_fields=["is_active", "revoked_at", "revoked_reason", "updated_at"])
        return OnboardingTokenValidationResult(valid=False, reason="max_uses_reached", token_record=token_record)

    normalized_allowed_domain = _normalized_email_domain(token_record.allowed_email_domain)
    normalized_email = str(email or "").strip().lower()
    if normalized_allowed_domain:
        if not normalized_email or "@" not in normalized_email:
            return OnboardingTokenValidationResult(valid=False, reason="email_required", token_record=token_record)
        submitted_domain = normalized_email.rsplit("@", 1)[-1]
        if not hmac.compare_digest(submitted_domain, normalized_allowed_domain):
            return OnboardingTokenValidationResult(valid=False, reason="email_domain_not_allowed", token_record=token_record)

    active_subscription = get_active_subscription_for_organization(organization_id=token_org_id)
    if active_subscription is None:
        return OnboardingTokenValidationResult(valid=False, reason="subscription_inactive", token_record=token_record)

    if consume:
        token_record.uses = int(token_record.uses or 0) + 1
        token_record.last_used_at = moment
        if token_record.subscription_id != active_subscription.id:
            token_record.subscription = active_subscription
        update_fields = ["uses", "last_used_at", "subscription", "updated_at"]
        if token_record.max_uses is not None and token_record.uses >= token_record.max_uses:
            token_record.is_active = False
            token_record.revoked_at = moment
            token_record.revoked_reason = "max_uses_reached"
            update_fields.extend(["is_active", "revoked_at", "revoked_reason"])
        token_record.save(update_fields=update_fields)

    remaining_uses = None
    if token_record.max_uses is not None:
        remaining_uses = max(int(token_record.max_uses) - int(token_record.uses), 0)

    return OnboardingTokenValidationResult(
        valid=True,
        reason="ok",
        token_record=token_record,
        subscription=active_subscription,
        remaining_uses=remaining_uses,
    )


def sync_onboarding_tokens_for_subscription(subscription: BillingSubscription | None) -> None:
    if subscription is None:
        return
    organization_id = str(getattr(subscription, "organization_id", "") or "")
    if not organization_id:
        return
    if is_subscription_active(subscription):
        return
    deactivate_active_onboarding_tokens(
        organization_id=organization_id,
        reason="subscription_inactive",
    )
