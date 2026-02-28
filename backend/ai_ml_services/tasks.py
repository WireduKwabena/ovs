"""Backward-compatible task exports.

Canonical task implementations now live in ``ai_ml_services.utils.tasks``.
"""

from ai_ml_services.utils.tasks import (
    batch_verify_documents_task,
    check_consistency_task,
    check_social_profiles_task,
    detect_fraud_task,
    health_check_task,
    verify_document_task,
)

__all__ = [
    "verify_document_task",
    "detect_fraud_task",
    "check_social_profiles_task",
    "check_consistency_task",
    "batch_verify_documents_task",
    "health_check_task",
]

