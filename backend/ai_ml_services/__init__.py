"""
AI/ML Services module.

Keep package imports lightweight so Django startup does not require optional
ML dependencies (for example OpenCV) unless a specific AI function is used.
"""

from __future__ import annotations

from typing import Any

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


def get_ai_service(*args: Any, **kwargs: Any):
    from ai_ml_services.service import get_ai_service as _get_ai_service

    return _get_ai_service(*args, **kwargs)


def verify_document(*args: Any, **kwargs: Any):
    from ai_ml_services.service import verify_document as _verify_document

    return _verify_document(*args, **kwargs)


def check_consistency(*args: Any, **kwargs: Any):
    from ai_ml_services.service import check_consistency as _check_consistency

    return _check_consistency(*args, **kwargs)


def detect_fraud(*args: Any, **kwargs: Any):
    from ai_ml_services.service import detect_fraud as _detect_fraud

    return _detect_fraud(*args, **kwargs)


def check_social_profiles(*args: Any, **kwargs: Any):
    from ai_ml_services.service import check_social_profiles as _check_social_profiles

    return _check_social_profiles(*args, **kwargs)


def batch_verify_documents(*args: Any, **kwargs: Any):
    from ai_ml_services.service import batch_verify_documents as _batch_verify_documents

    return _batch_verify_documents(*args, **kwargs)


def classify_document(*args: Any, **kwargs: Any):
    from ai_ml_services.service import classify_document as _classify_document

    return _classify_document(*args, **kwargs)


def __getattr__(name: str):
    if name in {"AIOrchestrator", "AIServiceException"}:
        from ai_ml_services import service as _service

        return getattr(_service, name)

    if name in {"DocumentFeatureExtractor", "DocumentTypeClassifier"}:
        from ai_ml_services import document_classification as _doc_cls

        return getattr(_doc_cls, name)

    raise AttributeError(f"module 'ai_ml_services' has no attribute '{name}'")
