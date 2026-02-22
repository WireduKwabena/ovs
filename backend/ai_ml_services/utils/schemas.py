"""Framework-agnostic DTOs for AI/ML service request/response payloads."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class DictSerializable:
    """Simple mixin to expose dataclass payload as dict."""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DocumentVerificationRequest(DictSerializable):
    """Input payload for document verification."""

    case_id: str
    document_type: str
    file_content: bytes


@dataclass
class OCRResult(DictSerializable):
    """OCR extraction output."""

    text: str
    confidence: float
    method: str
    extracted_data: Dict[str, Any] = field(default_factory=dict)
    pages: Optional[int] = 1


@dataclass
class AuthenticityResult(DictSerializable):
    """Document authenticity result."""

    authenticity_score: float
    is_authentic: bool
    confidence: float
    deep_learning_score: float
    cv_checks: Dict[str, Any] = field(
        default_factory=lambda: {
            "metadata": {},
            "copy_move": {},
            "compression": {},
        }
    )


@dataclass
class ConsistencyCheckRequest(DictSerializable):
    """Input payload for cross-document consistency check."""

    documents: List[Dict[str, Any]]


@dataclass
class ConsistencyCheckResponse(DictSerializable):
    """Consistency check output."""

    overall_consistent: bool
    overall_score: float
    name_consistency: Dict[str, Any]
    date_consistency: Dict[str, Any]
    recommendation: str


@dataclass
class FraudDetectionRequest(DictSerializable):
    """Input payload for fraud detection."""

    application_data: Dict[str, Any]


@dataclass
class FraudDetectionResponse(DictSerializable):
    """Fraud detection output."""

    is_fraud: bool
    fraud_probability: float
    anomaly_score: float
    risk_level: str
    confidence: float
    recommendation: str


@dataclass
class DocumentVerificationResponse(DictSerializable):
    """End-to-end document verification response."""

    success: bool
    case_id: str
    document_type: str
    results: Dict[str, Any] = field(
        default_factory=lambda: {
            "ocr": {},
            "authenticity": {},
            "overall_score": 0.0,
            "recommendation": "",
        }
    )
    processing_time: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
