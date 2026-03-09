import json
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.billing.quotas import (
    VETTING_OPERATION_BACKGROUND_CHECK_SUBMISSION,
    enforce_vetting_operation_quota,
    resolve_case_organization_id,
)

from .models import BackgroundCheck, BackgroundCheckEvent
from .providers import default_provider_registry

try:
    from apps.audit.events import log_event
except Exception:  # pragma: no cover - audit app may be optional in some setups
    def log_event(**kwargs):  # type: ignore
        return False


TERMINAL_STATUSES = {"completed", "failed", "cancelled", "manual_review"}
VALID_STATUSES = {choice[0] for choice in BackgroundCheck.STATUS_CHOICES}
VALID_RISK_LEVELS = {choice[0] for choice in BackgroundCheck.RISK_LEVEL_CHOICES}
VALID_RECOMMENDATIONS = {choice[0] for choice in BackgroundCheck.RECOMMENDATION_CHOICES}


def _json_sanitize(value):
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        normalized = {}
        for key, item in value.items():
            normalized[str(key)] = _json_sanitize(item)
        return normalized
    if isinstance(value, (list, tuple, set)):
        return [_json_sanitize(item) for item in value]
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            return str(value)
    try:
        json.dumps(value)
        return value
    except Exception:
        return str(value)


def _normalize_payload(payload):
    if payload is None:
        return {}
    if isinstance(payload, dict):
        return _json_sanitize(payload)
    return {"value": _json_sanitize(payload)}


def _normalize_status(status):
    normalized = str(status or "").lower()
    return normalized if normalized in VALID_STATUSES else "submitted"


def _normalize_risk_level(risk_level):
    normalized = str(risk_level or "").lower()
    return normalized if normalized in VALID_RISK_LEVELS else "unknown"


def _normalize_recommendation(recommendation):
    normalized = str(recommendation or "").lower()
    return normalized if normalized in VALID_RECOMMENDATIONS else "unavailable"


def _providers():
    return default_provider_registry()


def available_provider_keys():
    return sorted(_providers().keys())


def get_provider(provider_key):
    providers = _providers()
    key = str(provider_key or "").strip().lower()
    if not key:
        key = str(getattr(settings, "BACKGROUND_CHECK_DEFAULT_PROVIDER", "mock")).strip().lower()
    provider = providers.get(key)
    if provider is None:
        raise ValueError(f"Unsupported background check provider '{provider_key}'.")
    return provider


def _consent_granted(consent_evidence):
    if not isinstance(consent_evidence, dict):
        return False
    return bool(
        consent_evidence.get("granted")
        or consent_evidence.get("consent_granted")
        or consent_evidence.get("accepted")
    )


def _record_event(check, *, event_type, status_before, status_after, payload=None, message=""):
    BackgroundCheckEvent.objects.create(
        background_check=check,
        event_type=event_type,
        status_before=status_before or "",
        status_after=status_after or "",
        payload=_normalize_payload(payload),
        message=message or "",
    )


def _audit_check(*, check, action, event, changes=None, user=None, request=None):
    payload = {
        "event": event,
        "case_id": check.case.case_id,
        "check_type": check.check_type,
        "provider_key": check.provider_key,
        "status": check.status,
        **(changes or {}),
    }
    log_event(
        action=action,
        entity_type="background_check",
        entity_id=str(check.id),
        changes=payload,
        user=user if user is not None else check.submitted_by,
        request=request,
    )


def submit_background_check(
    *,
    case,
    check_type,
    submitted_by,
    provider_key=None,
    request_payload=None,
    consent_evidence=None,
    request=None,
):
    require_consent = bool(getattr(settings, "BACKGROUND_CHECK_REQUIRE_CONSENT", True))
    normalized_consent = _normalize_payload(consent_evidence)
    if require_consent and not _consent_granted(normalized_consent):
        raise ValueError("Consent is required before running third-party background checks.")

    resolved_org_id = resolve_case_organization_id(case)
    quota_actor = submitted_by if (resolved_org_id is None and getattr(submitted_by, "is_authenticated", False)) else None
    enforce_vetting_operation_quota(
        operation=VETTING_OPERATION_BACKGROUND_CHECK_SUBMISSION,
        user=quota_actor,
        organization_id=resolved_org_id,
        additional=1,
    )

    provider = get_provider(provider_key)

    check = BackgroundCheck.objects.create(
        case=case,
        check_type=check_type,
        provider_key=provider.key,
        status="pending",
        request_payload=_normalize_payload(request_payload),
        consent_evidence=normalized_consent,
        submitted_by=submitted_by,
    )

    status_before = check.status
    try:
        submission = provider.submit_check(check)
        check.status = _normalize_status(submission.status)
        check.external_reference = submission.external_reference
        check.response_payload = _normalize_payload(submission.raw_payload)
        check.submitted_at = timezone.now()
        check.error_code = ""
        check.error_message = ""
        check.save(
            update_fields=[
                "status",
                "external_reference",
                "response_payload",
                "submitted_at",
                "error_code",
                "error_message",
                "updated_at",
            ]
        )
        _record_event(
            check,
            event_type="submitted",
            status_before=status_before,
            status_after=check.status,
            payload=submission.raw_payload,
        )
        _audit_check(
            check=check,
            action="create",
            event="submit",
            user=submitted_by,
            changes={
                "status_before": status_before,
                "status_after": check.status,
                "external_reference": check.external_reference,
            },
            request=request,
        )
        return check
    except Exception as exc:
        check.status = "failed"
        check.error_code = "submit_failed"
        check.error_message = str(exc)
        check.save(update_fields=["status", "error_code", "error_message", "updated_at"])
        _record_event(
            check,
            event_type="error",
            status_before=status_before,
            status_after=check.status,
            payload={"error": str(exc)},
            message="Failed to submit background check to provider.",
        )
        _audit_check(
            check=check,
            action="update",
            event="submit_error",
            user=submitted_by,
            changes={
                "status_before": status_before,
                "status_after": check.status,
                "error_code": check.error_code,
                "error_message": check.error_message,
            },
            request=request,
        )
        raise


def refresh_background_check(check, *, request=None):
    if check.status in TERMINAL_STATUSES:
        return check

    provider = get_provider(check.provider_key)
    status_before = check.status

    result = provider.refresh_check(check)
    check.status = _normalize_status(result.status)
    check.last_polled_at = timezone.now()
    check.response_payload = _normalize_payload(result.raw_payload)

    if result.score is not None:
        check.score = float(result.score)
    if result.risk_level is not None:
        check.risk_level = _normalize_risk_level(result.risk_level)
    if result.recommendation is not None:
        check.recommendation = _normalize_recommendation(result.recommendation)

    if check.status in {"completed", "manual_review"}:
        check.completed_at = result.completed_at or timezone.now()

    check.result_summary = {
        "score": check.score,
        "risk_level": check.risk_level,
        "recommendation": check.recommendation,
    }

    check.save(
        update_fields=[
            "status",
            "last_polled_at",
            "response_payload",
            "score",
            "risk_level",
            "recommendation",
            "completed_at",
            "result_summary",
            "updated_at",
        ]
    )
    _record_event(
        check,
        event_type="provider_update",
        status_before=status_before,
        status_after=check.status,
        payload=result.raw_payload,
    )
    _audit_check(
        check=check,
        action="update",
        event="provider_refresh",
        changes={
            "status_before": status_before,
            "status_after": check.status,
            "score": check.score,
            "risk_level": check.risk_level,
            "recommendation": check.recommendation,
        },
        request=request,
    )
    return check


def apply_webhook_update(*, provider_key, payload, request=None):
    provider = get_provider(provider_key)
    normalized_payload = _normalize_payload(payload)
    result = provider.parse_webhook(normalized_payload)

    external_reference = (
        normalized_payload.get("external_reference")
        or normalized_payload.get("reference")
        or result.raw_payload.get("external_reference")
    )
    if not external_reference:
        raise ValueError("Webhook payload must include external_reference.")

    with transaction.atomic():
        check = (
            BackgroundCheck.objects.select_for_update()
            .filter(provider_key=provider.key, external_reference=external_reference)
            .first()
        )
        if check is None:
            raise LookupError("No background check found for webhook reference.")

        status_before = check.status
        check.status = _normalize_status(result.status)
        check.webhook_received_at = timezone.now()
        check.response_payload = normalized_payload

        if result.score is not None:
            check.score = float(result.score)
        if result.risk_level is not None:
            check.risk_level = _normalize_risk_level(result.risk_level)
        if result.recommendation is not None:
            check.recommendation = _normalize_recommendation(result.recommendation)

        if check.status in {"completed", "manual_review"}:
            check.completed_at = result.completed_at or timezone.now()

        check.result_summary = {
            "score": check.score,
            "risk_level": check.risk_level,
            "recommendation": check.recommendation,
        }

        check.save(
            update_fields=[
                "status",
                "webhook_received_at",
                "response_payload",
                "score",
                "risk_level",
                "recommendation",
                "completed_at",
                "result_summary",
                "updated_at",
            ]
        )
        _record_event(
            check,
            event_type="webhook",
            status_before=status_before,
            status_after=check.status,
            payload=normalized_payload,
        )
        _audit_check(
            check=check,
            action="update",
            event="provider_webhook",
            changes={
                "status_before": status_before,
                "status_after": check.status,
                "score": check.score,
                "risk_level": check.risk_level,
                "recommendation": check.recommendation,
                "external_reference": check.external_reference,
            },
            request=request,
        )
        return check
