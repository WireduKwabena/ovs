"""
AI/ML Services Module

This module provides AI/ML capabilities for document verification, fraud detection,
and consistency checking. It is designed as a service layer that other Django apps
can import and use directly.
"""

from ai_ml_services.document_classification import (
    DocumentFeatureExtractor,
    DocumentTypeClassifier,
)
from ai_ml_services.service import (
    AIOrchestrator,
    AIServiceException,
    batch_verify_documents,
    check_consistency,
    check_social_profiles,
    classify_document,
    detect_fraud,
    get_ai_service,
    verify_document,
)

__all__ = [
    "AIServiceException",
    "AIOrchestrator",
    "get_ai_service",
    "verify_document",
    "check_consistency",
    "detect_fraud",
    "check_social_profiles",
    "batch_verify_documents",
    "classify_document",
    "DocumentFeatureExtractor",
    "DocumentTypeClassifier",
]
