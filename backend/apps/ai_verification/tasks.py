"""Compatibility task surface for legacy ``apps.ai_verification.tasks`` imports.

This module now delegates to the current ``apps.applications`` pipeline so
legacy references do not execute stale schema logic.
"""

from __future__ import annotations

import logging
from typing import Any

from celery import shared_task
from django.db.models import Avg

from apps.applications.models import VerificationResult, VettingCase
from apps.applications.tasks import verify_document_async as verify_document_async
from apps.interviews.services.flag_generator import InterrogationFlagGenerator
from apps.rubrics.models import VettingRubric
from apps.rubrics.tasks import evaluate_case_with_rubric

logger = logging.getLogger(__name__)


def _get_case_or_error(case_id: int) -> tuple[VettingCase | None, dict[str, Any] | None]:
    try:
        return VettingCase.objects.get(id=case_id), None
    except VettingCase.DoesNotExist:
        return None, {"success": False, "error": f"VettingCase {case_id} not found"}


@shared_task
def check_application_consistency(case_id: int) -> dict[str, Any]:
    """Backfill a case-level consistency score from existing document results."""

    case, error = _get_case_or_error(case_id)
    if error:
        return error

    aggregate = VerificationResult.objects.filter(document__case=case).aggregate(
        avg_ocr_confidence=Avg("ocr_confidence")
    )
    score = aggregate["avg_ocr_confidence"]
    if score is None:
        return {
            "success": False,
            "case_id": case.case_id,
            "error": "No verification results available for consistency scoring",
        }

    case.consistency_score = float(score)
    case.save(update_fields=["consistency_score", "updated_at"])
    return {"success": True, "case_id": case.case_id, "consistency_score": case.consistency_score}


@shared_task
def detect_application_fraud(case_id: int) -> dict[str, Any]:
    """Backfill a case-level fraud score from existing document results."""

    case, error = _get_case_or_error(case_id)
    if error:
        return error

    aggregate = VerificationResult.objects.filter(document__case=case).aggregate(
        avg_fraud_risk=Avg("fraud_risk_score")
    )
    score = aggregate["avg_fraud_risk"]
    if score is None:
        return {
            "success": False,
            "case_id": case.case_id,
            "error": "No verification results available for fraud scoring",
        }

    case.fraud_risk_score = float(score)
    case.requires_manual_review = case.fraud_risk_score >= 50
    if case.requires_manual_review and case.status in {"pending", "document_upload", "document_analysis"}:
        case.status = "under_review"
    if case.fraud_risk_score >= 75 and case.priority in {"low", "medium"}:
        case.priority = "high"
    case.save(update_fields=["fraud_risk_score", "requires_manual_review", "status", "priority", "updated_at"])
    return {"success": True, "case_id": case.case_id, "fraud_risk_score": case.fraud_risk_score}


@shared_task
def evaluate_with_rubric(case_id: int) -> dict[str, Any]:
    """Queue rubric evaluation using the active default rubric when available."""

    case, error = _get_case_or_error(case_id)
    if error:
        return error

    rubric = (
        VettingRubric.objects.filter(is_active=True, is_default=True).order_by("-updated_at").first()
        or VettingRubric.objects.filter(is_active=True).order_by("-updated_at").first()
    )
    if rubric is None:
        logger.warning("No active rubric found for case %s", case.case_id)
        return {"success": False, "case_id": case.case_id, "error": "No active rubric configured"}

    task = evaluate_case_with_rubric.delay(case.id, rubric.id)
    return {
        "success": True,
        "case_id": case.case_id,
        "rubric_id": rubric.id,
        "queued_task_id": task.id,
    }


@shared_task
def batch_process_applications(case_ids: list[int]) -> dict[str, Any]:
    """Queue document verification tasks for each provided case id."""

    queued = 0
    skipped = 0
    errors: list[dict[str, Any]] = []

    for case_id in case_ids:
        case, error = _get_case_or_error(case_id)
        if error:
            skipped += 1
            errors.append({"case_id": case_id, "error": error["error"]})
            continue

        document_ids = list(case.documents.values_list("id", flat=True))
        for document_id in document_ids:
            verify_document_async.delay(document_id)
            queued += 1

    return {"success": True, "queued_documents": queued, "skipped_cases": skipped, "errors": errors}


@shared_task
def aggregate_flags(vetting_case_id: int) -> dict[str, Any]:
    """Generate interrogation flags from current document verification outputs."""

    case, error = _get_case_or_error(vetting_case_id)
    if error:
        return error
    return InterrogationFlagGenerator.sync_case_flags(case=case, persist=True, replace_pending=False)


@shared_task
def trigger_interrogation(vetting_case_id: int) -> dict[str, Any]:
    """
    Legacy entrypoint retained for compatibility.

    Current behavior regenerates case flags and returns the flag summary.
    Interview session orchestration should happen in the interviews app.
    """

    return aggregate_flags(vetting_case_id)


# Backward-compatible aliases from previous naming.
check_consistency_async = check_application_consistency
detect_fraud_async = detect_application_fraud
verify_document_complete = verify_document_async
