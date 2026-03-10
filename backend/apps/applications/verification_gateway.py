"""Verification gateway services for inter-agency evidence ingestion.

This module stores and normalizes external verification evidence.
Outputs remain advisory-only and must not become autonomous decisions.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.db import transaction
from django.utils import timezone

try:
    from apps.audit.contracts import (
        VERIFICATION_GATEWAY_REQUEST_CREATED_EVENT,
        VERIFICATION_GATEWAY_RESULT_RECORDED_EVENT,
    )
    from apps.audit.events import log_event
except Exception:  # pragma: no cover - audit app may be optional in some setups
    VERIFICATION_GATEWAY_REQUEST_CREATED_EVENT = "verification_gateway_request_created"
    VERIFICATION_GATEWAY_RESULT_RECORDED_EVENT = "verification_gateway_result_recorded"

    def log_event(**kwargs):  # type: ignore
        return False
from apps.billing.quotas import resolve_case_organization_id

from .models import ExternalVerificationResult, VerificationRequest, VerificationSource

REQUEST_TERMINAL_STATUSES = {"completed", "failed", "unavailable", "cancelled"}
RESULT_TO_REQUEST_STATUS = {
    "verified": "completed",
    "mismatch": "completed",
    "not_found": "completed",
    "inconclusive": "completed",
    "error": "failed",
    "unavailable": "unavailable",
}


def _json_sanitize(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        payload = {}
        for key, item in value.items():
            payload[str(key)] = _json_sanitize(item)
        return payload
    if isinstance(value, (list, tuple, set)):
        return [_json_sanitize(item) for item in value]
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            return str(value)
    return str(value)


def _normalize_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return _json_sanitize(value)
    if value is None:
        return {}
    return {"value": _json_sanitize(value)}


def _normalize_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return _json_sanitize(value)
    if value is None:
        return []
    return [_json_sanitize(value)]


def _resolve_request_organization_id(*, case, source: VerificationSource | None = None, actor=None) -> str | None:
    direct_case_org = str(getattr(case, "organization_id", "") or "").strip()
    if direct_case_org:
        return direct_case_org
    source_org = str(getattr(source, "organization_id", "") or "").strip()
    if source_org:
        return source_org
    resolved = resolve_case_organization_id(case, actor=actor)
    return str(resolved or "").strip() or None


def create_verification_request(
    *,
    case,
    source: VerificationSource,
    requested_by=None,
    purpose: str = "vetting_evidence",
    subject_identifiers: dict[str, Any] | None = None,
    request_payload: dict[str, Any] | None = None,
    idempotency_key: str = "",
    request=None,
) -> tuple[VerificationRequest, bool]:
    """
    Create a verification request with optional idempotency protection.

    Returns tuple: ``(verification_request, created)``.
    """
    if not source.is_active:
        raise ValueError("Verification source is inactive.")

    normalized_idempotency = str(idempotency_key or "").strip()
    normalized_identifiers = _normalize_dict(subject_identifiers)
    normalized_request_payload = _normalize_dict(request_payload)
    resolved_org_id = _resolve_request_organization_id(case=case, source=source, actor=requested_by)

    with transaction.atomic():
        case_model = case.__class__
        locked_case = case_model.objects.select_for_update().get(pk=case.pk)

        if normalized_idempotency:
            existing = (
                VerificationRequest.objects.select_for_update()
                .filter(
                    case=locked_case,
                    source=source,
                    idempotency_key=normalized_idempotency,
                )
                .order_by("-requested_at")
                .first()
            )
            if existing is not None:
                return existing, False

        verification_request = VerificationRequest.objects.create(
            organization_id=resolved_org_id,
            case=locked_case,
            source=source,
            requested_by=requested_by if getattr(requested_by, "is_authenticated", False) else None,
            status="pending",
            purpose=str(purpose or "vetting_evidence").strip()[:100] or "vetting_evidence",
            idempotency_key=normalized_idempotency,
            subject_identifiers=normalized_identifiers,
            request_payload=normalized_request_payload,
        )

    log_event(
        request=request,
        action="create",
        entity_type="VerificationRequest",
        entity_id=str(verification_request.id),
        user=requested_by if getattr(requested_by, "is_authenticated", False) else None,
        changes={
            "event": VERIFICATION_GATEWAY_REQUEST_CREATED_EVENT,
            "case_id": str(verification_request.case_id),
            "source_id": str(verification_request.source_id),
            "source_key": verification_request.source.key,
            "organization_id": str(verification_request.organization_id or ""),
            "status": verification_request.status,
            "has_subject_identifiers": bool(verification_request.subject_identifiers),
        },
    )
    return verification_request, True


def record_verification_result(
    *,
    verification_request: VerificationRequest,
    result_status: str,
    recommendation: str = "review",
    confidence_score: float | None = None,
    advisory_flags: list[dict[str, Any]] | None = None,
    evidence_summary: dict[str, Any] | None = None,
    normalized_evidence: dict[str, Any] | None = None,
    raw_payload: dict[str, Any] | None = None,
    raw_payload_redacted: bool = True,
    provider_reference: str = "",
    actor=None,
    request=None,
) -> ExternalVerificationResult:
    """Persist a normalized external verification result and sync request state."""
    allowed_statuses = {choice[0] for choice in ExternalVerificationResult.RESULT_STATUS_CHOICES}
    normalized_status = str(result_status or "").strip().lower()
    if normalized_status not in allowed_statuses:
        raise ValueError("Invalid result_status for external verification result.")

    allowed_recommendations = {choice[0] for choice in ExternalVerificationResult.RECOMMENDATION_CHOICES}
    normalized_recommendation = str(recommendation or "").strip().lower()
    if normalized_recommendation not in allowed_recommendations:
        normalized_recommendation = "review"

    normalized_confidence = None
    if confidence_score is not None:
        try:
            normalized_confidence = float(confidence_score)
        except (TypeError, ValueError) as exc:
            raise ValueError("confidence_score must be numeric.") from exc
        if normalized_confidence < 0 or normalized_confidence > 100:
            raise ValueError("confidence_score must be between 0 and 100.")

    with transaction.atomic():
        locked_request = VerificationRequest.objects.select_for_update().select_related("source", "case").get(
            pk=verification_request.pk
        )

        request_status = RESULT_TO_REQUEST_STATUS.get(normalized_status, "completed")
        now = timezone.now()
        update_fields = ["status", "updated_at"]
        if locked_request.submitted_at is None:
            locked_request.submitted_at = now
            update_fields.append("submitted_at")
        locked_request.status = request_status
        if request_status in REQUEST_TERMINAL_STATUSES:
            locked_request.completed_at = now
            update_fields.append("completed_at")
        else:
            locked_request.last_polled_at = now
            update_fields.append("last_polled_at")
        if provider_reference:
            locked_request.external_reference = str(provider_reference).strip()[:255]
            update_fields.append("external_reference")
        locked_request.save(update_fields=list(dict.fromkeys(update_fields)))

        result, _ = ExternalVerificationResult.objects.update_or_create(
            verification_request=locked_request,
            defaults={
                "organization_id": locked_request.organization_id,
                "case": locked_request.case,
                "source": locked_request.source,
                "result_status": normalized_status,
                "recommendation": normalized_recommendation,
                "confidence_score": normalized_confidence,
                "advisory_flags": _normalize_list(advisory_flags),
                "evidence_summary": _normalize_dict(evidence_summary),
                "normalized_evidence": _normalize_dict(normalized_evidence),
                "raw_payload": _normalize_dict(raw_payload),
                "raw_payload_redacted": bool(raw_payload_redacted),
                "provider_reference": str(provider_reference or "").strip()[:255],
            },
        )

    log_event(
        request=request,
        action="create",
        entity_type="ExternalVerificationResult",
        entity_id=str(result.id),
        user=actor if getattr(actor, "is_authenticated", False) else None,
        changes={
            "event": VERIFICATION_GATEWAY_RESULT_RECORDED_EVENT,
            "verification_request_id": str(result.verification_request_id),
            "case_id": str(result.case_id),
            "source_id": str(result.source_id),
            "source_key": result.source.key,
            "organization_id": str(result.organization_id or ""),
            "result_status": result.result_status,
            "recommendation": result.recommendation,
            "advisory_flags_count": len(result.advisory_flags or []),
            "has_normalized_evidence": bool(result.normalized_evidence),
            "raw_payload_redacted": bool(result.raw_payload_redacted),
        },
    )
    return result


def empty_external_verification_snapshot() -> dict[str, Any]:
    return {
        "total_requests": 0,
        "pending": 0,
        "in_progress": 0,
        "completed": 0,
        "failed": 0,
        "unavailable": 0,
        "sources_with_advisory_flags": 0,
        "advisory_flags_total": 0,
        "latest_by_source": [],
        "advisory_only": True,
    }


def build_case_external_verification_snapshot(case) -> dict[str, Any]:
    """Build a decision-engine friendly snapshot for case-level external evidence."""
    queryset = (
        VerificationRequest.objects.filter(case=case)
        .select_related("source")
        .prefetch_related("external_result")
        .order_by("-requested_at", "-updated_at")
    )
    if not queryset.exists():
        return empty_external_verification_snapshot()

    snapshot = empty_external_verification_snapshot()
    snapshot["total_requests"] = queryset.count()
    snapshot["pending"] = queryset.filter(status="pending").count()
    snapshot["in_progress"] = queryset.filter(status__in=["submitted", "in_progress"]).count()
    snapshot["completed"] = queryset.filter(status="completed").count()
    snapshot["failed"] = queryset.filter(status="failed").count()
    snapshot["unavailable"] = queryset.filter(status="unavailable").count()

    seen_source_ids: set[str] = set()
    latest_by_source: list[dict[str, Any]] = []
    advisory_sources = 0
    advisory_flags_total = 0

    for verification_request in queryset:
        source_id = str(verification_request.source_id)
        if source_id in seen_source_ids:
            continue
        seen_source_ids.add(source_id)
        result = getattr(verification_request, "external_result", None)
        flags = []
        if result is not None and isinstance(result.advisory_flags, list):
            flags = result.advisory_flags
            if flags:
                advisory_sources += 1
                advisory_flags_total += len(flags)
        latest_by_source.append(
            {
                "source_id": source_id,
                "source_key": verification_request.source.key,
                "source_name": verification_request.source.name,
                "source_category": verification_request.source.source_category,
                "request_status": verification_request.status,
                "result_status": getattr(result, "result_status", ""),
                "recommendation": getattr(result, "recommendation", ""),
                "confidence_score": getattr(result, "confidence_score", None),
                "advisory_flags_count": len(flags),
                "received_at": (
                    result.received_at.isoformat()
                    if result is not None and getattr(result, "received_at", None) is not None
                    else None
                ),
            }
        )

    snapshot["latest_by_source"] = latest_by_source
    snapshot["sources_with_advisory_flags"] = advisory_sources
    snapshot["advisory_flags_total"] = advisory_flags_total
    return snapshot
