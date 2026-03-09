import logging

from celery import shared_task
from django.db.models import Avg
from django.utils import timezone
from rest_framework.exceptions import ValidationError as DRFValidationError

from .models import Document, InterrogationFlag, VerificationResult
from apps.applications.social_checks import run_case_social_profile_check
from apps.billing.quotas import (
    VETTING_OPERATION_DOCUMENT_VERIFICATION,
    enforce_vetting_operation_quota,
    resolve_case_organization_id,
)

logger = logging.getLogger(__name__)


def _build_placeholder_analysis(document: Document) -> dict:
    """
    Temporary baseline until OCR/authenticity/fraud models are wired.
    Produces deterministic values from document metadata to keep the
    document pipeline and rubric flow functional.
    """
    filename = (document.original_filename or "").lower()

    authenticity_score = 92.0
    fraud_risk_score = 18.0
    if "scan" in filename or "copy" in filename:
        authenticity_score = 75.0
        fraud_risk_score = 35.0
    if "edited" in filename or "fake" in filename:
        authenticity_score = 48.0
        fraud_risk_score = 82.0

    is_authentic = authenticity_score >= 70
    fraud_prediction = "fraudulent" if fraud_risk_score >= 75 else ("suspicious" if fraud_risk_score >= 50 else "legitimate")

    return {
        "ocr_text": f"Placeholder OCR text for {document.document_type}",
        "ocr_confidence": 88.0,
        "ocr_language": "en",
        "authenticity_score": authenticity_score,
        "authenticity_confidence": 80.0,
        "is_authentic": is_authentic,
        "metadata_check_passed": is_authentic,
        "visual_check_passed": is_authentic,
        "tampering_detected": not is_authentic,
        "fraud_risk_score": fraud_risk_score,
        "fraud_prediction": fraud_prediction,
        "fraud_indicators": ["placeholder_pipeline"],
        "detailed_results": {
            "pipeline": "placeholder",
            "document_type": document.document_type,
        },
        "ocr_model_version": "baseline-0.1",
        "authenticity_model_version": "baseline-0.1",
        "fraud_model_version": "baseline-0.1",
    }


def _upsert_flag_for_document(document: Document, result: VerificationResult) -> None:
    if result.fraud_prediction == "legitimate" and result.is_authentic:
        return

    flag_type = "fraud_indicator" if result.fraud_risk_score >= 50 else "authenticity_concern"
    severity = "critical" if result.fraud_risk_score >= 75 else "high"
    title = f"{document.get_document_type_display()} requires review"

    flag, created = InterrogationFlag.objects.get_or_create(
        case=document.case,
        title=title,
        defaults={
            "flag_type": flag_type,
            "severity": severity,
            "description": "Document analysis detected non-trivial risk signals.",
            "data_point": document.original_filename,
            "evidence": {
                "authenticity_score": result.authenticity_score,
                "fraud_risk_score": result.fraud_risk_score,
                "fraud_prediction": result.fraud_prediction,
            },
            "suggested_questions": [
                "Can you clarify the source of this document?",
                "Can you explain any edits or re-issuance history?",
            ],
        },
    )
    if created:
        flag.related_documents.add(document)


def _refresh_case_aggregates(document: Document):
    case = document.case
    documents = case.documents.all()
    verification_qs = VerificationResult.objects.filter(document__case=case)

    case.documents_uploaded = documents.exists()

    aggregate = verification_qs.aggregate(
        avg_authenticity=Avg("authenticity_score"),
        avg_fraud=Avg("fraud_risk_score"),
        avg_ocr=Avg("ocr_confidence"),
    )
    case.document_authenticity_score = aggregate["avg_authenticity"] or case.document_authenticity_score
    case.fraud_risk_score = aggregate["avg_fraud"] or case.fraud_risk_score
    case.consistency_score = aggregate["avg_ocr"] or case.consistency_score

    processed_states = {"verified", "flagged", "failed"}
    case.documents_verified = documents.exists() and not documents.exclude(status__in=processed_states).exists()
    case.red_flags_count = case.interrogation_flags.exclude(status__in=["resolved", "dismissed"]).count()
    case.requires_manual_review = case.red_flags_count > 0 or (case.fraud_risk_score or 0) >= 50

    if case.status in {"pending", "document_upload", "document_analysis"}:
        case.status = "document_analysis" if not case.documents_verified else "interview_scheduled"

    case.save(
        update_fields=[
            "documents_uploaded",
            "documents_verified",
            "document_authenticity_score",
            "fraud_risk_score",
            "consistency_score",
            "red_flags_count",
            "requires_manual_review",
            "status",
            "updated_at",
        ]
    )
    return case


def _ensure_interview_session_for_case(case):
    if not case.documents_verified or case.interview_completed:
        return None

    from apps.interviews.models import InterviewSession

    interview_session = (
        InterviewSession.objects.filter(case=case)
        .order_by("-created_at")
        .first()
    )
    if interview_session is None:
        interview_session = InterviewSession.objects.create(
            case=case,
            use_dynamic_questions=True,
            status="created",
        )

    if case.status not in {"approved", "rejected", "on_hold"}:
        target_status = case.status
        if interview_session.status == "in_progress":
            target_status = "interview_in_progress"
        elif interview_session.status in {"created", "failed", "cancelled"}:
            target_status = "interview_scheduled"
        elif interview_session.status == "completed":
            target_status = "under_review"

        if target_status != case.status:
            case.status = target_status
            case.save(update_fields=["status", "updated_at"])

    return interview_session


def _sync_case_social_profile_result(document: Document) -> None:
    outcome = run_case_social_profile_check(document.case)
    if not outcome.get("success") and outcome.get("reason") != "no_profiles":
        logger.warning(
            "Social profile sync did not complete for case %s: %s",
            outcome.get("case_id", "unknown"),
            outcome,
        )


@shared_task(bind=True, max_retries=2)
def verify_document_async(self, document_id: int):
    try:
        document = Document.objects.select_related("case").get(id=document_id)
    except Document.DoesNotExist:
        return {"success": False, "error": f"Document {document_id} not found"}

    started_at = timezone.now()
    document.status = "processing"
    document.save(update_fields=["status"])

    try:
        resolved_org_id = resolve_case_organization_id(document.case)
        enforce_vetting_operation_quota(
            operation=VETTING_OPERATION_DOCUMENT_VERIFICATION,
            user=None,
            organization_id=resolved_org_id,
            additional=0,
        )

        analysis = _build_placeholder_analysis(document)
        duration = (timezone.now() - started_at).total_seconds()

        result, _ = VerificationResult.objects.update_or_create(
            document=document,
            defaults={
                **analysis,
                "processing_time_seconds": duration,
            },
        )

        document.extracted_text = analysis["ocr_text"]
        document.extracted_data = analysis["detailed_results"]
        document.ocr_completed = True
        document.authenticity_check_completed = True
        document.fraud_check_completed = True
        document.processed_at = timezone.now()
        document.status = "verified" if result.is_authentic and result.fraud_prediction == "legitimate" else "flagged"
        document.processing_error = ""
        document.save(
            update_fields=[
                "extracted_text",
                "extracted_data",
                "ocr_completed",
                "authenticity_check_completed",
                "fraud_check_completed",
                "processed_at",
                "status",
                "processing_error",
            ]
        )

        _upsert_flag_for_document(document, result)
        case = _refresh_case_aggregates(document)
        if case.documents_verified:
            _ensure_interview_session_for_case(case)
            _sync_case_social_profile_result(document)

        return {
            "success": True,
            "document_id": document.id,
            "status": document.status,
            "verification_result_id": result.id,
        }
    except DRFValidationError as exc:
        detail = exc.detail if isinstance(exc.detail, dict) else {"detail": exc.detail}
        document.status = "failed"
        document.processing_error = str(detail.get("detail") or "Vetting operation quota enforcement blocked processing.")
        document.processed_at = timezone.now()
        document.save(update_fields=["status", "processing_error", "processed_at"])
        return {
            "success": False,
            "document_id": document.id,
            "error": detail.get("detail"),
            "code": detail.get("code"),
            "quota": detail.get("quota"),
        }
    except Exception as exc:
        document.status = "failed"
        document.retry_count += 1
        document.processing_error = str(exc)
        document.processed_at = timezone.now()
        document.save(update_fields=["status", "retry_count", "processing_error", "processed_at"])
        raise






