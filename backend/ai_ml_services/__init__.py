"""
AI/ML Services Module

This module provides AI/ML capabilities for document verification, fraud detection,
and consistency checking. It is designed as a service layer that other Django apps
can import and use directly.

Example usage:
    from ai_ml_services import verify_document, detect_fraud, check_consistency

    # Verify a document
    result = verify_document(
        file_path='/path/to/document.pdf',
        document_type='id_card',
        case_id='APP-123'
    )

    # Detect fraud
    fraud_result = detect_fraud(application_data)

    # Check consistency across documents
    consistency_result = check_consistency(documents)
"""

from ai_ml_services.service import (
    AIServiceException,
    AIOrchestrator,
    batch_verify_documents,
    classify_document,
    check_consistency,
    detect_fraud,
    get_ai_service,
    verify_document,
)
from ai_ml_services.document_classification import (
    DocumentFeatureExtractor,
    DocumentTypeClassifier,
)

__all__ = [
    "AIServiceException",
    "AIOrchestrator",
    "get_ai_service",
    "verify_document",
    "check_consistency",
    "detect_fraud",
    "batch_verify_documents",
    "classify_document",
    "DocumentFeatureExtractor",
    "DocumentTypeClassifier",
]

