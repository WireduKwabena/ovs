from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

try:
    from drf_spectacular.utils import extend_schema
except ModuleNotFoundError:  # pragma: no cover - optional in lightweight setups
    def extend_schema(*args, **kwargs):  # type: ignore
        def decorator(func):
            return func

        return decorator

from .models import BillingSubscription, BillingWebhookEvent
from .serializers import (
    BillingActionErrorSerializer,
    BillingHealthResponseSerializer,
    BillingWebhookResponseSerializer,
    StripeCheckoutSessionConfirmSerializer,
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
    def log_event(**kwargs):  # type: ignore
        return False

    def request_ip_address(request):  # type: ignore
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


def _stripe_secret_key() -> str:
    return str(getattr(settings, "STRIPE_SECRET_KEY", "") or "").strip()


def _stripe_webhook_secret() -> str:
    return str(getattr(settings, "STRIPE_WEBHOOK_SECRET", "") or "").strip()


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


def _to_decimal(value, fallback: str = "0.00") -> Decimal:
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal(fallback)


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


def _ms_to_datetime(ms: int | None):
    if ms is None:
        return None
    try:
        return timezone.datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc)
    except Exception:
        return None


def _datetime_to_ms(value):
    if value is None:
        return None
    return int(value.timestamp() * 1000)


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


def _billing_health_require_staff() -> bool:
    return bool(getattr(settings, "BILLING_HEALTH_REQUIRE_STAFF", False))


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


def _persist_sandbox_ticket(ticket: dict):
    return BillingSubscription.objects.create(
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
        metadata={"source": "sandbox_confirm"},
        raw_last_payload=ticket,
    )


def _persist_stripe_session(session_data: dict, *, checkout_url: str | None = None):
    metadata = session_data.get("metadata") or {}
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

    subscription, _ = BillingSubscription.objects.update_or_create(
        session_id=session_id,
        defaults=defaults,
    )
    return subscription


class SubscriptionConfirmAPIView(APIView):
    permission_classes = [AllowAny]
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

        _persist_sandbox_ticket(ticket)

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
                "subscription_verify_rate_limit": {
                    "enabled": _verify_rate_limit_enabled(),
                    "per_minute": _verify_rate_limit_per_minute(),
                },
            },
            status=status.HTTP_200_OK,
        )


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
    permission_classes = [AllowAny]
    serializer_class = StripeCheckoutSessionCreateSerializer

    def post(self, request):
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
            )
        except Exception as exc:
            raise ValidationError(f"Unable to create Stripe checkout session: {exc}") from exc

        _persist_stripe_session(dict(session), checkout_url=session.get("url"))

        return Response(
            {
                "provider": "stripe",
                "session_id": session.get("id"),
                "checkout_url": session.get("url"),
            },
            status=status.HTTP_200_OK,
        )


class StripeCheckoutSessionConfirmAPIView(APIView):
    permission_classes = [AllowAny]
    serializer_class = StripeCheckoutSessionConfirmSerializer

    def post(self, request):
        _ensure_stripe_ready()

        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        session_id = serializer.validated_data["session_id"]

        try:
            session = _stripe_retrieve_checkout_session(session_id)
        except Exception as exc:
            raise ValidationError(f"Unable to retrieve Stripe session: {exc}") from exc

        session_payload = dict(session)
        session_status = session_payload.get("status")
        payment_status = session_payload.get("payment_status")
        if session_status != "complete" or payment_status not in {"paid", "no_payment_required"}:
            raise ValidationError("Stripe checkout session is not fully paid yet.")

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
    @transaction.atomic
    def post(self, request):
        _ensure_stripe_webhook_ready()

        signature = request.headers.get("Stripe-Signature", "")
        if not signature:
            raise ValidationError("Missing Stripe-Signature header.")

        payload = request.body
        try:
            event = _stripe_construct_event(payload=payload, sig_header=signature)
        except Exception as exc:
            raise ValidationError(f"Invalid Stripe webhook signature: {exc}") from exc

        event_id = str(event.get("id") or "")
        if event_id:
            webhook_event, _ = BillingWebhookEvent.objects.get_or_create(
                provider="stripe",
                event_id=event_id,
                defaults={
                    "event_type": event.get("type", ""),
                    "signature": signature,
                    "payload": event,
                    "livemode": bool(event.get("livemode", False)),
                    "processing_status": "received",
                },
            )
            webhook_event.event_type = event.get("type", "")
            webhook_event.signature = signature
            webhook_event.payload = event
            webhook_event.livemode = bool(event.get("livemode", False))
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
                event_type=event.get("type", ""),
                signature=signature,
                payload=event,
                livemode=bool(event.get("livemode", False)),
                processing_status="received",
            )

        event_type = event.get("type", "")
        event_data = (event.get("data") or {}).get("object") or {}

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
                subscription = _persist_stripe_session(dict(event_data))
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
            raise

        return Response(response_payload, status=status.HTTP_200_OK)
















