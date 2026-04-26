from datetime import timedelta, timezone as dt_timezone
from decimal import Decimal
from uuid import UUID, uuid4
import hashlib
import hmac
import json
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from django.conf import settings
from django.core.cache import cache
from django.db import connection, transaction
from django.db.models import Q
from django.utils.dateparse import parse_datetime
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
import requests

try:
    from drf_spectacular.utils import extend_schema
except ModuleNotFoundError:  # pragma: no cover - optional in lightweight setups
    def extend_schema(*args: object, **kwargs: object):  # type: ignore[misc]
        def decorator(func):
            return func

        return decorator

from .models import BillingSubscription, BillingWebhookEvent
from .quotas import (
    get_active_subscription_for_user,
    get_candidate_quota_snapshot,
    get_latest_subscription_for_user,
    get_organization_seat_quota_snapshot,
)
from .services import (
    build_onboarding_link,
    create_organization_onboarding_token,
    deactivate_active_onboarding_tokens,
    get_active_onboarding_token_for_organization,
    get_active_subscription_for_organization,
    sync_onboarding_tokens_for_subscription,
    validate_organization_onboarding_token,
)

from apps.core.permissions import (
    get_request_active_organization_id,
    get_request_tenant_context,
    is_platform_admin_user,
)
from apps.core.policies.registry_policy import (
    ORG_GOVERNANCE_ADMIN_MEMBERSHIP_ROLES,
    can_manage_registry_governance,
)
from .serializers import (
    BillingActionErrorSerializer,
    CheckoutConfirmErrorSerializer,
    BillingExchangeRateResponseSerializer,
    BillingHealthResponseSerializer,
    OrganizationOnboardingTokenGenerateResponseSerializer,
    OrganizationOnboardingTokenGenerateSerializer,
    OrganizationOnboardingTokenRevokeSerializer,
    OrganizationOnboardingTokenStateResponseSerializer,
    OrganizationOnboardingTokenSendInviteSerializer,
    OrganizationOnboardingTokenSendInviteResponseSerializer,
    OrganizationOnboardingTokenValidateResponseSerializer,
    OrganizationOnboardingTokenValidateSerializer,
    BillingPaymentMethodUpdateSerializer,
    BillingPortalSessionResponseSerializer,
    BillingQuotaResponseSerializer,
    BillingSubscriptionManageResponseSerializer,
    BillingSubscriptionRetryResponseSerializer,
    BillingWebhookResponseSerializer,
    PaystackCheckoutSessionConfirmSerializer,
    PaystackCheckoutSessionConfirmResponseSerializer,
    PaystackCheckoutSessionCreateSerializer,
    StripeCheckoutSessionConfirmSerializer,
    StripeCheckoutSessionConfirmResponseSerializer,
    StripeCheckoutSessionCreateSerializer,
    SubscriptionAccessVerifySerializer,
    SubscriptionConfirmSerializer,
)

try:
    import stripe
except ModuleNotFoundError:  # pragma: no cover - optional in lightweight setups
    stripe = None

try:
    from apps.audit.events import log_event, request_ip_address
except Exception:  # pragma: no cover - audit app may be optional in some setups
    def log_event(**kwargs: object) -> bool:
        return False

    def request_ip_address(request: object) -> str | None:  # type: ignore[misc]
        meta = getattr(request, "META", {}) or {}
        forwarded_for = str(meta.get("HTTP_X_FORWARDED_FOR", "") or "").strip()
        if forwarded_for:
            return forwarded_for.split(",")[0].strip() or None
        remote_addr = str(meta.get("REMOTE_ADDR", "") or "").strip()
        return remote_addr or None



def _ticket_ttl_hours() -> int:
    return max(1, int(getattr(settings, "BILLING_SUBSCRIPTION_TICKET_TTL_HOURS", 24)))


def _build_subscription_ticket(
    *,
    plan_id: str,
    plan_name: str,
    billing_cycle: str,
    payment_method: str,
    amount_usd: float,
    reference: str,
):
    now = timezone.now()
    expires_at = now + timedelta(hours=_ticket_ttl_hours())

    return {
        "planId": plan_id,
        "planName": plan_name,
        "billingCycle": billing_cycle,
        "paymentMethod": payment_method,
        "amountUsd": amount_usd,
        "reference": reference,
        "confirmedAt": int(now.timestamp() * 1000),
        "expiresAt": int(expires_at.timestamp() * 1000),
    }


def _ensure_checkout_placeholder(url: str) -> str:
    if "{CHECKOUT_SESSION_ID}" in url:
        return url
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}stripe_session_id={{CHECKOUT_SESSION_ID}}"


def _default_success_url() -> str:
    frontend_base = str(getattr(settings, "FRONTEND_URL", "http://localhost:3000")).rstrip("/")
    return f"{frontend_base}/billing/success?stripe_session_id={{CHECKOUT_SESSION_ID}}"


def _default_cancel_url() -> str:
    frontend_base = str(getattr(settings, "FRONTEND_URL", "http://localhost:3000")).rstrip("/")
    return f"{frontend_base}/billing/cancel"


def _default_success_url_no_provider_marker() -> str:
    frontend_base = str(getattr(settings, "FRONTEND_URL", "http://localhost:3000")).rstrip("/")
    return f"{frontend_base}/billing/success"


def _stripe_secret_key() -> str:
    return str(getattr(settings, "STRIPE_SECRET_KEY", "") or "").strip()


def _stripe_webhook_secret() -> str:
    return str(getattr(settings, "STRIPE_WEBHOOK_SECRET", "") or "").strip()


def _stripe_event_organization_id(event_type: str, event_data: dict) -> str | None:
    """Extract organization_id from a Stripe event's metadata (plain dict form).

    - checkout.session.* and customer.subscription.* events: metadata is on the object itself.
    - invoice.* events: metadata lives on subscription_details.metadata (populated when
      subscription_data.metadata was set at checkout creation time).
    """
    metadata: dict = {}
    if event_type.startswith("checkout.session.") or event_type.startswith("customer.subscription."):
        metadata = dict(event_data.get("metadata") or {})
    elif event_type.startswith("invoice."):
        sub_details = dict(event_data.get("subscription_details") or {})
        metadata = dict(sub_details.get("metadata") or {})
    return _normalized_organization_id(metadata.get("organization_id"))


def _paystack_secret_key() -> str:
    return str(getattr(settings, "PAYSTACK_SECRET_KEY", "") or "").strip()


def _paystack_base_url() -> str:
    return str(getattr(settings, "PAYSTACK_BASE_URL", "https://api.paystack.co") or "https://api.paystack.co").rstrip("/")


def _paystack_currency() -> str:
    return str(getattr(settings, "PAYSTACK_CURRENCY", "USD") or "USD").strip().upper()


def _ensure_stripe_ready() -> None:
    if stripe is None:
        raise ValidationError("Stripe SDK is not installed on the backend.")

    secret_key = _stripe_secret_key()
    if not secret_key:
        raise ValidationError("Stripe is not configured. Set STRIPE_SECRET_KEY.")

    stripe.api_key = secret_key


def _ensure_stripe_webhook_ready() -> None:
    if stripe is None:
        raise ValidationError("Stripe SDK is not installed on the backend.")

    webhook_secret = _stripe_webhook_secret()
    if not webhook_secret:
        raise ValidationError("Stripe webhook is not configured. Set STRIPE_WEBHOOK_SECRET.")


def _stripe_create_checkout_session(**kwargs):
    return stripe.checkout.Session.create(**kwargs)


def _stripe_retrieve_checkout_session(session_id: str):
    return stripe.checkout.Session.retrieve(session_id)


def _stripe_construct_event(payload: bytes, sig_header: str):
    return stripe.Webhook.construct_event(payload=payload, sig_header=sig_header, secret=_stripe_webhook_secret())


def _stripe_create_billing_portal_session(**kwargs):
    return stripe.billing_portal.Session.create(**kwargs)


def _stripe_retrieve_subscription(subscription_id: str):
    return stripe.Subscription.retrieve(subscription_id, expand=["default_payment_method"])


def _stripe_modify_subscription(subscription_id: str, **kwargs):
    return stripe.Subscription.modify(subscription_id, **kwargs)


def _stripe_retrieve_checkout_session_with_expansions(session_id: str):
    return stripe.checkout.Session.retrieve(session_id, expand=["subscription", "customer"])


def _ensure_paystack_ready() -> None:
    secret_key = _paystack_secret_key()
    if not secret_key:
        raise ValidationError("Paystack is not configured. Set PAYSTACK_SECRET_KEY.")


def _paystack_headers() -> dict:
    return {
        "Authorization": f"Bearer {_paystack_secret_key()}",
        "Content-Type": "application/json",
    }


def _paystack_initialize_transaction(payload: dict) -> dict:
    endpoint = f"{_paystack_base_url()}/transaction/initialize"
    try:
        response = requests.post(
            endpoint,
            json=payload,
            headers=_paystack_headers(),
            timeout=20,
        )
    except requests.RequestException as exc:
        raise ValidationError(f"Unable to connect to Paystack initialize endpoint: {exc}") from exc

    try:
        payload_data = response.json()
    except ValueError as exc:
        raise ValidationError("Paystack initialize response was not valid JSON.") from exc

    if response.status_code >= 400 or not bool(payload_data.get("status")):
        message = payload_data.get("message") or "Unable to initialize Paystack transaction."
        raise ValidationError(str(message))

    data = payload_data.get("data")
    if not isinstance(data, dict):
        raise ValidationError("Paystack initialize response missing data payload.")
    return data


def _paystack_verify_transaction(reference: str) -> dict:
    endpoint = f"{_paystack_base_url()}/transaction/verify/{reference}"
    try:
        response = requests.get(
            endpoint,
            headers=_paystack_headers(),
            timeout=20,
        )
    except requests.RequestException as exc:
        raise ValidationError(f"Unable to connect to Paystack verify endpoint: {exc}") from exc

    try:
        payload_data = response.json()
    except ValueError as exc:
        raise ValidationError("Paystack verify response was not valid JSON.") from exc

    if response.status_code >= 400 or not bool(payload_data.get("status")):
        message = payload_data.get("message") or "Unable to verify Paystack transaction."
        raise ValidationError(str(message))

    data = payload_data.get("data")
    if not isinstance(data, dict):
        raise ValidationError("Paystack verify response missing data payload.")
    return data


def _paystack_channel_to_payment_method(channel: str) -> str:
    normalized = str(channel or "").strip().lower()
    if normalized in {"mobile_money", "ussd", "qr", "eft", "bank", "bank_transfer"}:
        if normalized in {"mobile_money"}:
            return "mobile_money"
        return "bank_transfer"
    return "card"


def _paystack_channels_for_requested_method(payment_method: str) -> list[str] | None:
    normalized = str(payment_method or "").strip().lower()
    if normalized == "mobile_money":
        return ["mobile_money"]
    if normalized == "bank_transfer":
        return ["bank_transfer"]
    if normalized == "card":
        return ["card"]
    return None


def _paystack_signature(payload: bytes) -> str:
    secret = _paystack_secret_key().encode("utf-8")
    return hmac.new(secret, payload, hashlib.sha512).hexdigest()


def _is_valid_paystack_signature(payload: bytes, signature: str) -> bool:
    expected = _paystack_signature(payload)
    candidate = str(signature or "").strip().lower()
    return bool(candidate) and hmac.compare_digest(expected, candidate)


def _to_decimal(value, fallback: str = "0.00") -> Decimal:
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal(fallback)


def _exchange_rate_api_url(base_currency: str, target_currency: str) -> str:
    raw_url = str(getattr(settings, "EXCHANGE_RATE_API_URL", "") or "").strip()
    if not raw_url:
        return ""

    if any(token in raw_url for token in ("{base}", "{target}", "{from}", "{to}")):
        return (
            raw_url.replace("{base}", base_currency)
            .replace("{target}", target_currency)
            .replace("{from}", base_currency)
            .replace("{to}", target_currency)
        )

    try:
        parsed = urlparse(raw_url)
        query = dict(parse_qsl(parsed.query, keep_blank_values=True))
        query.setdefault("base", base_currency)
        query.setdefault("symbols", target_currency)
        return urlunparse(parsed._replace(query=urlencode(query)))
    except Exception:
        return raw_url


def _extract_exchange_rate(payload: dict, base_currency: str, target_currency: str) -> Decimal | None:
    target = str(target_currency or "").strip().upper()
    base = str(base_currency or "").strip().upper()
    if not target or not base:
        return None

    pair_key = f"{base}{target}"

    def _positive_decimal(value) -> Decimal | None:
        candidate = _to_decimal(value, fallback="0")
        if candidate > 0:
            return candidate
        return None

    def _from_mapping(mapping: dict) -> Decimal | None:
        for key in (target, target.lower(), pair_key):
            if key in mapping:
                rate = _positive_decimal(mapping.get(key))
                if rate is not None:
                    return rate
        return None

    top_level_rate = _positive_decimal(payload.get("rate"))
    if top_level_rate is not None:
        return top_level_rate

    for key in ("exchange_rate", "conversion_rate", "price", "value"):
        rate = _positive_decimal(payload.get(key))
        if rate is not None:
            return rate

    containers = [payload, payload.get("data"), payload.get("result"), payload.get("info")]
    for container in containers:
        if not isinstance(container, dict):
            continue

        direct_rate = _from_mapping(container)
        if direct_rate is not None:
            return direct_rate

        for nested_key in ("rates", "conversion_rates", "quotes", "data"):
            nested = container.get(nested_key)
            if isinstance(nested, dict):
                nested_rate = _from_mapping(nested)
                if nested_rate is not None:
                    return nested_rate

        info = container.get("info")
        if isinstance(info, dict):
            info_rate = _positive_decimal(info.get("rate"))
            if info_rate is not None:
                return info_rate

    return None


def _fetch_exchange_rate(base_currency: str, target_currency: str) -> Decimal | None:
    url = _exchange_rate_api_url(base_currency, target_currency)
    if not url:
        return None

    timeout = max(1, int(getattr(settings, "EXCHANGE_RATE_API_TIMEOUT_SECONDS", 8)))
    try:
        response = requests.get(url, timeout=timeout)
    except requests.RequestException:
        return None

    if response.status_code >= 400:
        return None

    try:
        payload = response.json()
    except ValueError:
        return None

    if not isinstance(payload, dict):
        return None
    return _extract_exchange_rate(payload, base_currency, target_currency)


def _paystack_usd_exchange_rate() -> Decimal:
    rate, _ = _paystack_usd_exchange_rate_with_source()
    return rate


def _paystack_usd_exchange_rate_with_source() -> tuple[Decimal, str]:
    fallback_raw = getattr(settings, "PAYSTACK_USD_EXCHANGE_RATE", 1.0)
    fallback_rate = _to_decimal(fallback_raw, fallback="1.0")
    if fallback_rate <= 0:
        fallback_rate = Decimal("1.0")

    target_currency = _paystack_currency()
    if target_currency == "USD":
        return Decimal("1.0"), "identity"

    api_url = _exchange_rate_api_url("USD", target_currency)
    if not api_url:
        return fallback_rate, "fallback"

    cache_key_hash = hashlib.sha256(api_url.encode("utf-8")).hexdigest()[:16]
    cache_key = f"billing:fx:USD:{target_currency}:{cache_key_hash}"
    cached_value = cache.get(cache_key)
    if cached_value is not None:
        cached_rate = _to_decimal(cached_value, fallback="0")
        if cached_rate > 0:
            return cached_rate, "api_cache"

    live_rate = _fetch_exchange_rate("USD", target_currency)
    if live_rate is not None and live_rate > 0:
        cache_ttl = max(60, int(getattr(settings, "EXCHANGE_RATE_CACHE_TTL_SECONDS", 3600)))
        cache.set(cache_key, str(live_rate), cache_ttl)
        return live_rate, "api_live"

    return fallback_rate, "fallback"


def _paystack_exchange_rate_health() -> dict:
    fallback_raw = getattr(settings, "PAYSTACK_USD_EXCHANGE_RATE", 1.0)
    fallback_rate = _to_decimal(fallback_raw, fallback="1.0")
    if fallback_rate <= 0:
        fallback_rate = Decimal("1.0")

    target_currency = _paystack_currency()
    api_url_configured = False
    if target_currency != "USD":
        api_url_configured = bool(_exchange_rate_api_url("USD", target_currency))

    timeout_seconds = max(1, int(getattr(settings, "EXCHANGE_RATE_API_TIMEOUT_SECONDS", 8)))
    cache_ttl_seconds = max(60, int(getattr(settings, "EXCHANGE_RATE_CACHE_TTL_SECONDS", 3600)))

    return {
        "api_url_configured": api_url_configured,
        "fallback_rate": float(fallback_rate),
        "timeout_seconds": timeout_seconds,
        "cache_ttl_seconds": cache_ttl_seconds,
    }


def _paystack_amount_minor_from_usd(amount_usd: Decimal) -> int:
    usd_amount = _to_decimal(amount_usd, fallback="0.00")
    currency = _paystack_currency()
    local_amount = usd_amount
    if currency != "USD":
        local_amount = usd_amount * _paystack_usd_exchange_rate()
    return int((local_amount * Decimal("100")).quantize(Decimal("1")))


def _paystack_amount_usd_from_minor(amount_minor: Decimal) -> Decimal:
    local_amount = _to_decimal(amount_minor, fallback="0") / Decimal("100")
    currency = _paystack_currency()
    if currency == "USD":
        return local_amount
    exchange_rate = _paystack_usd_exchange_rate()
    if exchange_rate <= 0:
        return local_amount
    return local_amount / exchange_rate


def _fit_model_field_value(model_cls, field_name: str, value: str | None) -> str:
    text = str(value or "")
    try:
        field = model_cls._meta.get_field(field_name)
    except Exception:
        return text
    max_length = getattr(field, "max_length", None)
    if isinstance(max_length, int) and max_length > 0 and len(text) > max_length:
        return text[:max_length]
    return text


def _extract_amount_usd(session_data: dict) -> Decimal:
    amount_total = session_data.get("amount_total")
    if amount_total is not None:
        return _to_decimal(amount_total) / Decimal("100")

    metadata = session_data.get("metadata") or {}
    amount_from_metadata = metadata.get("amount_usd")
    return _to_decimal(amount_from_metadata)


def _parse_iso_datetime(value):
    if not value:
        return None
    parsed = parse_datetime(str(value))
    if parsed is None:
        return None
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, dt_timezone.utc)
    return parsed


def _subscription_period_bounds(subscription: BillingSubscription) -> tuple[timezone.datetime | None, timezone.datetime | None]:
    metadata = dict(subscription.metadata or {})
    current_period_start = _parse_iso_datetime(metadata.get("current_period_start"))
    current_period_end = _parse_iso_datetime(metadata.get("current_period_end"))

    if current_period_end is not None:
        return current_period_start, current_period_end

    anchor_start = subscription.ticket_confirmed_at or subscription.updated_at or timezone.now()
    if subscription.billing_cycle == "annual":
        fallback_end = anchor_start + timedelta(days=365)
    else:
        fallback_end = anchor_start + timedelta(days=30)
    return current_period_start or anchor_start, fallback_end


def _subscription_cancellation_fields(subscription: BillingSubscription):
    metadata = dict(subscription.metadata or {})
    cancel_at_period_end = bool(metadata.get("cancel_at_period_end"))
    requested_at = _parse_iso_datetime(metadata.get("cancellation_requested_at"))
    effective_at = _parse_iso_datetime(metadata.get("cancellation_effective_at"))
    return cancel_at_period_end, requested_at, effective_at


def _build_latest_subscription_incident(
    *,
    subscription: BillingSubscription,
    metadata: dict,
    cancel_at_period_end: bool,
    cancellation_effective_at,
    retry_available: bool,
) -> dict | None:
    normalized_provider = str(getattr(subscription, "provider", "") or "billing").strip().lower() or "billing"
    normalized_status = str(getattr(subscription, "status", "") or "").strip().lower()
    normalized_payment_status = str(getattr(subscription, "payment_status", "") or "").strip().lower()
    payment_failure_event = str(metadata.get("last_payment_failure_event") or "").strip()
    payment_failure_at = _parse_iso_datetime(metadata.get("last_payment_failure_at"))
    invoice_payment_failed_at = _parse_iso_datetime(metadata.get("last_invoice_payment_failed_at"))

    if (
        payment_failure_event
        or payment_failure_at is not None
        or invoice_payment_failed_at is not None
        or normalized_status in {"failed", "expired", "canceled", "cancelled"}
        or normalized_payment_status in {"failed", "unpaid", "past_due"}
    ):
        if payment_failure_event:
            message = f"{normalized_provider.title()} reported a payment failure event ({payment_failure_event})."
        elif invoice_payment_failed_at is not None:
            message = f"{normalized_provider.title()} reported an invoice payment failure."
        elif normalized_payment_status in {"failed", "unpaid", "past_due"}:
            message = (
                f"The current payment status is {normalized_payment_status.replace('_', ' ')}."
            )
        else:
            message = f"The current subscription status is {normalized_status.replace('_', ' ')}."

        return {
            "code": "payment_failed",
            "message": message,
            "detected_at": payment_failure_at or invoice_payment_failed_at or subscription.updated_at,
            "source": normalized_provider,
            "event_type": payment_failure_event or None,
        }

    if cancel_at_period_end:
        return {
            "code": "cancellation_scheduled",
            "message": "Cancellation is scheduled at the end of the current billing period.",
            "detected_at": cancellation_effective_at or subscription.updated_at,
            "source": normalized_provider,
            "event_type": None,
        }

    if retry_available:
        return {
            "code": "retry_available",
            "message": "Billing retry is available for this subscription.",
            "detected_at": subscription.updated_at,
            "source": normalized_provider,
            "event_type": None,
        }

    return None


def _hydrate_stripe_identifiers(subscription: BillingSubscription):
    metadata = dict(subscription.metadata or {})
    raw_payload = dict(subscription.raw_last_payload or {})

    customer_id = metadata.get("stripe_customer_id") or raw_payload.get("customer")
    stripe_subscription_id = metadata.get("stripe_subscription_id") or raw_payload.get("subscription")

    if (customer_id and stripe_subscription_id) or not subscription.session_id:
        return str(customer_id or "") or None, str(stripe_subscription_id or "") or None

    try:
        _ensure_stripe_ready()
        session = _stripe_retrieve_checkout_session_with_expansions(subscription.session_id)
        if session is not None:
            session_data = session._to_dict_recursive() if hasattr(session, "_to_dict_recursive") else dict(session)
        else:
            session_data = {}
        customer_id = customer_id or session_data.get("customer")
        stripe_subscription_id = stripe_subscription_id or session_data.get("subscription")
    except Exception:
        return str(customer_id or "") or None, str(stripe_subscription_id or "") or None

    if customer_id or stripe_subscription_id:
        metadata["stripe_customer_id"] = customer_id
        metadata["stripe_subscription_id"] = stripe_subscription_id
        subscription.metadata = metadata
        subscription.save(update_fields=["metadata", "updated_at"])

    return str(customer_id or "") or None, str(stripe_subscription_id or "") or None


def _stripe_payment_method_summary(stripe_subscription: dict, fallback_type: str) -> dict:
    payment_method = stripe_subscription.get("default_payment_method")
    if isinstance(payment_method, str):
        payment_method = None

    if isinstance(payment_method, dict):
        card = payment_method.get("card") or {}
        brand = str(card.get("brand") or "").strip() or None
        last4 = str(card.get("last4") or "").strip() or None
        exp_month = card.get("exp_month")
        exp_year = card.get("exp_year")
        display = None
        if brand and last4:
            display = f"{brand.title()} •••• {last4}"
        elif last4:
            display = f"Card •••• {last4}"

        return {
            "type": "card",
            "display": display or "Card",
            "brand": brand,
            "last4": last4,
            "exp_month": int(exp_month) if exp_month else None,
            "exp_year": int(exp_year) if exp_year else None,
        }

    return {
        "type": fallback_type or None,
        "display": (fallback_type or "Payment method").replace("_", " ").title(),
        "brand": None,
        "last4": None,
        "exp_month": None,
        "exp_year": None,
    }


def _build_subscription_summary(subscription: BillingSubscription) -> dict:
    from django.db import connection as _db_conn
    _tenant = getattr(_db_conn, "tenant", None)
    metadata = dict(subscription.metadata or {})
    payment_method = subscription.payment_method

    period_start, period_end = _subscription_period_bounds(subscription)
    cancel_at_period_end, cancellation_requested_at, cancellation_effective_at = _subscription_cancellation_fields(
        subscription
    )

    if subscription.provider == "stripe":
        customer_id, stripe_subscription_id = _hydrate_stripe_identifiers(subscription)
        metadata = dict(subscription.metadata or {})
        if customer_id:
            metadata["stripe_customer_id"] = customer_id
        if stripe_subscription_id:
            metadata["stripe_subscription_id"] = stripe_subscription_id

        if stripe_subscription_id:
            try:
                _ensure_stripe_ready()
                stripe_subscription = dict(_stripe_retrieve_subscription(stripe_subscription_id))
                cancel_at_period_end = bool(stripe_subscription.get("cancel_at_period_end", cancel_at_period_end))
                period_start_ts = stripe_subscription.get("current_period_start")
                period_end_ts = stripe_subscription.get("current_period_end")
                if period_start_ts:
                    period_start = timezone.datetime.fromtimestamp(int(period_start_ts), tz=dt_timezone.utc)
                if period_end_ts:
                    period_end = timezone.datetime.fromtimestamp(int(period_end_ts), tz=dt_timezone.utc)
                payment_method_summary = _stripe_payment_method_summary(stripe_subscription, payment_method)
                metadata["payment_method_summary"] = payment_method_summary
                metadata["current_period_start"] = period_start.isoformat() if period_start else None
                metadata["current_period_end"] = period_end.isoformat() if period_end else None
                metadata["cancel_at_period_end"] = cancel_at_period_end
                if cancel_at_period_end and period_end and not cancellation_effective_at:
                    cancellation_effective_at = period_end
                    metadata["cancellation_effective_at"] = period_end.isoformat()
                subscription.metadata = metadata
                subscription.save(update_fields=["metadata", "updated_at"])
            except Exception:
                payment_method_summary = metadata.get("payment_method_summary")
        else:
            payment_method_summary = metadata.get("payment_method_summary")
    else:
        payment_method_summary = metadata.get("payment_method_summary")

    if not isinstance(payment_method_summary, dict):
        payment_method_summary = {
            "type": payment_method or None,
            "display": (payment_method or "Payment method").replace("_", " ").title(),
            "brand": None,
            "last4": None,
            "exp_month": None,
            "exp_year": None,
        }

    retry_available = bool(subscription.status in {"failed", "canceled", "expired"} or subscription.payment_status in {"unpaid"})
    retry_reason = None
    if retry_available:
        retry_reason = subscription.status if subscription.status in {"failed", "canceled", "expired"} else "payment_unpaid"

    can_update_payment_method = subscription.status == "complete" and subscription.provider in {"stripe", "sandbox"}
    can_delete_payment_method = subscription.status == "complete" and not cancel_at_period_end
    latest_incident = _build_latest_subscription_incident(
        subscription=subscription,
        metadata=metadata,
        cancel_at_period_end=cancel_at_period_end,
        cancellation_effective_at=cancellation_effective_at,
        retry_available=retry_available,
    )

    # Use the explicit subscription FK when available; fall back to the
    # current tenant (schema-isolation path used in production).
    _sub_org_id = str(getattr(subscription, "organization_id", "") or "").strip()
    _tenant_id = str(getattr(_tenant, "id", "") or "").strip()
    _org_id = _sub_org_id or _tenant_id or None
    _org_name = str(getattr(_tenant, "name", "") or "").strip() or None
    return {
        "id": subscription.id,
        "organization_id": _org_id,
        "organization_name": _org_name,
        "provider": subscription.provider,
        "status": subscription.status,
        "payment_status": subscription.payment_status,
        "plan_id": subscription.plan_id,
        "plan_name": subscription.plan_name,
        "billing_cycle": subscription.billing_cycle,
        "amount_usd": subscription.amount_usd,
        "payment_method": payment_method_summary,
        "checkout_url": subscription.checkout_url or None,
        "current_period_start": period_start,
        "current_period_end": period_end,
        "cancel_at_period_end": cancel_at_period_end,
        "cancellation_requested_at": cancellation_requested_at,
        "cancellation_effective_at": cancellation_effective_at,
        "can_update_payment_method": can_update_payment_method,
        "can_delete_payment_method": can_delete_payment_method,
        "retry_available": retry_available,
        "retry_reason": retry_reason,
        "latest_incident": latest_incident,
        "updated_at": subscription.updated_at,
    }


def _scope_subscription_for_request_user(*, request, user) -> tuple[BillingSubscription | None, BillingSubscription | None]:
    organization_id = _request_billing_organization_id(request)
    active = get_active_subscription_for_user(user, organization_id=organization_id)
    latest = get_latest_subscription_for_user(user, organization_id=organization_id)
    return active, latest


def _find_subscription_by_stripe_subscription_id(stripe_subscription_id: str) -> BillingSubscription | None:
    if not stripe_subscription_id:
        return None
    candidates = BillingSubscription.objects.filter(provider="stripe").order_by("-updated_at", "-created_at")
    for subscription in candidates:
        metadata = dict(subscription.metadata or {})
        raw_payload = dict(subscription.raw_last_payload or {})
        if str(metadata.get("stripe_subscription_id") or "") == stripe_subscription_id:
            return subscription
        if str(raw_payload.get("subscription") or "") == stripe_subscription_id:
            return subscription
    return None


def _find_subscription_by_paystack_reference(reference: str) -> BillingSubscription | None:
    normalized = str(reference or "").strip()
    if not normalized:
        return None
    return (
        BillingSubscription.objects.filter(provider="paystack")
        .filter(session_id=normalized)
        .order_by("-updated_at", "-created_at")
        .first()
        or BillingSubscription.objects.filter(provider="paystack", reference=normalized)
        .order_by("-updated_at", "-created_at")
        .first()
    )


def _ms_to_datetime(ms: int | None):
    if ms is None:
        return None
    try:
        return timezone.datetime.fromtimestamp(int(ms) / 1000, tz=dt_timezone.utc)
    except Exception:
        return None


def _datetime_to_ms(value):
    if value is None:
        return None
    return int(value.timestamp() * 1000)


def _normalized_organization_id(value) -> str | None:
    raw_value = str(value or "").strip()
    if not raw_value:
        return None
    try:
        return str(UUID(raw_value))
    except Exception:
        return None


def _request_billing_organization_id(request) -> str | None:
    return _normalized_organization_id(get_request_active_organization_id(request))


def _request_explicit_billing_organization_id(request) -> str | None:
    query_value = _normalized_organization_id(getattr(request, "query_params", {}).get("organization_id"))
    if query_value:
        return query_value
    data = getattr(request, "data", None)
    if data is not None and hasattr(data, "get"):
        return _normalized_organization_id(data.get("organization_id") or data.get("organization"))
    return None


def _billing_schema_exists(schema_name: str | None) -> bool:
    normalized_schema = str(schema_name or "").strip()
    if not normalized_schema:
        return False
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1 FROM pg_namespace WHERE nspname = %s", [normalized_schema])
        return cursor.fetchone() is not None


def _resolve_billing_schema_organization(organization_id: str | None):
    from apps.tenants.models import Organization

    def _current_schema_organization():
        current_schema = str(getattr(connection, "schema_name", "") or "")
        if not current_schema or current_schema == "public":
            return None

        current_tenant = getattr(connection, "tenant", None)
        if (
            current_tenant is not None
            and str(getattr(current_tenant, "schema_name", "") or "") == current_schema
            and getattr(current_tenant, "is_active", True) is not False
        ):
            return current_tenant

        return Organization.objects.filter(schema_name=current_schema, is_active=True).first()

    if organization_id:
        organization = Organization.objects.filter(id=organization_id, is_active=True).first()
        if organization is not None and _billing_schema_exists(getattr(organization, "schema_name", "")):
            return organization
        return _current_schema_organization()

    return _current_schema_organization()


def _can_manage_governance_billing_scope(user, *, organization_id=None) -> bool:
    return can_manage_registry_governance(
        user,
        organization_id=organization_id,
        allow_membershipless_fallback=False,
    )


def _raise_org_setup_required(*, action_label: str) -> None:
    raise ValidationError(
        {
            "detail": (
                f"Select or create an active organization before {action_label}. "
                "Use the organization setup flow first."
            ),
            "code": "ORG_SETUP_REQUIRED",
            "setup_path": "/organization/setup",
        }
    )


def _resolve_onboarding_management_organization(request):
    from apps.tenants.models import Organization

    user = getattr(request, "user", None)
    tenant_context = get_request_tenant_context(request)
    invalid_requested_org_id = str(tenant_context.get("invalid_requested_organization_id") or "").strip()
    if invalid_requested_org_id and not is_platform_admin_user(user):
        raise NotFound("Selected organization was not found in your governance scope.")

    organization_id = _request_billing_organization_id(request)
    if not organization_id and is_platform_admin_user(user):
        organization_id = _request_explicit_billing_organization_id(request)
    if not organization_id:
        _raise_org_setup_required(action_label="managing onboarding tokens")

    organization = Organization.objects.filter(id=organization_id, is_active=True).first()
    if organization is None:
        raise NotFound("Selected organization was not found or is inactive.")

    if is_platform_admin_user(user):
        return organization

    if not _can_manage_governance_billing_scope(user, organization_id=organization_id):
        raise PermissionDenied("You do not have permission to manage organization onboarding tokens.")
    return organization


def _resolve_checkout_organization_id(request) -> str:
    """
    Resolve and authorize checkout context to prevent unscoped subscription creation.
    """
    request_user = getattr(request, "user", None)
    if not bool(getattr(request_user, "is_authenticated", False)):
        raise PermissionDenied("Authentication credentials were not provided.")

    tenant_context = get_request_tenant_context(request)
    invalid_requested_org_id = str(tenant_context.get("invalid_requested_organization_id") or "").strip()
    if invalid_requested_org_id and not is_platform_admin_user(request_user):
        raise NotFound("Selected organization was not found in your governance scope.")

    organization_id = _request_billing_organization_id(request)
    if not organization_id and is_platform_admin_user(request_user):
        organization_id = _request_explicit_billing_organization_id(request)
    if not organization_id:
        _raise_org_setup_required(action_label="starting checkout")

    from apps.tenants.models import Organization

    selected_organization = Organization.objects.filter(id=organization_id, is_active=True).first()

    if selected_organization is None:
        raise NotFound("Selected organization was not found or is inactive.")

    if not _can_manage_governance_billing_scope(request_user, organization_id=organization_id):
        raise PermissionDenied("You do not have permission to initiate billing checkout.")

    return organization_id


def _send_onboarding_invite_email(
    *,
    recipient_email: str,
    organization_name: str,
    onboarding_link: str,
    invited_by: str,
    expires_at=None,
    allowed_email_domain: str = "",
) -> None:
    """Send an onboarding invite email to recipient_email with the given link."""
    from django.core.mail import EmailMultiAlternatives
    from django.template.loader import render_to_string
    from django.utils.html import strip_tags

    subject = f"You're invited to join {organization_name} on CAVP"
    context = {
        "organization_name": organization_name,
        "onboarding_link": onboarding_link,
        "invited_by": invited_by,
        "expires_at": expires_at.strftime("%Y-%m-%d %H:%M UTC") if expires_at else None,
        "allowed_email_domain": allowed_email_domain or "",
    }
    try:
        html_body = render_to_string("emails/onboarding_invite.html", context)
        text_body = strip_tags(html_body)
    except Exception:
        html_body = None
        text_body = (
            f"You have been invited by {invited_by} to join {organization_name} on CAVP.\n\n"
            f"Accept your invitation: {onboarding_link}\n"
        )
        if expires_at:
            text_body += f"\nThis link expires on {context['expires_at']}."

    from_email = str(getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@cavp.app"))
    email_msg = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=from_email,
        to=[recipient_email],
    )
    if html_body:
        email_msg.attach_alternative(html_body, "text/html")
    email_msg.send(fail_silently=False)


def _serialize_onboarding_token_state(token_record):
    if token_record is None:
        return None
    metadata = token_record.metadata if isinstance(token_record.metadata, dict) else {}
    remaining_uses = None
    if token_record.max_uses is not None:
        remaining_uses = max(int(token_record.max_uses) - int(token_record.uses), 0)
    return {
        "id": token_record.id,
        "subscription_id": token_record.subscription_id,
        "token_preview": token_record.token_prefix,
        "is_active": bool(token_record.is_active),
        "expires_at": token_record.expires_at,
        "max_uses": token_record.max_uses,
        "uses": int(token_record.uses),
        "remaining_uses": remaining_uses,
        "allowed_email_domain": str(token_record.allowed_email_domain or ""),
        "last_used_at": token_record.last_used_at,
        "revoked_at": token_record.revoked_at,
        "revoked_reason": str(token_record.revoked_reason or ""),
        "revoked_by_email": str(metadata.get("revoked_by_email", "") or ""),
        "created_at": token_record.created_at,
        "updated_at": token_record.updated_at,
    }


def _onboarding_token_validation_payload(*, validation_result):
    from django.db import connection as _db_conn
    payload = {
        "valid": bool(validation_result.valid),
        "reason": str(validation_result.reason),
    }
    token_record = validation_result.token_record
    if token_record is None:
        return payload
    _tenant = getattr(_db_conn, "tenant", None)
    # Prefer explicit org_id from the subscription FK; fall back to current tenant.
    sub = validation_result.subscription
    sub_org_id = str(getattr(sub, "organization_id", "") or "") if sub else ""
    org_id = sub_org_id or str(getattr(_tenant, "id", "") or "") or None
    org_name = str(getattr(_tenant, "name", "") or "")
    if sub_org_id and _tenant and str(getattr(_tenant, "id", "")) != sub_org_id:
        try:
            from apps.tenants.models import Organization as _Org
            _org = _Org.objects.filter(id=sub_org_id).first()
            if _org is not None:
                org_name = str(_org.name or "")
        except Exception:
            pass
    payload.update(
        {
            "organization_id": org_id,
            "organization_name": org_name,
            "subscription_id": sub.id if sub else None,
            "remaining_uses": validation_result.remaining_uses,
            "expires_at": token_record.expires_at,
        }
    )
    return payload


def _resolve_subscription_access_state(reference: str) -> tuple[bool, str, BillingSubscription | None]:
    subscription = (
        BillingSubscription.objects.filter(reference=reference)
        .order_by("-created_at")
        .first()
    )
    if subscription is None:
        return False, "not_found", None

    if subscription.status != "complete":
        return False, "not_complete", subscription

    if subscription.payment_status not in {"paid", "no_payment_required"}:
        return False, "unpaid", subscription

    if subscription.ticket_expires_at and subscription.ticket_expires_at <= timezone.now():
        return False, "expired", subscription

    if subscription.registration_consumed_at is not None:
        return False, "already_consumed", subscription

    return True, "ok", subscription


def _verify_rate_limit_enabled() -> bool:
    return bool(getattr(settings, "BILLING_SUBSCRIPTION_VERIFY_RATE_LIMIT_ENABLED", True))


def _verify_rate_limit_per_minute() -> int:
    return max(1, int(getattr(settings, "BILLING_SUBSCRIPTION_VERIFY_RATE_LIMIT_PER_MINUTE", 30)))


def _onboarding_token_validate_rate_limit_enabled() -> bool:
    return bool(getattr(settings, "BILLING_ONBOARDING_TOKEN_VALIDATE_RATE_LIMIT_ENABLED", True))


def _onboarding_token_validate_rate_limit_per_minute() -> int:
    return max(1, int(getattr(settings, "BILLING_ONBOARDING_TOKEN_VALIDATE_RATE_LIMIT_PER_MINUTE", 30)))


def _checkout_confirm_rate_limit_enabled() -> bool:
    return bool(getattr(settings, "BILLING_CHECKOUT_CONFIRM_RATE_LIMIT_ENABLED", True))


def _checkout_confirm_rate_limit_per_minute() -> int:
    return max(1, int(getattr(settings, "BILLING_CHECKOUT_CONFIRM_RATE_LIMIT_PER_MINUTE", 60)))


def _billing_health_require_staff() -> bool:
    return bool(getattr(settings, "BILLING_HEALTH_REQUIRE_STAFF", False))


def _resolve_billing_alert_organization_id(
    *,
    subscription: BillingSubscription | None = None,
    extra_metadata: dict | None = None,
) -> str | None:
    subscription_organization_id = _normalized_organization_id(
        getattr(subscription, "organization_id", None)
    )
    if subscription_organization_id:
        return subscription_organization_id

    if extra_metadata:
        return _normalized_organization_id(extra_metadata.get("organization_id"))

    return None


def _billing_alert_recipients(*, organization_id: str | None = None):
    # organization_id param kept for API compatibility; schema isolation handles tenant scoping.
    try:
        from apps.users.models import User
    except Exception:
        return []

    platform_alert_filter = Q(user_type="admin") | Q(is_staff=True) | Q(is_superuser=True)
    governance_alert_filter = Q(
        organization_memberships__is_active=True,
        organization_memberships__membership_role__in=tuple(ORG_GOVERNANCE_ADMIN_MEMBERSHIP_ROLES),
    )
    return User.all_objects.filter(is_active=True).filter(
        platform_alert_filter | governance_alert_filter
    ).distinct()


def _notify_billing_processing_error(
    *,
    provider: str,
    webhook_event: BillingWebhookEvent,
    error_message: str,
    billing_event_type: str = "",
    subscription: BillingSubscription | None = None,
    extra_metadata: dict | None = None,
) -> None:
    try:
        from apps.notifications.services import NotificationService
    except Exception:
        return

    organization_id = _resolve_billing_alert_organization_id(
        subscription=subscription,
        extra_metadata=extra_metadata,
    )
    recipients = _billing_alert_recipients(organization_id=organization_id)
    if not recipients:
        return

    normalized_provider = str(provider or "billing").strip().lower() or "billing"
    normalized_event_type = str(
        billing_event_type or getattr(webhook_event, "event_type", "") or ""
    ).strip()
    event_identifier = (
        str(getattr(webhook_event, "event_id", "") or "").strip()
        or str(getattr(webhook_event, "id", "") or "").strip()
        or "unknown"
    )
    metadata = {
        "event_type": "processing_error",
        "subsystem": "billing",
        "provider": normalized_provider,
        "billing_event_type": normalized_event_type,
        "webhook_record_id": str(getattr(webhook_event, "id", "") or ""),
        "webhook_event_id": str(getattr(webhook_event, "event_id", "") or ""),
        "webhook_processing_status": str(getattr(webhook_event, "processing_status", "") or ""),
        "error_message": str(error_message or ""),
    }

    if subscription is not None:
        metadata.update(
            {
                "subscription_id": str(getattr(subscription, "id", "") or ""),
                "organization_id": str(getattr(subscription, "organization_id", "") or ""),
                "session_id": str(getattr(subscription, "session_id", "") or ""),
                "reference": str(getattr(subscription, "reference", "") or ""),
            }
        )

    if extra_metadata:
        metadata.update(extra_metadata)

    subject = f"{normalized_provider.title()} billing processing error"
    if normalized_event_type:
        message = (
            f"{normalized_provider.title()} billing webhook processing failed for "
            f"event {normalized_event_type}. Error: {error_message}"
        )
    else:
        message = f"{normalized_provider.title()} billing processing failed. Error: {error_message}"

    idempotency_key = (
        f"billing_processing_error:{normalized_provider}:{normalized_event_type or 'unknown'}:{event_identifier}"
    )

    for recipient in recipients:
        NotificationService.send_admin_notification(
            recipient,
            notification_type="processing_error",
            title=subject,
            message=message,
            metadata=metadata,
            idempotency_key=idempotency_key,
        )


def _notify_billing_payment_failure(
    *,
    provider: str,
    billing_event_type: str,
    subscription: BillingSubscription | None = None,
    reference: str = "",
    extra_metadata: dict | None = None,
) -> None:
    try:
        from apps.notifications.services import NotificationService
    except Exception:
        return

    organization_id = _resolve_billing_alert_organization_id(
        subscription=subscription,
        extra_metadata=extra_metadata,
    )
    recipients = _billing_alert_recipients(organization_id=organization_id)
    if not recipients:
        return

    normalized_provider = str(provider or "billing").strip().lower() or "billing"
    normalized_event_type = str(billing_event_type or "").strip() or "unknown"
    resolved_reference = (
        str(reference or "").strip()
        or str(getattr(subscription, "reference", "") or "").strip()
        or str(getattr(subscription, "session_id", "") or "").strip()
    )
    metadata = {
        "event_type": "billing_payment_failed",
        "subsystem": "billing",
        "provider": normalized_provider,
        "billing_event_type": normalized_event_type,
        "reference": resolved_reference,
    }

    if subscription is not None:
        metadata.update(
            {
                "subscription_id": str(getattr(subscription, "id", "") or ""),
                "organization_id": str(getattr(subscription, "organization_id", "") or ""),
                "session_id": str(getattr(subscription, "session_id", "") or ""),
                "plan_id": str(getattr(subscription, "plan_id", "") or ""),
                "plan_name": str(getattr(subscription, "plan_name", "") or ""),
                "payment_status": str(getattr(subscription, "payment_status", "") or ""),
                "subscription_status": str(getattr(subscription, "status", "") or ""),
            }
        )

    if extra_metadata:
        metadata.update(extra_metadata)

    subject = f"{normalized_provider.title()} payment issue detected"
    message = (
        f"{normalized_provider.title()} reported a payment failure event "
        f"({normalized_event_type})"
    )
    if resolved_reference:
        message = f"{message} for reference {resolved_reference}."
    else:
        message = f"{message}."

    idempotency_key = (
        f"billing_payment_failed:{normalized_provider}:{normalized_event_type}:{resolved_reference or 'unknown'}"
    )

    for recipient in recipients:
        NotificationService.send_admin_notification(
            recipient,
            notification_type="billing_payment_failed",
            title=subject,
            message=message,
            metadata=metadata,
            idempotency_key=idempotency_key,
        )


def _check_subscription_access_verify_rate_limit(request) -> tuple[bool, int, int, str]:
    if not _verify_rate_limit_enabled():
        return True, 0, 0, request_ip_address(request) or "unknown"

    now_ts = int(timezone.now().timestamp())
    bucket = now_ts // 60
    retry_after = max(1, 60 - (now_ts % 60))
    client_ip = request_ip_address(request) or "unknown"

    cache_key = f"billing:subscription-access-verify:{client_ip}:{bucket}"
    if cache.add(cache_key, 1, timeout=120):
        count = 1
    else:
        try:
            count = int(cache.incr(cache_key))
        except Exception:
            cache.set(cache_key, 1, timeout=120)
            count = 1

    limit = _verify_rate_limit_per_minute()
    return count <= limit, retry_after, count, client_ip


def _check_onboarding_token_validate_rate_limit(request) -> tuple[bool, int, int, str]:
    if not _onboarding_token_validate_rate_limit_enabled():
        return True, 0, 0, request_ip_address(request) or "unknown"

    now_ts = int(timezone.now().timestamp())
    bucket = now_ts // 60
    retry_after = max(1, 60 - (now_ts % 60))
    client_ip = request_ip_address(request) or "unknown"

    cache_key = f"billing:onboarding-token-validate:{client_ip}:{bucket}"
    if cache.add(cache_key, 1, timeout=120):
        count = 1
    else:
        try:
            count = int(cache.incr(cache_key))
        except Exception:
            cache.set(cache_key, 1, timeout=120)
            count = 1

    limit = _onboarding_token_validate_rate_limit_per_minute()
    return count <= limit, retry_after, count, client_ip


def _check_checkout_confirm_rate_limit(
    request,
    *,
    provider: str,
    identifier: str,
) -> tuple[bool, int, int, str]:
    if not _checkout_confirm_rate_limit_enabled():
        return True, 0, 0, request_ip_address(request) or "unknown"

    now_ts = int(timezone.now().timestamp())
    bucket = now_ts // 60
    retry_after = max(1, 60 - (now_ts % 60))
    client_ip = request_ip_address(request) or "unknown"
    normalized_provider = str(provider or "unknown").strip().lower() or "unknown"
    normalized_identifier = str(identifier or "").strip()
    identifier_digest = hashlib.sha256(normalized_identifier.encode("utf-8")).hexdigest()[:16]

    cache_key = f"billing:checkout-confirm:{normalized_provider}:{identifier_digest}:{client_ip}:{bucket}"
    if cache.add(cache_key, 1, timeout=120):
        count = 1
    else:
        try:
            count = int(cache.incr(cache_key))
        except Exception:
            cache.set(cache_key, 1, timeout=120)
            count = 1

    limit = _checkout_confirm_rate_limit_per_minute()
    return count <= limit, retry_after, count, client_ip


def _audit_subscription_access_verify(
    *,
    request,
    reference: str,
    valid: bool,
    reason: str,
    rate_limited: bool = False,
    attempts_in_window: int | None = None,
    client_ip: str | None = None,
) -> None:
    request_user = getattr(request, "user", None)
    actor = request_user if getattr(request_user, "is_authenticated", False) else None

    log_event(
        action="other",
        entity_type="BillingSubscriptionAccess",
        entity_id=reference or "missing",
        changes={
            "event": "subscription_access_verify",
            "valid": valid,
            "reason": reason,
            "rate_limited": rate_limited,
            "attempts_in_window": attempts_in_window,
            "client_ip": client_ip,
        },
        request=request,
        user=actor,
    )


def _persist_sandbox_ticket(
    ticket: dict,
    *,
    registration_email: str | None = None,
    organization_id: str | None = None,
):
    normalized_email = str(registration_email or "").strip().lower()
    normalized_org_id = _normalized_organization_id(organization_id)
    consumed_at = timezone.now() if normalized_email else None
    subscription = BillingSubscription.objects.create(
        provider="sandbox",
        status="complete",
        payment_status="paid",
        plan_id=ticket["planId"],
        plan_name=ticket["planName"],
        billing_cycle=ticket["billingCycle"],
        payment_method=ticket["paymentMethod"],
        amount_usd=_to_decimal(ticket["amountUsd"]),
        reference=ticket["reference"],
        ticket_confirmed_at=_ms_to_datetime(ticket.get("confirmedAt")),
        ticket_expires_at=_ms_to_datetime(ticket.get("expiresAt")),
        registration_consumed_at=consumed_at,
        registration_consumed_by_email=normalized_email,
        metadata={"source": "sandbox_confirm"},
        raw_last_payload=ticket,
    )
    sync_onboarding_tokens_for_subscription(subscription)
    return subscription


def _persist_stripe_session(
    session_data: dict,
    *,
    checkout_url: str | None = None,
    organization_id: str | None = None,
):
    metadata = dict(session_data.get("metadata") or {})
    session_id = session_data.get("id")

    if not session_id:
        raise ValidationError("Stripe session payload missing id.")

    plan_id = metadata.get("plan_id") or ""
    plan_name = metadata.get("plan_name") or ""
    billing_cycle = metadata.get("billing_cycle") or "monthly"
    payment_method = metadata.get("payment_method") or "card"

    payment_status = session_data.get("payment_status") or ""
    status_value = session_data.get("status") or "open"
    if status_value not in {"open", "complete", "expired", "canceled", "failed"}:
        status_value = "open"

    amount_usd = _extract_amount_usd(session_data)

    reference = str(
        session_data.get("payment_intent")
        or session_data.get("id")
        or f"STRIPE-{uuid4().hex[:8].upper()}"
    )

    ticket_confirmed_at = None
    ticket_expires_at = None
    if status_value == "complete" and payment_status in {"paid", "no_payment_required"}:
        confirmed_ticket = _build_subscription_ticket(
            plan_id=plan_id,
            plan_name=plan_name,
            billing_cycle=billing_cycle,
            payment_method=payment_method,
            amount_usd=float(amount_usd),
            reference=reference,
        )
        ticket_confirmed_at = _ms_to_datetime(confirmed_ticket.get("confirmedAt"))
        ticket_expires_at = _ms_to_datetime(confirmed_ticket.get("expiresAt"))

    stripe_customer_id = session_data.get("customer")
    stripe_subscription_id = session_data.get("subscription")
    current_period_start = session_data.get("current_period_start")
    current_period_end = session_data.get("current_period_end")

    if stripe_customer_id:
        metadata["stripe_customer_id"] = stripe_customer_id
    if stripe_subscription_id:
        metadata["stripe_subscription_id"] = stripe_subscription_id
    if current_period_start:
        try:
            metadata["current_period_start"] = timezone.datetime.fromtimestamp(
                int(current_period_start), tz=dt_timezone.utc
            ).isoformat()
        except Exception:
            pass
    if current_period_end:
        try:
            metadata["current_period_end"] = timezone.datetime.fromtimestamp(
                int(current_period_end), tz=dt_timezone.utc
            ).isoformat()
        except Exception:
            pass

    metadata_org_id = _normalized_organization_id(metadata.get("organization_id"))
    resolved_org_id = _normalized_organization_id(organization_id) or metadata_org_id
    if resolved_org_id and not metadata_org_id:
        metadata["organization_id"] = resolved_org_id

    defaults = {
        "provider": "stripe",
        "payment_intent_id": _fit_model_field_value(
            BillingSubscription,
            "payment_intent_id",
            session_data.get("payment_intent"),
        ),
        "status": _fit_model_field_value(BillingSubscription, "status", status_value),
        "payment_status": _fit_model_field_value(BillingSubscription, "payment_status", payment_status),
        "plan_id": _fit_model_field_value(BillingSubscription, "plan_id", plan_id),
        "plan_name": _fit_model_field_value(BillingSubscription, "plan_name", plan_name),
        "billing_cycle": _fit_model_field_value(BillingSubscription, "billing_cycle", billing_cycle),
        "payment_method": _fit_model_field_value(BillingSubscription, "payment_method", payment_method),
        "amount_usd": amount_usd,
        "checkout_url": _fit_model_field_value(
            BillingSubscription,
            "checkout_url",
            checkout_url or session_data.get("url"),
        ),
        "reference": _fit_model_field_value(BillingSubscription, "reference", reference),
        "ticket_confirmed_at": ticket_confirmed_at,
        "ticket_expires_at": ticket_expires_at,
        "metadata": metadata,
        "raw_last_payload": session_data,
    }
    workspace_email = str(metadata.get("workspace_email") or "").strip().lower()
    if workspace_email:
        defaults["registration_consumed_at"] = timezone.now()
        defaults["registration_consumed_by_email"] = workspace_email

    subscription, _ = BillingSubscription.objects.update_or_create(
        session_id=session_id,
        defaults=defaults,
    )
    sync_onboarding_tokens_for_subscription(subscription)
    return subscription


def _persist_paystack_transaction(
    transaction_data: dict,
    *,
    checkout_url: str | None = None,
    organization_id: str | None = None,
):
    metadata = dict(transaction_data.get("metadata") or {})
    customer = dict(transaction_data.get("customer") or {})

    reference = str(
        transaction_data.get("reference")
        or transaction_data.get("id")
        or f"PAYSTACK-{uuid4().hex[:8].upper()}"
    ).strip()
    if not reference:
        raise ValidationError("Paystack transaction payload missing reference.")

    session_id = reference
    channel = str(transaction_data.get("channel") or metadata.get("payment_method") or "card").strip().lower()
    payment_method = _paystack_channel_to_payment_method(channel)
    payment_status_raw = str(transaction_data.get("status") or "").strip().lower()
    status_value = "complete" if payment_status_raw == "success" else "open"
    payment_status_value = "paid" if payment_status_raw == "success" else (
        payment_status_raw or "unpaid"
    )

    amount_minor = _to_decimal(transaction_data.get("amount"), fallback="0")
    amount_usd_from_metadata = _to_decimal(metadata.get("amount_usd"), fallback="0.00")
    if amount_usd_from_metadata > 0:
        amount_usd = amount_usd_from_metadata
    else:
        amount_usd = _paystack_amount_usd_from_minor(amount_minor)

    existing_subscription = (
        BillingSubscription.objects.filter(provider="paystack", session_id=session_id)
        .order_by("-created_at")
        .first()
    )
    if existing_subscription is not None:
        merged_metadata = dict(existing_subscription.metadata or {})
        merged_metadata.update(metadata)
        metadata = merged_metadata

    plan_id = str(metadata.get("plan_id") or "").strip() or str(getattr(existing_subscription, "plan_id", "") or "").strip()
    plan_name = str(metadata.get("plan_name") or "").strip() or str(getattr(existing_subscription, "plan_name", "") or "").strip()
    billing_cycle = (
        str(metadata.get("billing_cycle") or "").strip()
        or str(getattr(existing_subscription, "billing_cycle", "") or "").strip()
        or "monthly"
    )
    if amount_usd <= 0 and existing_subscription is not None:
        amount_usd = _to_decimal(existing_subscription.amount_usd, fallback="0.00")

    ticket_confirmed_at = None
    ticket_expires_at = None
    if status_value == "complete" and payment_status_value in {"paid", "no_payment_required"}:
        confirmed_ticket = _build_subscription_ticket(
            plan_id=plan_id,
            plan_name=plan_name,
            billing_cycle=billing_cycle,
            payment_method=payment_method,
            amount_usd=float(amount_usd),
            reference=reference,
        )
        ticket_confirmed_at = _ms_to_datetime(confirmed_ticket.get("confirmedAt"))
        ticket_expires_at = _ms_to_datetime(confirmed_ticket.get("expiresAt"))

    customer_email = str(customer.get("email") or metadata.get("workspace_email") or "").strip().lower()
    if customer_email:
        metadata["workspace_email"] = customer_email
    metadata["payment_channel"] = channel
    metadata["paystack_reference"] = reference
    if checkout_url:
        metadata["authorization_url"] = checkout_url
    metadata_org_id = _normalized_organization_id(metadata.get("organization_id"))
    resolved_org_id = _normalized_organization_id(organization_id) or metadata_org_id
    if resolved_org_id and not metadata_org_id:
        metadata["organization_id"] = resolved_org_id
    metadata["payment_method_summary"] = {
        "type": payment_method,
        "display": str(payment_method).replace("_", " ").title(),
        "brand": None,
        "last4": None,
        "exp_month": None,
        "exp_year": None,
    }

    authorization_payload = transaction_data.get("authorization")
    if not isinstance(authorization_payload, dict):
        authorization_payload = {}

    defaults = {
        "provider": "paystack",
        "payment_intent_id": _fit_model_field_value(
            BillingSubscription,
            "payment_intent_id",
            authorization_payload.get("authorization_code"),
        ),
        "status": _fit_model_field_value(BillingSubscription, "status", status_value),
        "payment_status": _fit_model_field_value(BillingSubscription, "payment_status", payment_status_value),
        "plan_id": _fit_model_field_value(BillingSubscription, "plan_id", plan_id),
        "plan_name": _fit_model_field_value(BillingSubscription, "plan_name", plan_name),
        "billing_cycle": _fit_model_field_value(BillingSubscription, "billing_cycle", billing_cycle),
        "payment_method": _fit_model_field_value(BillingSubscription, "payment_method", payment_method),
        "amount_usd": amount_usd,
        "checkout_url": _fit_model_field_value(
            BillingSubscription,
            "checkout_url",
            checkout_url
            or metadata.get("authorization_url")
            or getattr(existing_subscription, "checkout_url", "")
            or "",
        ),
        "reference": _fit_model_field_value(BillingSubscription, "reference", reference),
        "ticket_confirmed_at": ticket_confirmed_at,
        "ticket_expires_at": ticket_expires_at,
        "metadata": metadata,
        "raw_last_payload": transaction_data,
    }
    if customer_email:
        defaults["registration_consumed_at"] = timezone.now()
        defaults["registration_consumed_by_email"] = customer_email

    subscription, _ = BillingSubscription.objects.update_or_create(
        session_id=session_id,
        defaults=defaults,
    )
    sync_onboarding_tokens_for_subscription(subscription)
    return subscription


class SubscriptionConfirmAPIView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = SubscriptionConfirmSerializer

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        ticket = _build_subscription_ticket(
            plan_id=serializer.validated_data["plan_id"],
            plan_name=serializer.validated_data["plan_name"],
            billing_cycle=serializer.validated_data["billing_cycle"],
            payment_method=serializer.validated_data["payment_method"],
            amount_usd=float(serializer.validated_data["amount_usd"]),
            reference=f"OVS-{uuid4().hex[:8].upper()}",
        )

        request_user = getattr(request, "user", None)
        organization_id = _resolve_checkout_organization_id(request)
        workspace_email = str(getattr(request_user, "email", "") or "").strip().lower() or None

        # Billing tables are TENANT_APPS — switch to the org's schema before writing.
        from apps.tenants.models import Organization as _Organization  # noqa: PLC0415
        from django_tenants.utils import schema_context as _schema_context  # noqa: PLC0415
        organization = (
            _Organization.objects.filter(id=organization_id, is_active=True).first()
            if organization_id else None
        )
        if organization is None:
            raise ValidationError("Unable to resolve organization for this subscription confirmation.")

        with _schema_context(organization.schema_name):
            _persist_sandbox_ticket(
                ticket,
                registration_email=workspace_email,
                organization_id=organization_id,
            )

        return Response(
            {
                "status": "confirmed",
                "provider": "sandbox",
                "ticket": ticket,
            },
            status=status.HTTP_200_OK,
        )


class BillingHealthAPIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        request=None,
        responses={
            200: BillingHealthResponseSerializer,
            401: BillingActionErrorSerializer,
            403: BillingActionErrorSerializer,
        },
    )
    def get(self, request):
        if _billing_health_require_staff():
            if not bool(getattr(request.user, "is_authenticated", False)):
                return Response(
                    {"detail": "Authentication credentials were not provided."},
                    status=status.HTTP_401_UNAUTHORIZED,
                )

            if not bool(getattr(request.user, "is_staff", False)):
                return Response(
                    {"detail": "You do not have permission to perform this action."},
                    status=status.HTTP_403_FORBIDDEN,
                )

        return Response(
            {
                "status": "ok",
                "access": {
                    "staff_required": _billing_health_require_staff(),
                    "requester_is_staff": bool(getattr(request.user, "is_staff", False)),
                },
                "stripe": {
                    "sdk_installed": stripe is not None,
                    "secret_key_configured": bool(_stripe_secret_key()),
                    "webhook_secret_configured": bool(_stripe_webhook_secret()),
                },
                "paystack": {
                    "secret_key_configured": bool(_paystack_secret_key()),
                    "base_url": _paystack_base_url(),
                    "currency": _paystack_currency(),
                },
                "exchange_rate": _paystack_exchange_rate_health(),
                "subscription_verify_rate_limit": {
                    "enabled": _verify_rate_limit_enabled(),
                    "per_minute": _verify_rate_limit_per_minute(),
                },
            },
            status=status.HTTP_200_OK,
        )


class BillingExchangeRateAPIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        request=None,
        responses={
            200: BillingExchangeRateResponseSerializer,
        },
    )
    def get(self, request):
        target_currency = _paystack_currency()
        rate, source = _paystack_usd_exchange_rate_with_source()
        return Response(
            {
                "status": "ok",
                "base": "USD",
                "target": target_currency,
                "rate": float(rate),
                "source": source,
            },
            status=status.HTTP_200_OK,
        )


class BillingQuotaAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=None,
        responses={
            200: BillingQuotaResponseSerializer,
            401: BillingActionErrorSerializer,
        },
    )
    def get(self, request):
        snapshot = get_candidate_quota_snapshot(
            request.user,
            organization_id=_request_billing_organization_id(request),
        )
        return Response(
            {
                "status": "ok",
                "candidate": {
                    "enforced": snapshot.enforced,
                    "scope": snapshot.scope,
                    "reason": snapshot.reason,
                    "plan_id": snapshot.plan_id,
                    "plan_name": snapshot.plan_name,
                    "limit": snapshot.limit,
                    "used": snapshot.used,
                    "remaining": snapshot.remaining,
                    "period_start": snapshot.period_start,
                    "period_end": snapshot.period_end,
                },
            },
            status=status.HTTP_200_OK,
        )


def _serialize_subscription_management_payload(*, request, user) -> dict:
    active_subscription, latest_subscription = _scope_subscription_for_request_user(
        request=request,
        user=user,
    )
    target = active_subscription or latest_subscription
    if target is None:
        return {
            "status": "ok",
            "message": "No subscription record found for this workspace.",
            "subscription": None,
        }

    summary = _build_subscription_summary(target)
    return {"status": "ok", "subscription": summary}


def _schedule_subscription_end_of_period(subscription: BillingSubscription) -> dict:
    metadata = dict(subscription.metadata or {})
    now = timezone.now()

    if subscription.provider == "stripe":
        _ensure_stripe_ready()
        _, stripe_subscription_id = _hydrate_stripe_identifiers(subscription)
        if not stripe_subscription_id:
            raise ValidationError("Stripe subscription id is missing for this subscription.")

        stripe_subscription = dict(
            _stripe_modify_subscription(
                stripe_subscription_id,
                cancel_at_period_end=True,
            )
        )
        period_end_ts = stripe_subscription.get("current_period_end")
        period_start_ts = stripe_subscription.get("current_period_start")
        period_end = (
            timezone.datetime.fromtimestamp(int(period_end_ts), tz=dt_timezone.utc)
            if period_end_ts
            else None
        )
        period_start = (
            timezone.datetime.fromtimestamp(int(period_start_ts), tz=dt_timezone.utc)
            if period_start_ts
            else None
        )
    else:
        period_start, period_end = _subscription_period_bounds(subscription)
        if period_end is None:
            period_end = now + timedelta(days=30)

    metadata["cancel_at_period_end"] = True
    metadata["cancellation_requested_at"] = now.isoformat()
    metadata["cancellation_effective_at"] = period_end.isoformat() if period_end else None
    if period_start is not None:
        metadata["current_period_start"] = period_start.isoformat()
    if period_end is not None:
        metadata["current_period_end"] = period_end.isoformat()
    metadata.setdefault("cancellation_reason", "payment_method_removed")
    subscription.metadata = metadata
    subscription.save(update_fields=["metadata", "updated_at"])
    return _build_subscription_summary(subscription)


class BillingSubscriptionManageAPIView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = BillingPaymentMethodUpdateSerializer

    @extend_schema(
        request=None,
        responses={
            200: BillingSubscriptionManageResponseSerializer,
            401: BillingActionErrorSerializer,
        },
    )
    def get(self, request):
        payload = _serialize_subscription_management_payload(request=request, user=request.user)
        return Response(payload, status=status.HTTP_200_OK)

    @extend_schema(
        request=BillingPaymentMethodUpdateSerializer,
        responses={
            200: BillingSubscriptionManageResponseSerializer,
            400: BillingActionErrorSerializer,
            401: BillingActionErrorSerializer,
        },
    )
    def patch(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        active_subscription, _ = _scope_subscription_for_request_user(
            request=request,
            user=request.user,
        )
        if active_subscription is None:
            raise ValidationError("No active subscription available for this workspace.")
        if active_subscription.provider != "sandbox":
            raise ValidationError(
                "Direct payment method updates are supported only for sandbox provider. "
                "Use billing portal session for Stripe."
            )

        new_method = serializer.validated_data["payment_method"]
        active_subscription.payment_method = new_method
        metadata = dict(active_subscription.metadata or {})
        metadata["payment_method_summary"] = {
            "type": new_method,
            "display": str(new_method).replace("_", " ").title(),
            "brand": None,
            "last4": None,
            "exp_month": None,
            "exp_year": None,
        }
        active_subscription.metadata = metadata
        active_subscription.save(update_fields=["payment_method", "metadata", "updated_at"])

        return Response(
            {
                "status": "ok",
                "message": "Payment method updated.",
                "subscription": _build_subscription_summary(active_subscription),
            },
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        request=None,
        responses={
            200: BillingSubscriptionManageResponseSerializer,
            400: BillingActionErrorSerializer,
            401: BillingActionErrorSerializer,
        },
    )
    def delete(self, request):
        active_subscription, _ = _scope_subscription_for_request_user(
            request=request,
            user=request.user,
        )
        if active_subscription is None:
            raise ValidationError("No active subscription available for this workspace.")

        summary = _build_subscription_summary(active_subscription)
        if summary["cancel_at_period_end"]:
            return Response(
                {
                    "status": "ok",
                    "message": "Cancellation is already scheduled for end of current billing period.",
                    "subscription": summary,
                },
                status=status.HTTP_200_OK,
            )

        scheduled = _schedule_subscription_end_of_period(active_subscription)
        return Response(
            {
                "status": "ok",
                "message": "Payment option removed. Service remains active until end of current billing period.",
                "subscription": scheduled,
            },
            status=status.HTTP_200_OK,
        )


class BillingPaymentMethodUpdateSessionAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=None,
        responses={
            200: BillingPortalSessionResponseSerializer,
            400: BillingActionErrorSerializer,
            401: BillingActionErrorSerializer,
        },
    )
    def post(self, request):
        active_subscription, _ = _scope_subscription_for_request_user(
            request=request,
            user=request.user,
        )
        if active_subscription is None:
            raise ValidationError("No active subscription available for this workspace.")
        if active_subscription.provider != "stripe":
            raise ValidationError("Billing portal payment update is available only for Stripe subscriptions.")

        _ensure_stripe_ready()
        customer_id, _ = _hydrate_stripe_identifiers(active_subscription)
        if not customer_id:
            raise ValidationError("Stripe customer id is missing for this subscription.")

        return_url = str(
            getattr(settings, "STRIPE_BILLING_PORTAL_RETURN_URL", "")
            or f"{getattr(settings, 'FRONTEND_URL', 'http://localhost:3000').rstrip('/')}/settings"
        )
        try:
            session = _stripe_create_billing_portal_session(
                customer=customer_id,
                return_url=return_url,
                flow_data={"type": "payment_method_update"},
            )
        except Exception as exc:
            raise ValidationError(f"Unable to start Stripe billing portal session: {exc}") from exc

        session_dict = session._to_dict_recursive() if hasattr(session, "_to_dict_recursive") else dict(session)
        return Response(
            {
                "status": "ok",
                "provider": "stripe",
                "url": session_dict.get("url"),
            },
            status=status.HTTP_200_OK,
        )


class BillingSubscriptionRetryAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=None,
        responses={
            200: BillingSubscriptionRetryResponseSerializer,
            400: BillingActionErrorSerializer,
            401: BillingActionErrorSerializer,
        },
    )
    def post(self, request):
        active_subscription, latest_subscription = _scope_subscription_for_request_user(
            request=request,
            user=request.user,
        )
        candidate = latest_subscription or active_subscription
        if candidate is None:
            raise ValidationError("No subscription record found to retry.")

        summary = _build_subscription_summary(candidate)
        if not summary["retry_available"]:
            raise ValidationError("Current subscription does not require a retry.")

        if candidate.provider == "stripe":
            _ensure_stripe_ready()
            amount_usd = _to_decimal(candidate.amount_usd)
            amount_cents = int((amount_usd * Decimal("100")).quantize(Decimal("1")))
            billing_cycle = candidate.billing_cycle or "monthly"
            interval = "month" if billing_cycle == "monthly" else "year"
            success_url = _ensure_checkout_placeholder(_default_success_url())
            cancel_url = _default_cancel_url()
            metadata = {
                "plan_id": candidate.plan_id,
                "plan_name": candidate.plan_name,
                "billing_cycle": billing_cycle,
                "payment_method": "card",
                "amount_usd": f"{amount_usd:.2f}",
                "retry_of_subscription_id": str(candidate.id),
                "workspace_email": str(getattr(request.user, "email", "") or "").strip().lower(),
            }
            retry_org_id = (
                _normalized_organization_id(getattr(candidate, "organization_id", None))
                or _request_billing_organization_id(request)
            )
            if retry_org_id:
                metadata["organization_id"] = retry_org_id

            try:
                session = _stripe_create_checkout_session(
                    mode="subscription",
                    success_url=success_url,
                    cancel_url=cancel_url,
                    line_items=[
                        {
                            "price_data": {
                                "currency": "usd",
                                "unit_amount": amount_cents,
                                "recurring": {"interval": interval},
                                "product_data": {
                                    "name": f"OVS {candidate.plan_name} ({billing_cycle})",
                                    "metadata": metadata,
                                },
                            },
                            "quantity": 1,
                        }
                    ],
                    metadata=metadata,
                    subscription_data={"metadata": metadata},
                )
            except Exception as exc:
                raise ValidationError(f"Unable to start Stripe retry checkout session: {exc}") from exc

            session_dict = session._to_dict_recursive()
            _persist_stripe_session(
                session_dict,
                checkout_url=session_dict.get("url"),
                organization_id=_request_billing_organization_id(request),
            )
            return Response(
                {
                    "status": "ok",
                    "provider": "stripe",
                    "message": "Retry checkout session created.",
                    "session_id": session_dict.get("id"),
                    "checkout_url": session_dict.get("url"),
                },
                status=status.HTTP_200_OK,
            )

        if candidate.provider == "paystack":
            _ensure_paystack_ready()
            amount_usd = _to_decimal(candidate.amount_usd)
            amount_minor = _paystack_amount_minor_from_usd(amount_usd)
            reference = f"OVS-PAYSTACK-RETRY-{uuid4().hex[:10].upper()}"
            workspace_email = str(getattr(request.user, "email", "") or "").strip().lower()
            if not workspace_email:
                raise ValidationError("A workspace email is required to retry Paystack checkout.")
            success_url = _default_success_url_no_provider_marker()
            cancel_url = _default_cancel_url()
            requested_payment_method = str(candidate.payment_method or "card").strip().lower()
            if requested_payment_method not in {"card", "bank_transfer", "mobile_money"}:
                requested_payment_method = "card"

            metadata = {
                "plan_id": candidate.plan_id,
                "plan_name": candidate.plan_name,
                "billing_cycle": candidate.billing_cycle or "monthly",
                "payment_method": requested_payment_method,
                "amount_usd": f"{amount_usd:.2f}",
                "retry_of_subscription_id": str(candidate.id),
                "workspace_email": workspace_email,
                "cancel_url": cancel_url,
            }
            retry_org_id = (
                _normalized_organization_id(getattr(candidate, "organization_id", None))
                or _request_billing_organization_id(request)
            )
            if retry_org_id:
                metadata["organization_id"] = retry_org_id

            initialize_payload = {
                "email": workspace_email,
                "amount": amount_minor,
                "currency": _paystack_currency(),
                "callback_url": success_url,
                "reference": reference,
                "metadata": metadata,
            }
            channels = _paystack_channels_for_requested_method(requested_payment_method)
            if channels:
                initialize_payload["channels"] = channels
            initialize_response = _paystack_initialize_transaction(initialize_payload)
            checkout_url = initialize_response.get("authorization_url")
            if not checkout_url:
                raise ValidationError("Paystack retry checkout missing authorization_url.")

            _persist_paystack_transaction(
                {
                    "reference": initialize_response.get("reference") or reference,
                    "status": "pending",
                    "amount": amount_minor,
                    "channel": requested_payment_method,
                    "metadata": metadata,
                    "customer": {"email": workspace_email},
                },
                checkout_url=checkout_url,
                organization_id=retry_org_id,
            )

            return Response(
                {
                    "status": "ok",
                    "provider": "paystack",
                    "message": "Retry checkout session created.",
                    "session_id": initialize_response.get("reference") or reference,
                    "checkout_url": checkout_url,
                },
                status=status.HTTP_200_OK,
            )

        ticket = _build_subscription_ticket(
            plan_id=candidate.plan_id,
            plan_name=candidate.plan_name,
            billing_cycle=candidate.billing_cycle,
            payment_method=candidate.payment_method,
            amount_usd=float(candidate.amount_usd),
            reference=f"OVS-RETRY-{uuid4().hex[:8].upper()}",
        )
        _persist_sandbox_ticket(
            ticket,
            registration_email=str(getattr(request.user, "email", "") or "").strip().lower(),
            organization_id=_request_billing_organization_id(request),
        )
        return Response(
            {
                "status": "ok",
                "provider": "sandbox",
                "message": "Sandbox subscription retry confirmed.",
            },
            status=status.HTTP_200_OK,
        )


class OrganizationOnboardingTokenStateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=None,
        responses={
            200: OrganizationOnboardingTokenStateResponseSerializer,
            400: BillingActionErrorSerializer,
            401: BillingActionErrorSerializer,
            403: BillingActionErrorSerializer,
        },
    )
    def get(self, request):
        organization = _resolve_onboarding_management_organization(request)
        active_subscription = get_active_subscription_for_organization(organization_id=str(organization.id))
        token_record = get_active_onboarding_token_for_organization(organization_id=str(organization.id))
        seat_snapshot = get_organization_seat_quota_snapshot(
            organization_id=str(organization.id),
            subscription=active_subscription,
        )
        return Response(
            {
                "status": "ok",
                "organization_id": organization.id,
                "organization_name": organization.name,
                "subscription_id": active_subscription.id if active_subscription else None,
                "subscription_active": bool(active_subscription is not None),
                "has_active_token": bool(token_record is not None),
                "token": _serialize_onboarding_token_state(token_record),
                "organization_seat_limit": seat_snapshot.limit,
                "organization_seat_used": seat_snapshot.used,
                "organization_seat_remaining": seat_snapshot.remaining,
            },
            status=status.HTTP_200_OK,
        )


class OrganizationOnboardingTokenGenerateAPIView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = OrganizationOnboardingTokenGenerateSerializer

    @extend_schema(
        request=OrganizationOnboardingTokenGenerateSerializer,
        responses={
            200: OrganizationOnboardingTokenGenerateResponseSerializer,
            400: BillingActionErrorSerializer,
            401: BillingActionErrorSerializer,
            403: BillingActionErrorSerializer,
        },
    )
    @transaction.atomic
    def post(self, request):
        organization = _resolve_onboarding_management_organization(request)

        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        active_subscription = get_active_subscription_for_organization(organization_id=str(organization.id))
        if active_subscription is None:
            raise ValidationError("Active organization subscription is required before generating onboarding tokens.")

        expires_in_hours = serializer.validated_data.get("expires_in_hours")
        expires_at = None
        if expires_in_hours is not None:
            expires_at = timezone.now() + timedelta(hours=int(expires_in_hours))

        token_record, raw_token = create_organization_onboarding_token(
            organization=organization,
            subscription=active_subscription,
            created_by=request.user,
            expires_at=expires_at,
            max_uses=serializer.validated_data.get("max_uses"),
            allowed_email_domain=serializer.validated_data.get("allowed_email_domain", ""),
            rotate=bool(serializer.validated_data.get("rotate", True)),
            metadata={
                "issued_via": "billing_api",
            },
        )

        log_event(
            request=request,
            action="update",
            entity_type="OrganizationOnboardingToken",
            entity_id=str(token_record.id),
            changes={
                "event": "organization_onboarding_token_generated",
                "organization_id": str(organization.id),
                "subscription_id": str(active_subscription.id),
                "token_preview": token_record.token_prefix,
                "max_uses": token_record.max_uses,
                "expires_at": token_record.expires_at.isoformat() if token_record.expires_at else None,
                "allowed_email_domain": token_record.allowed_email_domain,
                "rotate": bool(serializer.validated_data.get("rotate", True)),
            },
        )

        return Response(
            {
                "status": "ok",
                "organization_id": organization.id,
                "organization_name": organization.name,
                "token": raw_token,
                "onboarding_link": build_onboarding_link(raw_token),
                "token_state": _serialize_onboarding_token_state(token_record),
            },
            status=status.HTTP_200_OK,
        )


class OrganizationOnboardingTokenRevokeAPIView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = OrganizationOnboardingTokenRevokeSerializer

    @extend_schema(
        request=OrganizationOnboardingTokenRevokeSerializer,
        responses={
            200: OrganizationOnboardingTokenStateResponseSerializer,
            400: BillingActionErrorSerializer,
            401: BillingActionErrorSerializer,
            403: BillingActionErrorSerializer,
        },
    )
    @transaction.atomic
    def post(self, request):
        organization = _resolve_onboarding_management_organization(request)
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        reason = str(serializer.validated_data.get("reason", "") or "").strip() or "manual_revocation"
        deactivated = deactivate_active_onboarding_tokens(
            organization_id=str(organization.id),
            reason=reason,
            revoked_by=request.user,
            when=timezone.now(),
        )
        token_record = get_active_onboarding_token_for_organization(organization_id=str(organization.id))
        active_subscription = get_active_subscription_for_organization(organization_id=str(organization.id))

        log_event(
            request=request,
            action="update",
            entity_type="OrganizationOnboardingToken",
            entity_id=str(organization.id),
            changes={
                "event": "organization_onboarding_token_revoked",
                "organization_id": str(organization.id),
                "revoked_count": int(deactivated),
                "reason": reason,
            },
        )

        return Response(
            {
                "status": "ok",
                "organization_id": organization.id,
                "organization_name": organization.name,
                "subscription_id": active_subscription.id if active_subscription else None,
                "subscription_active": bool(active_subscription is not None),
                "has_active_token": bool(token_record is not None),
                "token": _serialize_onboarding_token_state(token_record),
            },
            status=status.HTTP_200_OK,
        )


class OrganizationOnboardingTokenSendInviteAPIView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = OrganizationOnboardingTokenSendInviteSerializer

    @extend_schema(
        request=OrganizationOnboardingTokenSendInviteSerializer,
        responses={
            200: OrganizationOnboardingTokenSendInviteResponseSerializer,
            400: BillingActionErrorSerializer,
            401: BillingActionErrorSerializer,
            403: BillingActionErrorSerializer,
        },
    )
    @transaction.atomic
    def post(self, request):
        organization = _resolve_onboarding_management_organization(request)

        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        active_subscription = get_active_subscription_for_organization(organization_id=str(organization.id))
        if active_subscription is None:
            raise ValidationError("Active organization subscription is required before sending onboarding invites.")

        recipient_emails: list = serializer.validated_data["recipient_emails"]
        expires_in_hours = serializer.validated_data.get("expires_in_hours")
        expires_at = None
        if expires_in_hours is not None:
            expires_at = timezone.now() + timedelta(hours=int(expires_in_hours))

        # Generate a single token shared across all recipients — the link is the same for all.
        token_record, raw_token = create_organization_onboarding_token(
            organization=organization,
            subscription=active_subscription,
            created_by=request.user,
            expires_at=expires_at,
            max_uses=serializer.validated_data.get("max_uses"),
            allowed_email_domain=serializer.validated_data.get("allowed_email_domain", ""),
            rotate=bool(serializer.validated_data.get("rotate", True)),
            metadata={"issued_via": "email_invite", "recipient_emails": recipient_emails},
        )

        onboarding_link = build_onboarding_link(raw_token)
        invited_by = str(getattr(request.user, "get_full_name", lambda: "")() or "").strip()
        if not invited_by:
            invited_by = str(getattr(request.user, "email", "") or organization.name)

        sent: list[str] = []
        failed: list[str] = []
        for email in recipient_emails:
            try:
                _send_onboarding_invite_email(
                    recipient_email=email,
                    organization_name=organization.name,
                    onboarding_link=onboarding_link,
                    invited_by=invited_by,
                    expires_at=token_record.expires_at,
                    allowed_email_domain=token_record.allowed_email_domain,
                )
                sent.append(email)
            except Exception:
                failed.append(email)

        log_event(
            request=request,
            action="update",
            entity_type="OrganizationOnboardingToken",
            entity_id=str(token_record.id),
            changes={
                "event": "organization_onboarding_invite_sent",
                "organization_id": str(organization.id),
                "subscription_id": str(active_subscription.id),
                "token_preview": token_record.token_prefix,
                "sent": sent,
                "failed": failed,
                "max_uses": token_record.max_uses,
                "expires_at": token_record.expires_at.isoformat() if token_record.expires_at else None,
                "allowed_email_domain": token_record.allowed_email_domain,
            },
        )

        return Response(
            {
                "status": "ok",
                "sent": sent,
                "failed": failed,
                "organization_name": organization.name,
                "token_state": _serialize_onboarding_token_state(token_record),
            },
            status=status.HTTP_200_OK,
        )


class OrganizationOnboardingTokenValidateAPIView(APIView):
    permission_classes = [AllowAny]
    serializer_class = OrganizationOnboardingTokenValidateSerializer

    @extend_schema(
        request=OrganizationOnboardingTokenValidateSerializer,
        responses={
            200: OrganizationOnboardingTokenValidateResponseSerializer,
            400: BillingActionErrorSerializer,
        },
    )
    def post(self, request):
        allowed, retry_after, _count, _client_ip = _check_onboarding_token_validate_rate_limit(request)
        if not allowed:
            response = Response(
                {
                    "detail": "Rate limit exceeded for onboarding token validation. Please retry shortly.",
                    "code": "RATE_LIMITED",
                },
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
            response["Retry-After"] = str(retry_after)
            return response

        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        validation_result = validate_organization_onboarding_token(
            raw_token=serializer.validated_data["token"],
            email=serializer.validated_data.get("email", ""),
            consume=False,
        )
        payload = _onboarding_token_validation_payload(validation_result=validation_result)
        return Response(payload, status=status.HTTP_200_OK)


class SubscriptionAccessVerifyAPIView(APIView):
    permission_classes = [AllowAny]
    serializer_class = SubscriptionAccessVerifySerializer

    def post(self, request):
        allowed, retry_after, count, client_ip = _check_subscription_access_verify_rate_limit(request)
        if not allowed:
            reference = str(request.data.get("reference", "") or "")
            _audit_subscription_access_verify(
                request=request,
                reference=reference,
                valid=False,
                reason="rate_limited",
                rate_limited=True,
                attempts_in_window=count,
                client_ip=client_ip,
            )
            response = Response(
                {
                    "detail": "Rate limit exceeded for subscription verification. Please retry shortly.",
                },
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
            response["Retry-After"] = str(retry_after)
            return response

        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        reference = serializer.validated_data["reference"]
        org_id = _normalized_organization_id(serializer.validated_data.get("organization_id"))

        # Billing tables are TENANT_APPS — switch to the org's schema before querying.
        from django_tenants.utils import schema_context as _schema_context  # noqa: PLC0415
        organization = _resolve_billing_schema_organization(org_id)
        if organization is None:
            _audit_subscription_access_verify(
                request=request,
                reference=reference,
                valid=False,
                reason="no_tenant_context",
                rate_limited=False,
                attempts_in_window=count,
                client_ip=client_ip,
            )
            return Response(
                {"valid": False, "reason": "no_tenant_context", "reference": reference},
                status=status.HTTP_200_OK,
            )

        with _schema_context(organization.schema_name):
            valid, reason, subscription = _resolve_subscription_access_state(reference)

            payload = {
                "valid": valid,
                "reason": reason,
                "reference": reference,
            }

            if subscription is not None:
                payload.update(
                    {
                        "planId": subscription.plan_id,
                        "planName": subscription.plan_name,
                        "billingCycle": subscription.billing_cycle,
                        "paymentMethod": subscription.payment_method,
                        "amountUsd": float(subscription.amount_usd),
                        "confirmedAt": _datetime_to_ms(subscription.ticket_confirmed_at),
                        "expiresAt": _datetime_to_ms(subscription.ticket_expires_at),
                        "status": subscription.status,
                        "paymentStatus": subscription.payment_status,
                        "registrationConsumedAt": _datetime_to_ms(subscription.registration_consumed_at),
                    }
                )

            _audit_subscription_access_verify(
                request=request,
                reference=reference,
                valid=valid,
                reason=reason,
                rate_limited=False,
                attempts_in_window=count,
                client_ip=client_ip,
            )

        return Response(payload, status=status.HTTP_200_OK)


class StripeCheckoutSessionCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = StripeCheckoutSessionCreateSerializer

    def post(self, request):
        organization_id = _resolve_checkout_organization_id(request)
        _ensure_stripe_ready()

        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        amount_usd = serializer.validated_data["amount_usd"]
        amount_cents = int((amount_usd * Decimal("100")).quantize(Decimal("1")))

        billing_cycle = serializer.validated_data["billing_cycle"]
        interval = "month" if billing_cycle == "monthly" else "year"

        success_url = _ensure_checkout_placeholder(
            serializer.validated_data.get("success_url") or _default_success_url()
        )
        cancel_url = serializer.validated_data.get("cancel_url") or _default_cancel_url()

        metadata = {
            "plan_id": serializer.validated_data["plan_id"],
            "plan_name": serializer.validated_data["plan_name"],
            "billing_cycle": billing_cycle,
            "payment_method": "card",
            "amount_usd": f"{amount_usd:.2f}",
        }
        metadata["organization_id"] = organization_id

        request_user = getattr(request, "user", None)
        workspace_email = str(getattr(request_user, "email", "") or "").strip().lower()
        if workspace_email:
            metadata["workspace_email"] = workspace_email

        try:
            session = _stripe_create_checkout_session(
                mode="subscription",
                success_url=success_url,
                cancel_url=cancel_url,
                line_items=[
                    {
                        "price_data": {
                            "currency": "usd",
                            "unit_amount": amount_cents,
                            "recurring": {"interval": interval},
                            "product_data": {
                                "name": f"OVS {serializer.validated_data['plan_name']} ({billing_cycle})",
                                "metadata": metadata,
                            },
                        },
                        "quantity": 1,
                    }
                ],
                metadata=metadata,
                subscription_data={"metadata": metadata},
            )
        except Exception as exc:
            raise ValidationError(f"Unable to create Stripe checkout session: {exc}") from exc

        session_dict = session._to_dict_recursive() if hasattr(session, "_to_dict_recursive") else dict(session)
        _persist_stripe_session(
            session_dict,
            checkout_url=session_dict.get("url"),
            organization_id=organization_id,
        )

        return Response(
            {
                "provider": "stripe",
                "session_id": session_dict.get("id"),
                "checkout_url": session_dict.get("url"),
            },
            status=status.HTTP_200_OK,
        )


class StripeCheckoutSessionConfirmAPIView(APIView):
    permission_classes = [AllowAny]
    serializer_class = StripeCheckoutSessionConfirmSerializer

    @extend_schema(
        request=StripeCheckoutSessionConfirmSerializer,
        responses={
            200: StripeCheckoutSessionConfirmResponseSerializer,
            400: BillingActionErrorSerializer,
            429: CheckoutConfirmErrorSerializer,
        },
    )
    def post(self, request):
        _ensure_stripe_ready()

        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        session_id = serializer.validated_data["session_id"]
        allowed, retry_after, _count, _client_ip = _check_checkout_confirm_rate_limit(
            request,
            provider="stripe",
            identifier=session_id,
        )
        if not allowed:
            response = Response(
                {
                    "detail": "Rate limit exceeded for checkout confirmation. Please retry shortly.",
                    "code": "RATE_LIMITED",
                },
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
            response["Retry-After"] = str(retry_after)
            return response

        try:
            session = _stripe_retrieve_checkout_session(session_id)
        except Exception as exc:
            raise ValidationError(f"Unable to retrieve Stripe session: {exc}") from exc

        session_payload = session._to_dict_recursive() if hasattr(session, "_to_dict_recursive") else dict(session)
        session_status = session_payload.get("status")
        payment_status = session_payload.get("payment_status")
        if session_status != "complete" or payment_status not in {"paid", "no_payment_required"}:
            raise ValidationError("Stripe checkout session is not fully paid yet.")

        # Billing tables are TENANT_APPS — resolve the tenant from the organization_id
        # embedded in the session metadata before any ORM calls.
        session_metadata = dict(session_payload.get("metadata") or {})
        org_id = _normalized_organization_id(session_metadata.get("organization_id"))
        from django_tenants.utils import schema_context as _schema_context  # noqa: PLC0415
        organization = _resolve_billing_schema_organization(org_id)
        if organization is None:
            raise ValidationError("Unable to resolve organization for this Stripe session.")

        with _schema_context(organization.schema_name):
            subscription = _persist_stripe_session(session_payload)
            ticket = _build_subscription_ticket(
                plan_id=subscription.plan_id,
                plan_name=subscription.plan_name,
                billing_cycle=subscription.billing_cycle,
                payment_method=subscription.payment_method,
                amount_usd=float(subscription.amount_usd),
                reference=subscription.reference,
            )

        return Response(
            {
                "status": "confirmed",
                "provider": "stripe",
                "stripe_session_id": session_payload.get("id"),
                "ticket": ticket,
            },
            status=status.HTTP_200_OK,
        )


class PaystackCheckoutSessionCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = PaystackCheckoutSessionCreateSerializer

    def post(self, request):
        organization_id = _resolve_checkout_organization_id(request)
        _ensure_paystack_ready()

        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        request_user = getattr(request, "user", None)
        workspace_email = str(getattr(request_user, "email", "") or "").strip().lower()

        customer_email = workspace_email or str(
            serializer.validated_data.get("customer_email") or ""
        ).strip().lower()
        if not customer_email:
            raise ValidationError("Customer email is required for Paystack checkout.")

        amount_usd = serializer.validated_data["amount_usd"]
        amount_minor = _paystack_amount_minor_from_usd(amount_usd)
        success_url = serializer.validated_data.get("success_url") or _default_success_url_no_provider_marker()
        cancel_url = serializer.validated_data.get("cancel_url") or _default_cancel_url()
        reference = f"OVS-PAYSTACK-{uuid4().hex[:12].upper()}"
        requested_payment_method = serializer.validated_data.get("payment_method") or "card"

        metadata = {
            "plan_id": serializer.validated_data["plan_id"],
            "plan_name": serializer.validated_data["plan_name"],
            "billing_cycle": serializer.validated_data["billing_cycle"],
            "payment_method": requested_payment_method,
            "amount_usd": f"{amount_usd:.2f}",
            "workspace_email": workspace_email,
            "cancel_url": cancel_url,
        }
        metadata["organization_id"] = organization_id

        payload = {
            "email": customer_email,
            "amount": amount_minor,
            "currency": _paystack_currency(),
            "callback_url": success_url,
            "reference": reference,
            "metadata": metadata,
        }
        channels = _paystack_channels_for_requested_method(requested_payment_method)
        if channels:
            payload["channels"] = channels

        session_data = _paystack_initialize_transaction(payload)
        checkout_url = session_data.get("authorization_url")
        if not checkout_url:
            raise ValidationError("Paystack initialize response missing authorization_url.")

        _persist_paystack_transaction(
            {
                "reference": session_data.get("reference") or reference,
                "status": "pending",
                "amount": amount_minor,
                "channel": requested_payment_method,
                "metadata": metadata,
                "customer": {"email": customer_email},
            },
            checkout_url=checkout_url,
            organization_id=organization_id,
        )

        return Response(
            {
                "provider": "paystack",
                "reference": session_data.get("reference") or reference,
                "checkout_url": checkout_url,
            },
            status=status.HTTP_200_OK,
        )


class PaystackCheckoutSessionConfirmAPIView(APIView):
    permission_classes = [AllowAny]
    serializer_class = PaystackCheckoutSessionConfirmSerializer

    @extend_schema(
        request=PaystackCheckoutSessionConfirmSerializer,
        responses={
            200: PaystackCheckoutSessionConfirmResponseSerializer,
            400: CheckoutConfirmErrorSerializer,
            429: CheckoutConfirmErrorSerializer,
        },
    )
    def post(self, request):
        _ensure_paystack_ready()

        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        reference = serializer.validated_data["reference"]
        allowed, retry_after, _count, _client_ip = _check_checkout_confirm_rate_limit(
            request,
            provider="paystack",
            identifier=reference,
        )
        if not allowed:
            response = Response(
                {
                    "detail": "Rate limit exceeded for checkout confirmation. Please retry shortly.",
                    "code": "RATE_LIMITED",
                },
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
            response["Retry-After"] = str(retry_after)
            return response

        # Verify the transaction first (no DB — HTTP call to Paystack) so we can
        # extract the organization_id that was embedded in the metadata at checkout
        # initiation time.  We need it to switch to the correct tenant schema before
        # any billing ORM calls.
        transaction_data = _paystack_verify_transaction(reference)
        tx_metadata = dict(transaction_data.get("metadata") or {})
        org_id = _normalized_organization_id(tx_metadata.get("organization_id"))
        from django_tenants.utils import schema_context as _schema_context  # noqa: PLC0415
        organization = _resolve_billing_schema_organization(org_id)
        if organization is None:
            raise ValidationError("Unable to resolve organization for this Paystack transaction.")

        with _schema_context(organization.schema_name):
            subscription = _persist_paystack_transaction(transaction_data)
            transaction_status = str(transaction_data.get("status") or "").strip().lower()
            if transaction_status != "success":
                gateway_response = str(transaction_data.get("gateway_response") or "").strip()
                detail = f"Paystack transaction is not successful yet (status: {transaction_status or 'unknown'})."
                if gateway_response:
                    detail = f"{detail} Gateway response: {gateway_response}"
                raise ValidationError(
                    {
                        "detail": detail,
                        "status": transaction_status or "unknown",
                        "reference": reference,
                        "checkout_url": subscription.checkout_url,
                    }
                )

            ticket = _build_subscription_ticket(
                plan_id=subscription.plan_id,
                plan_name=subscription.plan_name,
                billing_cycle=subscription.billing_cycle,
                payment_method=subscription.payment_method,
                amount_usd=float(subscription.amount_usd),
                reference=subscription.reference,
            )

        return Response(
            {
                "status": "confirmed",
                "provider": "paystack",
                "paystack_reference": reference,
                "ticket": ticket,
            },
            status=status.HTTP_200_OK,
        )


class PaystackWebhookAPIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        request=None,
        responses={
            200: BillingWebhookResponseSerializer,
            400: BillingActionErrorSerializer,
        },
    )
    def post(self, request):
        _ensure_paystack_ready()

        signature = request.headers.get("X-Paystack-Signature", "")
        if not signature:
            raise ValidationError("Missing X-Paystack-Signature header.")

        payload = request.body
        if not _is_valid_paystack_signature(payload, signature):
            raise ValidationError("Invalid Paystack webhook signature.")

        try:
            event = json.loads(payload.decode("utf-8") or "{}")
        except Exception as exc:
            raise ValidationError(f"Invalid Paystack webhook payload: {exc}") from exc

        event_id = str(event.get("id") or "")
        event_type = str(event.get("event") or "").strip()
        event_data = dict(event.get("data") or {})

        # Billing tables are TENANT_APPS — they only exist in tenant schemas, not the
        # public schema that handles this webhook endpoint.  Resolve the target tenant
        # from the organization_id embedded in the transaction metadata at checkout
        # initiation time, then switch the DB search_path before any ORM operations.
        event_metadata = dict(event_data.get("metadata") or {})
        org_id = _normalized_organization_id(event_metadata.get("organization_id"))
        from django_tenants.utils import schema_context as _schema_context  # noqa: PLC0415
        organization = _resolve_billing_schema_organization(org_id)
        if organization is None:
            # Acknowledge receipt but take no DB action — we have no tenant to write to.
            return Response(
                {"received": True, "event_type": event_type, "detail": "no_tenant_context"},
                status=status.HTTP_200_OK,
            )

        with _schema_context(organization.schema_name):
            return self._process_paystack_event(event, event_id, event_type, event_data, signature)

    @transaction.atomic
    def _process_paystack_event(self, event, event_id, event_type, event_data, signature):
        if event_id:
            webhook_event, _ = BillingWebhookEvent.objects.get_or_create(
                provider="paystack",
                event_id=event_id,
                defaults={
                    "event_type": event_type,
                    "signature": signature,
                    "payload": event,
                    "livemode": bool(event.get("livemode", False)),
                    "processing_status": "received",
                },
            )
            webhook_event.event_type = event_type
            webhook_event.signature = signature
            webhook_event.payload = event
            webhook_event.livemode = bool(event.get("livemode", False))
            webhook_event.processing_status = "received"
            webhook_event.processing_error = ""
            webhook_event.save(
                update_fields=[
                    "event_type",
                    "signature",
                    "payload",
                    "livemode",
                    "processing_status",
                    "processing_error",
                ]
            )
        else:
            webhook_event = BillingWebhookEvent.objects.create(
                provider="paystack",
                event_type=event_type,
                signature=signature,
                payload=event,
                livemode=bool(event.get("livemode", False)),
                processing_status="received",
            )

        response_payload = {
            "received": True,
            "event_type": event_type,
        }

        try:
            if event_type == "charge.success":
                subscription = _persist_paystack_transaction(event_data)
                response_payload["session_id"] = subscription.session_id
                response_payload["payment_status"] = subscription.payment_status
                webhook_event.processing_status = "processed"
            elif event_type in {"charge.failed", "charge.reversed", "charge.dispute.create"}:
                reference = str(event_data.get("reference") or "").strip()
                subscription = _find_subscription_by_paystack_reference(reference)
                if subscription is not None:
                    metadata = dict(subscription.metadata or {})
                    metadata["last_payment_failure_at"] = timezone.now().isoformat()
                    metadata["last_payment_failure_event"] = event_type
                    subscription.status = "failed"
                    subscription.payment_status = "unpaid"
                    subscription.metadata = metadata
                    subscription.raw_last_payload = event_data
                    subscription.save(
                        update_fields=["status", "payment_status", "metadata", "raw_last_payload", "updated_at"]
                    )
                    sync_onboarding_tokens_for_subscription(subscription)
                    response_payload["session_id"] = subscription.session_id
                    response_payload["payment_status"] = subscription.payment_status
                _notify_billing_payment_failure(
                    provider="paystack",
                    billing_event_type=event_type,
                    subscription=subscription,
                    reference=reference,
                )
                webhook_event.processing_status = "processed"
            else:
                webhook_event.processing_status = "ignored"

            webhook_event.processed_at = timezone.now()
            webhook_event.save(update_fields=["processing_status", "processed_at"])
        except Exception as exc:
            webhook_event.processing_status = "failed"
            webhook_event.processing_error = str(exc)
            webhook_event.processed_at = timezone.now()
            webhook_event.save(update_fields=["processing_status", "processing_error", "processed_at"])
            _notify_billing_processing_error(
                provider="paystack",
                webhook_event=webhook_event,
                billing_event_type=event_type,
                error_message=str(exc),
            )
            return Response(
                {
                    "received": True,
                    "event_type": event_type,
                    "detail": str(exc),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(response_payload, status=status.HTTP_200_OK)


class StripeWebhookAPIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        request=None,
        responses={
            200: BillingWebhookResponseSerializer,
            400: BillingActionErrorSerializer,
        },
    )
    def post(self, request):
        _ensure_stripe_webhook_ready()

        signature = request.headers.get("Stripe-Signature", "")
        if not signature:
            raise ValidationError("Missing Stripe-Signature header.")

        payload = request.body
        try:
            event_obj = _stripe_construct_event(payload=payload, sig_header=signature)
        except Exception as exc:
            raise ValidationError(f"Invalid Stripe webhook signature: {exc}") from exc

        # Convert the StripeObject to a plain dict immediately — StripeObject v14 does not
        # inherit from dict, so .get() and other dict methods are unavailable on the raw object.
        event = event_obj._to_dict_recursive() if hasattr(event_obj, "_to_dict_recursive") else dict(event_obj)

        event_type = event.get("type", "")
        event_data = dict((event.get("data") or {}).get("object") or {})

        # Billing tables are TENANT_APPS — resolve the tenant from the organization_id
        # embedded in the event metadata before any ORM calls.
        org_id = _stripe_event_organization_id(event_type, event_data)
        from django_tenants.utils import schema_context as _schema_context  # noqa: PLC0415
        organization = _resolve_billing_schema_organization(org_id)
        if organization is None:
            return Response(
                {"received": True, "event_type": event_type, "detail": "no_tenant_context"},
                status=status.HTTP_200_OK,
            )

        with _schema_context(organization.schema_name):
            return self._process_stripe_event(event, event_type, event_data, signature)

    @transaction.atomic
    def _process_stripe_event(self, event: dict, event_type: str, event_data: dict, signature: str):
        # event and event_data are already plain Python dicts (converted in post())
        event_id = str(event.get("id") or "")
        livemode = bool(event.get("livemode", False))
        if event_id:
            webhook_event, _ = BillingWebhookEvent.objects.get_or_create(
                provider="stripe",
                event_id=event_id,
                defaults={
                    "event_type": event_type,
                    "signature": signature,
                    "payload": event,
                    "livemode": livemode,
                    "processing_status": "received",
                },
            )
            webhook_event.event_type = event_type
            webhook_event.signature = signature
            webhook_event.payload = event
            webhook_event.livemode = livemode
            webhook_event.processing_status = "received"
            webhook_event.processing_error = ""
            webhook_event.save(update_fields=[
                "event_type",
                "signature",
                "payload",
                "livemode",
                "processing_status",
                "processing_error",
            ])
        else:
            webhook_event = BillingWebhookEvent.objects.create(
                provider="stripe",
                event_type=event_type,
                signature=signature,
                payload=event,
                livemode=livemode,
                processing_status="received",
            )

        event_data_dict = event_data  # already a plain dict from post()

        response_payload = {
            "received": True,
            "event_type": event_type,
        }

        try:
            if event_type in {
                "checkout.session.completed",
                "checkout.session.async_payment_succeeded",
                "checkout.session.async_payment_failed",
                "checkout.session.expired",
            }:
                subscription = _persist_stripe_session(event_data_dict)
                response_payload["session_id"] = subscription.session_id
                response_payload["payment_status"] = subscription.payment_status
            elif event_type == "invoice.payment_failed":
                stripe_subscription_id = str(event_data.get("subscription") or "").strip()
                subscription = _find_subscription_by_stripe_subscription_id(stripe_subscription_id)
                if subscription is not None:
                    subscription.status = "failed"
                    subscription.payment_status = "unpaid"
                    metadata = dict(subscription.metadata or {})
                    metadata["last_invoice_payment_failed_at"] = timezone.now().isoformat()
                    subscription.metadata = metadata
                    subscription.raw_last_payload = event_data_dict
                    subscription.save(
                        update_fields=["status", "payment_status", "metadata", "raw_last_payload", "updated_at"]
                    )
                    sync_onboarding_tokens_for_subscription(subscription)
                    response_payload["session_id"] = subscription.session_id
                    response_payload["payment_status"] = subscription.payment_status
                _notify_billing_payment_failure(
                    provider="stripe",
                    billing_event_type=event_type,
                    subscription=subscription,
                    reference=str(getattr(subscription, "reference", "") or stripe_subscription_id),
                    extra_metadata={"stripe_subscription_id": stripe_subscription_id},
                )
            elif event_type == "customer.subscription.deleted":
                stripe_subscription_id = str(event_data.get("id") or "").strip()
                subscription = _find_subscription_by_stripe_subscription_id(stripe_subscription_id)
                if subscription is not None:
                    subscription.status = "canceled"
                    subscription.payment_status = "unpaid"
                    metadata = dict(subscription.metadata or {})
                    metadata["cancel_at_period_end"] = bool(event_data.get("cancel_at_period_end", False))
                    current_period_end = event_data.get("current_period_end")
                    if current_period_end:
                        metadata["cancellation_effective_at"] = timezone.datetime.fromtimestamp(
                            int(current_period_end), tz=dt_timezone.utc
                        ).isoformat()
                    metadata["canceled_at"] = timezone.now().isoformat()
                    subscription.metadata = metadata
                    subscription.raw_last_payload = event_data_dict
                    subscription.save(
                        update_fields=["status", "payment_status", "metadata", "raw_last_payload", "updated_at"]
                    )
                    sync_onboarding_tokens_for_subscription(subscription)
                    response_payload["session_id"] = subscription.session_id
                    response_payload["payment_status"] = subscription.payment_status
            elif event_type == "customer.subscription.updated":
                stripe_subscription_id = str(event_data.get("id") or "").strip()
                subscription = _find_subscription_by_stripe_subscription_id(stripe_subscription_id)
                if subscription is not None:
                    metadata = dict(subscription.metadata or {})
                    current_period_start = event_data.get("current_period_start")
                    current_period_end = event_data.get("current_period_end")
                    if current_period_start:
                        metadata["current_period_start"] = timezone.datetime.fromtimestamp(
                            int(current_period_start), tz=dt_timezone.utc
                        ).isoformat()
                    if current_period_end:
                        metadata["current_period_end"] = timezone.datetime.fromtimestamp(
                            int(current_period_end), tz=dt_timezone.utc
                        ).isoformat()
                    cancel_at_period_end = bool(event_data.get("cancel_at_period_end", False))
                    metadata["cancel_at_period_end"] = cancel_at_period_end
                    if cancel_at_period_end and current_period_end:
                        metadata["cancellation_effective_at"] = timezone.datetime.fromtimestamp(
                            int(current_period_end), tz=dt_timezone.utc
                        ).isoformat()
                    stripe_status = str(event_data.get("status") or "").strip().lower()
                    if stripe_status in {"active", "trialing"}:
                        subscription.status = "complete"
                        if subscription.payment_status in {"unpaid", "failed", "canceled"}:
                            subscription.payment_status = "paid"
                    elif stripe_status in {"past_due", "unpaid", "incomplete", "incomplete_expired"}:
                        subscription.status = "failed"
                        subscription.payment_status = "unpaid"
                    elif stripe_status in {"canceled"}:
                        subscription.status = "canceled"
                        subscription.payment_status = "unpaid"
                    subscription.metadata = metadata
                    subscription.raw_last_payload = event_data_dict
                    subscription.save(
                        update_fields=["status", "payment_status", "metadata", "raw_last_payload", "updated_at"]
                    )
                    sync_onboarding_tokens_for_subscription(subscription)
                    response_payload["session_id"] = subscription.session_id
                    response_payload["payment_status"] = subscription.payment_status

            webhook_event.processing_status = "processed"
            webhook_event.processed_at = timezone.now()
            webhook_event.save(update_fields=["processing_status", "processed_at"])
        except Exception as exc:
            webhook_event.processing_status = "failed"
            webhook_event.processing_error = str(exc)
            webhook_event.processed_at = timezone.now()
            webhook_event.save(update_fields=["processing_status", "processing_error", "processed_at"])
            _notify_billing_processing_error(
                provider="stripe",
                webhook_event=webhook_event,
                billing_event_type=event_type,
                error_message=str(exc),
            )
            return Response(
                {
                    "received": True,
                    "event_type": event_type,
                    "detail": str(exc),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(response_payload, status=status.HTTP_200_OK)















