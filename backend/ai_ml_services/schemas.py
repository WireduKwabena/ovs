"""Backward-compatible schema exports.

Canonical dataclasses live in ``ai_ml_services.utils.schemas``.
"""

from ai_ml_services.utils.schemas import (
    AuthenticityResult,
    ConsistencyCheckRequest,
    ConsistencyCheckResponse,
    DictSerializable,
    DocumentVerificationRequest,
    DocumentVerificationResponse,
    FraudDetectionRequest,
    FraudDetectionResponse,
    OCRResult,
)

__all__ = [
    "DictSerializable",
    "DocumentVerificationRequest",
    "OCRResult",
    "AuthenticityResult",
    "ConsistencyCheckRequest",
    "ConsistencyCheckResponse",
    "FraudDetectionRequest",
    "FraudDetectionResponse",
    "DocumentVerificationResponse",
]
