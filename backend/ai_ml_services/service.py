"""High-level service API for AI/ML operations.

This module provides a clean, simple interface for other Django apps to interact
with the AI/ML services without needing to know implementation details.
"""

import logging
import os
import time
from pathlib import Path
from typing import Dict, List, Optional

from django.conf import settings

from ai_ml_services.utils.pdf import pdf2image_kwargs

logger = logging.getLogger(__name__)

APPROVAL_THRESHOLD = float(getattr(settings, "AI_ML_APPROVAL_THRESHOLD", 85))
MANUAL_REVIEW_THRESHOLD = float(getattr(settings, "AI_ML_MANUAL_REVIEW_THRESHOLD", 70))
RECOMMENDATION_APPROVE = "APPROVE"
RECOMMENDATION_MANUAL_REVIEW = "MANUAL_REVIEW"
RECOMMENDATION_REJECT = "REJECT"


class AIServiceException(Exception):
    """Raised when an AI/ML orchestration flow fails."""


class AIOrchestrator:
    """Main orchestrator for AI/ML services."""

    @staticmethod
    def _resolve_path(raw_path: str) -> Path:
        path = Path(str(raw_path))
        if not path.is_absolute():
            path = Path(settings.BASE_DIR) / path
        return path

    @staticmethod
    def _is_signature_document(document_type: str) -> bool:
        normalized = str(document_type or "").strip().lower().replace("-", "_")
        return "signature" in normalized or "signed" in normalized

    def __init__(self):
        from ai_ml_services.authenticity.authenticity_detector import (
            AuthenticityDetector,
        )
        from ai_ml_services.authenticity.cv_detector import (
            CVAuthenticityDetector,
        )
        from ai_ml_services.authenticity.consistency_checker import (
            ConsistencyChecker,
        )
        from ai_ml_services.fraud.fraud_detector import FraudDetector
        from ai_ml_services.ocr.ocr_service import OCRService
        from ai_ml_services.signature.signature_detector import (
            SignatureAuthenticityDetector,
        )

        authenticity_model_path = self._resolve_path(
            str(
                getattr(
                    settings,
                    "AI_ML_AUTHENTICITY_MODEL_PATH",
                    settings.MODEL_PATH / "authenticity_best.h5",
                )
            )
        )
        fraud_model_path = self._resolve_path(
            str(
                getattr(
                    settings,
                    "AI_ML_FRAUD_MODEL_PATH",
                    settings.MODEL_PATH / "fraud_classifier.pkl",
                )
            )
        )
        signature_model_path = self._resolve_path(
            str(
                getattr(
                    settings,
                    "AI_ML_SIGNATURE_MODEL_PATH",
                    settings.MODEL_PATH / "signature_authenticity.pkl",
                )
            )
        )

        self.ocr_service = OCRService()
        self.authenticity_detector = AuthenticityDetector(
            model_path=str(authenticity_model_path)
        )
        self.cv_detector = CVAuthenticityDetector()
        self.consistency_checker = ConsistencyChecker()
        self.fraud_detector = FraudDetector(
            model_path=str(fraud_model_path) if fraud_model_path.exists() else None
        )
        self.signature_detector = SignatureAuthenticityDetector(
            model_path=str(signature_model_path)
        )
        if not fraud_model_path.exists():
            logger.warning(
                "Fraud model artifact not found at %s; heuristic mode will be used.",
                fraud_model_path,
            )

        logger.info("AI service orchestrator initialized")

    @staticmethod
    def _apply_threshold_recommendation(score: float) -> str:
        if score >= APPROVAL_THRESHOLD:
            return RECOMMENDATION_APPROVE
        if score >= MANUAL_REVIEW_THRESHOLD:
            return RECOMMENDATION_MANUAL_REVIEW
        return RECOMMENDATION_REJECT

    @staticmethod
    def _contains_error(payload: Dict) -> bool:
        return isinstance(payload, dict) and bool(payload.get("error"))

    def verify_document(
        self, file_path: str, document_type: str, case_id: Optional[str] = None
    ) -> Dict:
        """
        Verify a document for authenticity.

        Args:
            file_path: Path to the document file
            document_type: Type of document (id_card, passport, certificate, etc.)
            case_id: Optional case ID for logging/traceability

        Returns:
            Dictionary containing verification results with keys:
            - success: bool
            - results: dict with ocr, authenticity, overall_score, recommendation
            - processing_time: float

        Raises:
            AIServiceException: If verification fails
        """
        start_time = time.time()
        case_id = case_id or "unknown"

        logger.info(f"Starting document verification for case {case_id}")

        try:
            decision_constraints: List[Dict[str, str]] = []
            is_pdf = file_path.lower().endswith(".pdf")
            if is_pdf:
                ocr_result = self.ocr_service.extract_from_pdf(file_path)
            else:
                ocr_result = self.ocr_service.extract_structured_data(
                    file_path, document_type
                )

            import cv2

            image = None
            signature_result = None
            if is_pdf:
                try:
                    from pdf2image import convert_from_path

                    pages = convert_from_path(
                        file_path,
                        first_page=1,
                        last_page=1,
                        **pdf2image_kwargs(),
                    )
                    if pages:
                        import numpy as np

                        image = cv2.cvtColor(np.array(pages[0]), cv2.COLOR_RGB2BGR)
                except Exception as exc:
                    logger.warning(
                        "Could not rasterize PDF for CV checks (%s): %s", file_path, exc
                    )
            else:
                image = cv2.imread(file_path)
                if image is None:
                    raise ValueError(f"Failed to read image from {file_path}")

            if image is not None:
                dl_authenticity = self.authenticity_detector.predict(image)
                cv_checks = {
                    "metadata": self.cv_detector.check_metadata(file_path),
                    "copy_move": self.cv_detector.detect_copy_move(image),
                    "compression": self.cv_detector.check_compression_artifacts(image),
                }
                if self._is_signature_document(document_type):
                    signature_result = self.signature_detector.predict(image)
                    if signature_result.get("mode") != "model":
                        decision_constraints.append(
                            {
                                "code": "signature_model_unavailable",
                                "reason": "Signature model is unavailable; fallback heuristics were used.",
                            }
                        )
                if dl_authenticity.get("mode") != "model":
                    decision_constraints.append(
                        {
                            "code": "authenticity_model_unavailable",
                            "reason": "Deep-learning authenticity model is unavailable; fallback heuristics were used.",
                        }
                    )
                if any(self._contains_error(check) for check in cv_checks.values()):
                    decision_constraints.append(
                        {
                            "code": "cv_signal_degraded",
                            "reason": "At least one CV authenticity check failed and returned degraded output.",
                        }
                    )
            else:
                logger.warning(
                    "Skipping CV authenticity checks for %s; returning review-required decision.",
                    file_path,
                )
                dl_authenticity = {
                    "authenticity_score": 50.0,
                    "is_authentic": False,
                    "confidence": 0.0,
                    "mode": "unavailable",
                }
                cv_checks = {
                    "metadata": {
                        "suspicious": True,
                        "score": 50.0,
                        "reason": "cv_skipped",
                        "error": "image_unavailable",
                    },
                    "copy_move": {
                        "copy_move_detected": True,
                        "confidence": 0.0,
                        "score": 50.0,
                        "error": "image_unavailable",
                    },
                    "compression": {
                        "suspicious": True,
                        "score": 50.0,
                        "error": "image_unavailable",
                    },
                }
                decision_constraints.append(
                    {
                        "code": "image_unavailable",
                        "reason": "Document image could not be processed for CV/deep-learning authenticity checks.",
                    }
                )
                if self._is_signature_document(document_type):
                    signature_result = {
                        "authenticity_score": 50.0,
                        "is_authentic": False,
                        "confidence": 0.0,
                        "mode": "unavailable",
                    }
                    decision_constraints.append(
                        {
                            "code": "signature_image_unavailable",
                            "reason": "Signature document could not be rasterized for signature checks.",
                        }
                    )

            copy_move_score = (
                100 - cv_checks["copy_move"].get("confidence", 0.0)
                if cv_checks["copy_move"].get("copy_move_detected")
                else 100.0
            )
            metadata_score = cv_checks["metadata"].get(
                "score", 70.0 if cv_checks["metadata"].get("suspicious") else 100.0
            )
            compression_score = cv_checks["compression"].get(
                "score", 75.0 if cv_checks["compression"].get("suspicious") else 100.0
            )

            authenticity_scores = [
                dl_authenticity.get("authenticity_score", 50.0),
                copy_move_score,
                metadata_score,
                compression_score,
            ]
            overall_authenticity = sum(authenticity_scores) / len(authenticity_scores)

            scores = [
                ocr_result.get("confidence", 0),
                overall_authenticity,
            ]
            if signature_result is not None:
                scores.append(float(signature_result.get("authenticity_score", 50.0)))
            overall_score = sum(scores) / len(scores)

            recommendation = self._apply_threshold_recommendation(overall_score)
            automated_decision_allowed = not decision_constraints
            if decision_constraints and recommendation != RECOMMENDATION_MANUAL_REVIEW:
                logger.warning(
                    "Case %s recommendation changed from %s to MANUAL_REVIEW due to degraded model state.",
                    case_id,
                    recommendation,
                )
                recommendation = RECOMMENDATION_MANUAL_REVIEW

            processing_time = time.time() - start_time
            logger.info(
                f"Document verification completed for case {case_id}: "
                f"score={overall_score:.2f}, recommendation={recommendation}"
            )

            return {
                "success": True,
                "case_id": case_id,
                "document_type": document_type,
                "results": {
                    "ocr": ocr_result,
                    "authenticity": {
                        "overall_score": overall_authenticity,
                        "deep_learning": dl_authenticity,
                        "computer_vision": cv_checks,
                    },
                    "signature": signature_result,
                    "overall_score": overall_score,
                    "recommendation": recommendation,
                    "automated_decision_allowed": automated_decision_allowed,
                    "decision_constraints": decision_constraints,
                },
                "processing_time": processing_time,
            }

        except Exception as e:
            logger.error(
                f"Document verification failed for case {case_id}: {e}", exc_info=True
            )
            raise AIServiceException(f"Document verification failed: {str(e)}")

    def check_consistency(self, documents: List[Dict]) -> Dict:
        """
        Check consistency across multiple documents.

        Args:
            documents: List of document dictionaries with 'text' and 'document_type' keys

        Returns:
            Dictionary containing consistency check results
        """
        logger.info(f"Starting consistency check for {len(documents)} documents")

        try:
            result = self.consistency_checker.verify_all_documents(documents)
            logger.info(
                f"Consistency check completed: consistent={result['overall_consistent']}"
            )
            return result

        except Exception as e:
            logger.error(f"Consistency check failed: {e}", exc_info=True)
            raise AIServiceException(f"Consistency check failed: {str(e)}")

    def detect_fraud(self, application_data: Dict) -> Dict:
        """
        Detect fraud in application data.

        Args:
            application_data: Dictionary containing application information

        Returns:
            Dictionary containing fraud detection results
        """
        logger.info("Starting fraud detection")

        try:
            result = self.fraud_detector.predict_fraud(application_data)
            if result.get("mode") != "model":
                result["recommendation"] = RECOMMENDATION_MANUAL_REVIEW
                result["automated_decision_allowed"] = False
                constraints = list(result.get("decision_constraints") or [])
                constraints.append(
                    {
                        "code": "fraud_model_unavailable",
                        "reason": "Fraud model is unavailable; heuristic signal is advisory only.",
                    }
                )
                result["decision_constraints"] = constraints
            else:
                result["automated_decision_allowed"] = True
            logger.info(
                f"Fraud detection completed: is_fraud={result['is_fraud']}, "
                f"probability={result['fraud_probability']:.2f}"
            )
            return result

        except Exception as e:
            logger.error(f"Fraud detection failed: {e}", exc_info=True)
            raise AIServiceException(f"Fraud detection failed: {str(e)}")

    def batch_verify_documents(
        self,
        file_paths: List[str],
        document_type: Optional[str] = None,
        case_id: Optional[str] = None,
    ) -> Dict:
        """
        Verify multiple documents in batch.

        Args:
            file_paths: List of file paths to verify
            document_type: Optional default document type
            case_id: Optional case ID for logging

        Returns:
            Dictionary containing batch verification results
        """
        case_id = case_id or "batch_verification"
        document_type = document_type or "unknown"
        results = []

        logger.info(
            f"Starting batch verification for {len(file_paths)} documents (case: {case_id})"
        )

        for i, file_path in enumerate(file_paths):
            try:
                result = self.verify_document(
                    file_path, document_type, f"{case_id}_{i}"
                )
                results.append({**result, "filename": os.path.basename(file_path)})

            except Exception as e:
                logger.error(f"Failed to verify {file_path}: {e}")
                results.append(
                    {
                        "success": False,
                        "error": str(e),
                        "filename": os.path.basename(file_path),
                    }
                )

        logger.info(
            f"Batch verification completed: {len(results)}/{len(file_paths)} processed"
        )

        return {
            "success": True,
            "case_id": case_id,
            "total_documents": len(file_paths),
            "results": results,
        }


# Global orchestrator instance
_orchestrator: Optional[AIOrchestrator] = None


def get_ai_service() -> AIOrchestrator:
    """
    Get the global AI orchestrator instance.

    Returns:
        AIOrchestrator instance

    This function creates and caches the orchestrator on first call.
    Subsequent calls return the same instance.
    """
    global _orchestrator

    if _orchestrator is None:
        _orchestrator = AIOrchestrator()

    return _orchestrator


def verify_document(
    file_path: str, document_type: str, case_id: Optional[str] = None
) -> Dict:
    """Convenience function to verify a document."""
    return get_ai_service().verify_document(file_path, document_type, case_id)


def check_consistency(documents: List[Dict]) -> Dict:
    """Convenience function to check document consistency."""
    return get_ai_service().check_consistency(documents)


def detect_fraud(application_data: Dict) -> Dict:
    """Convenience function to detect fraud."""
    return get_ai_service().detect_fraud(application_data)


def batch_verify_documents(
    file_paths: List[str],
    document_type: Optional[str] = None,
    case_id: Optional[str] = None,
) -> Dict:
    """Convenience function to batch verify documents."""
    return get_ai_service().batch_verify_documents(file_paths, document_type, case_id)

