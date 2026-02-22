"""
Celery tasks for AI/ML services.

These tasks provide async processing for document verification, fraud detection,
etc. They are designed to be called from other apps' task modules.
"""

import logging

from celery import shared_task

from ai_ml_services.service import (
    AIServiceException,
    verify_document,
    detect_fraud,
    check_consistency,
    batch_verify_documents,
)

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    max_retries=3,
    autoretry_for=(AIServiceException,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
)
def verify_document_task(
    self,
    document_id: int,
    file_path: str,
    document_type: str,
    case_id: str,
):
    """
    Asynchronously verify a document using AI/ML services.

    Args:
        document_id: Database ID of the document
        file_path: Path to the document file
        document_type: Type of document (id_card, passport, etc.)
        case_id: Case ID for tracking

    Returns:
        Dictionary containing verification results

    Example:
        from ai_ml_services.utils.tasks import verify_document_task

        verify_document_task.delay(
            document_id=123,
            file_path='/path/to/document.pdf',
            document_type='id_card',
            case_id='APP-001'
        )
    """
    logger.info(
        f"Starting AI document verification for document_id={document_id}, "
        f"case={case_id}, type={document_type}"
    )

    try:
        result = verify_document(
            file_path=file_path,
            document_type=document_type,
            case_id=case_id,
        )

        logger.info(
            f"Document verification completed for document_id={document_id}: "
            f"score={result['results']['overall_score']:.2f}, "
            f"recommendation={result['results']['recommendation']}"
        )

        return {
            "success": True,
            "document_id": document_id,
            "case_id": case_id,
            "result": result,
        }

    except AIServiceException as exc:
        logger.error(
            f"AI service error for document_id={document_id}: {exc}",
            exc_info=True,
        )
        raise

    except FileNotFoundError:
        logger.error(
            f"Document file not found for document_id={document_id}: {file_path}"
        )
        raise AIServiceException(f"File not found: {file_path}")

    except Exception as exc:
        logger.error(
            f"Unexpected error verifying document_id={document_id}: {exc}",
            exc_info=True,
        )
        raise


@shared_task(
    bind=True,
    max_retries=2,
    autoretry_for=(AIServiceException,),
    retry_backoff=True,
    retry_backoff_max=300,
)
def detect_fraud_task(
    self,
    case_id: str,
    application_data: dict,
):
    """
    Asynchronously detect fraud for a case.

    Args:
        case_id: Case ID for tracking
        application_data: Dictionary containing application information

    Returns:
        Dictionary containing fraud detection results

    Example:
        from ai_ml_services.utils.tasks import detect_fraud_task

        detect_fraud_task.delay(
            case_id='APP-001',
            application_data= {...}
        )
    """
    logger.info(f"Starting fraud detection for case={case_id}")

    try:
        result = detect_fraud(application_data)

        logger.info(
            f"Fraud detection completed for case={case_id}: "
            f"is_fraud={result['is_fraud']}, "
            f"probability={result['fraud_probability']:.2f}, "
            f"risk_level={result['risk_level']}"
        )

        return {
            "success": True,
            "case_id": case_id,
            "result": result,
        }

    except AIServiceException as exc:
        logger.error(
            f"AI service error for fraud detection case={case_id}: {exc}", exc_info=True
        )
        raise

    except Exception as exc:
        logger.error(
            f"Unexpected error detecting fraud for case={case_id}: {exc}", exc_info=True
        )
        raise


@shared_task(
    bind=True,
    max_retries=1,
)
def check_consistency_task(
    self,
    case_id: str,
    documents: list,
):
    """
    Asynchronously check consistency across documents.

    Args:
        case_id: Case ID for tracking
        documents: List of document dictionaries with 'text' and 'document_type'

    Returns:
        Dictionary containing consistency check results

    Example:
        from ai_ml_services.utils.tasks import check_consistency_task

        check_consistency_task.delay(
            case_id='APP-001',
            documents=[
                {'text': 'John Doe...', 'document_type': 'id_card'},
                {'text': 'John Doe...', 'document_type': 'passport'},
            ]
        )
    """
    logger.info(
        f"Starting consistency check for case={case_id} ({len(documents)} documents)"
    )

    try:
        result = check_consistency(documents)

        logger.info(
            f"Consistency check completed for case={case_id}: "
            f"consistent={result['overall_consistent']}, "
            f"score={result['overall_score']:.2f}"
        )

        return {
            "success": True,
            "case_id": case_id,
            "result": result,
        }

    except AIServiceException as exc:
        logger.error(
            f"AI service error for consistency check case={case_id}: {exc}",
            exc_info=True,
        )
        raise

    except Exception as exc:
        logger.error(
            f"Unexpected error checking consistency for case={case_id}: {exc}",
            exc_info=True,
        )
        raise


@shared_task(
    bind=True,
    max_retries=2,
    autoretry_for=(AIServiceException,),
    retry_backoff=True,
    retry_backoff_max=600,
)
def batch_verify_documents_task(
    self,
    case_id: str,
    documents: list,
    default_document_type: str = None,
):
    """
    Asynchronously verify multiple documents for a case.

    Args:
        case_id: Case ID for tracking
        documents: List of dictionaries with 'file_path' and optionally 'document_type'
        default_document_type: Default document type if not specified per document

    Returns:
        Dictionary containing batch verification results

    Example:
        from ai_ml_services.utils.tasks import batch_verify_documents_task

        batch_verify_documents_task.delay(
            case_id='APP-001',
            documents=[
                {'file_path': '/path/to/id.jpg', 'document_type': 'id_card'},
                {'file_path': '/path/to/passport.pdf', 'document_type': 'passport'},
            ]
        )
    """
    logger.info(
        f"Starting batch document verification for case={case_id} "
        f"({len(documents)} documents)"
    )

    try:
        file_paths = [doc.get("file_path") for doc in documents]

        result = batch_verify_documents(
            file_paths=file_paths,
            document_type=default_document_type,
            case_id=case_id,
        )

        logger.info(
            f"Batch verification completed for case={case_id}: "
            f"{result['total_documents']}/{len(documents)} processed successfully"
        )

        return {
            "success": True,
            "case_id": case_id,
            "result": result,
        }

    except AIServiceException as exc:
        logger.error(
            f"AI service error for batch verification case={case_id}: {exc}",
            exc_info=True,
        )
        raise

    except Exception as exc:
        logger.error(
            f"Unexpected error in batch verification for case={case_id}: {exc}",
            exc_info=True,
        )
        raise


@shared_task
def health_check_task():
    """
    Health check for AI/ML services.

    Returns:
        Dictionary with service status

    Example:
        from ai_ml_services.utils.tasks import health_check_task

        result = health_check_task.delay()
    """
    try:
        from ai_ml_services.service import get_ai_service

        orchestrator = get_ai_service()

        status = "healthy"
        details = {}

        try:
            orchestrator.ocr_service.extract_text_tesseract.__name__
            details["ocr"] = "operational"
        except Exception:
            details["ocr"] = "not_available"
            status = "degraded"

        try:
            model = getattr(orchestrator.authenticity_detector, "model", None)
            if model is None:
                details["authenticity"] = "degraded_model_missing"
                status = "degraded"
            else:
                details["authenticity"] = "operational"
        except Exception:
            details["authenticity"] = "not_available"
            status = "degraded"

        try:
            detector = orchestrator.fraud_detector
            _predict = detector.predict_fraud
            model = getattr(detector, "model", None)
            scaler = getattr(detector, "scaler", None)
            if model is None or scaler is None or not hasattr(scaler, "mean_"):
                details["fraud_detection"] = "degraded_heuristic_mode"
                status = "degraded"
            else:
                details["fraud_detection"] = "operational"
        except Exception:
            details["fraud_detection"] = "not_available"
            status = "degraded"

        try:
            checker = orchestrator.consistency_checker
            if getattr(checker, "nlp", None) is None:
                details["consistency"] = "degraded_nlp_unavailable"
                status = "degraded"
            else:
                details["consistency"] = "operational"
        except Exception:
            details["consistency"] = "not_available"
            status = "degraded"

        return {
            "status": status,
            "services": details,
        }

    except Exception as exc:
        logger.error(f"Health check failed: {exc}", exc_info=True)
        return {
            "status": "unhealthy",
            "error": str(exc),
        }

