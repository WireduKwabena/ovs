"""High-level service API for AI/ML operations.

This module provides a clean, simple interface for other Django apps to interact
with the AI/ML services without needing to know implementation details.
"""

import logging
import os
import re
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

RVL_DOCUMENT_LABELS = {
    "advertisement",
    "budget",
    "email",
    "file_folder",
    "form",
    "handwritten",
    "invoice",
    "letter",
    "memo",
    "news_article",
    "presentation",
    "questionnaire",
    "resume",
    "scientific_publication",
    "scientific_report",
    "specification",
}

MIDV_FAMILIES = {"passport", "id_card", "driver_license", "social_security"}


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
        from ai_ml_services.document_classification.classifier import (
            DocumentTypeClassifier,
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
        rvl_model_path = self._resolve_path(
            str(
                getattr(
                    settings,
                    "AI_ML_RVL_CDIP_MODEL_PATH",
                    settings.MODEL_PATH / "rvl_cdip_classifier.pkl",
                )
            )
        )
        midv_model_path = self._resolve_path(
            str(
                getattr(
                    settings,
                    "AI_ML_MIDV500_MODEL_PATH",
                    settings.MODEL_PATH / "midv500_classifier.pkl",
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
        self.rvl_document_classifier = DocumentTypeClassifier(model_path=rvl_model_path)
        self.midv_document_classifier = DocumentTypeClassifier(model_path=midv_model_path)
        if not fraud_model_path.exists():
            logger.warning(
                "Fraud model artifact not found at %s; heuristic mode will be used.",
                fraud_model_path,
            )
        if not self.rvl_document_classifier.available:
            logger.warning(
                "RVL document classifier unavailable at %s (%s)",
                rvl_model_path,
                self.rvl_document_classifier.error,
            )
        if not self.midv_document_classifier.available:
            logger.warning(
                "MIDV document classifier unavailable at %s (%s)",
                midv_model_path,
                self.midv_document_classifier.error,
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

    @staticmethod
    def _normalize_text_token(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "_", str(value or "").lower()).strip("_")

    def _expected_document_profile(self, document_type: str) -> Dict[str, str]:
        normalized = self._normalize_text_token(document_type)
        tokens = [token for token in normalized.split("_") if token]
        token_set = set(tokens)

        if normalized in RVL_DOCUMENT_LABELS:
            return {"domain": "rvl", "label": normalized}

        if {"resume", "cv"}.intersection(token_set):
            return {"domain": "rvl", "label": "resume"}
        if {"invoice"}.intersection(token_set):
            return {"domain": "rvl", "label": "invoice"}
        if {"letter"}.intersection(token_set):
            return {"domain": "rvl", "label": "letter"}
        if {"form"}.intersection(token_set):
            return {"domain": "rvl", "label": "form"}

        if {"passport", "passportcard", "travel"}.intersection(token_set):
            return {"domain": "midv500", "family": "passport"}
        if {"driver", "drivers", "driving", "license", "licence", "drvlic"}.intersection(token_set):
            return {"domain": "midv500", "family": "driver_license"}
        if {"ssn", "social", "security"}.issubset(token_set) or {"ssn"}.intersection(token_set):
            return {"domain": "midv500", "family": "social_security"}
        if {"id", "identity", "national"}.intersection(token_set):
            return {"domain": "midv500", "family": "id_card"}

        return {"domain": "unknown", "label": normalized}

    def _midv_family_from_label(self, predicted_label: str) -> str:
        normalized = self._normalize_text_token(predicted_label)
        if "passport" in normalized:
            return "passport"
        if "drvlic" in normalized or "driver" in normalized:
            return "driver_license"
        if "ssn" in normalized or "social_security" in normalized:
            return "social_security"
        if normalized.endswith("_id") or "_id_" in normalized or normalized == "id":
            return "id_card"
        return "unknown"

    @staticmethod
    def _get_doc_type_mismatch_threshold() -> float:
        threshold = float(getattr(settings, "AI_ML_DOC_TYPE_MISMATCH_CONFIDENCE", 0.65))
        return min(1.0, max(0.0, threshold))

    @staticmethod
    def _doc_type_mismatch_enabled() -> bool:
        return bool(getattr(settings, "AI_ML_DOC_TYPE_MISMATCH_ENABLED", True))

    def _evaluate_document_type_alignment(
        self,
        declared_document_type: str,
        classification: Dict[str, Dict],
    ) -> Dict:
        if not self._doc_type_mismatch_enabled():
            return {
                "enabled": False,
                "declared_document_type": declared_document_type,
                "mismatch_detected": False,
                "mismatch_reason": "",
                "details": [],
            }

        expected = self._expected_document_profile(declared_document_type)
        threshold = self._get_doc_type_mismatch_threshold()
        details: List[Dict[str, str]] = []

        rvl_result = classification.get("rvl_cdip") or {}
        midv_result = classification.get("midv500") or {}
        rvl_label = self._normalize_text_token(rvl_result.get("predicted_label", ""))
        midv_label = self._normalize_text_token(midv_result.get("predicted_label", ""))
        rvl_conf = float(rvl_result.get("confidence", 0.0) or 0.0)
        midv_conf = float(midv_result.get("confidence", 0.0) or 0.0)

        if expected.get("domain") == "midv500":
            expected_family = expected.get("family", "")
            predicted_family = self._midv_family_from_label(midv_label)
            if (
                midv_result.get("available")
                and midv_conf >= threshold
                and predicted_family in MIDV_FAMILIES
                and predicted_family != expected_family
            ):
                details.append(
                    {
                        "model": "midv500",
                        "reason": (
                            f"Declared type expects `{expected_family}` but MIDV predicted "
                            f"`{predicted_family}` (label={midv_label}, confidence={midv_conf:.3f})."
                        ),
                    }
                )

            if (
                rvl_result.get("available")
                and rvl_conf >= threshold
                and rvl_label in RVL_DOCUMENT_LABELS
            ):
                details.append(
                    {
                        "model": "rvl_cdip",
                        "reason": (
                            f"Declared ID-like type but RVL predicted non-ID class "
                            f"`{rvl_label}` (confidence={rvl_conf:.3f})."
                        ),
                    }
                )

        if expected.get("domain") == "rvl":
            expected_label = expected.get("label", "")
            if (
                rvl_result.get("available")
                and rvl_conf >= threshold
                and rvl_label
                and rvl_label != expected_label
            ):
                details.append(
                    {
                        "model": "rvl_cdip",
                        "reason": (
                            f"Declared type expects `{expected_label}` but RVL predicted "
                            f"`{rvl_label}` (confidence={rvl_conf:.3f})."
                        ),
                    }
                )
            if (
                midv_result.get("available")
                and midv_conf >= threshold
                and self._midv_family_from_label(midv_label) in MIDV_FAMILIES
            ):
                details.append(
                    {
                        "model": "midv500",
                        "reason": (
                            f"Declared non-ID type but MIDV predicted ID family "
                            f"`{self._midv_family_from_label(midv_label)}` "
                            f"(label={midv_label}, confidence={midv_conf:.3f})."
                        ),
                    }
                )

        mismatch_detected = len(details) > 0
        mismatch_reason = (
            "Declared document type does not align with classifier prediction."
            if mismatch_detected
            else ""
        )

        return {
            "enabled": True,
            "declared_document_type": declared_document_type,
            "expected": expected,
            "confidence_threshold": threshold,
            "mismatch_detected": mismatch_detected,
            "mismatch_reason": mismatch_reason,
            "details": details,
        }

    def _classify_document_image(self, image, top_k: int = 3) -> Dict[str, Dict]:
        if image is None:
            return {
                "rvl_cdip": {
                    "available": bool(
                        getattr(self, "rvl_document_classifier", None)
                        and self.rvl_document_classifier.available
                    ),
                    "error": "image_unavailable",
                },
                "midv500": {
                    "available": bool(
                        getattr(self, "midv_document_classifier", None)
                        and self.midv_document_classifier.available
                    ),
                    "error": "image_unavailable",
                },
            }

        result: Dict[str, Dict] = {}
        rvl_classifier = getattr(self, "rvl_document_classifier", None)
        midv_classifier = getattr(self, "midv_document_classifier", None)

        if rvl_classifier is not None:
            result["rvl_cdip"] = rvl_classifier.predict_image(image, top_k=top_k)
        else:
            result["rvl_cdip"] = {"available": False, "error": "classifier_not_initialized"}

        if midv_classifier is not None:
            result["midv500"] = midv_classifier.predict_image(image, top_k=top_k)
        else:
            result["midv500"] = {"available": False, "error": "classifier_not_initialized"}

        return result

    def classify_document_image(
        self,
        image,
        document_type: Optional[str] = None,
        top_k: int = 3,
    ) -> Dict:
        classification = self._classify_document_image(image=image, top_k=top_k)
        alignment = self._evaluate_document_type_alignment(
            declared_document_type=document_type or "",
            classification=classification,
        )
        return {
            "document_classification": classification,
            "document_type_alignment": alignment,
        }

    def classify_document(
        self,
        file_path: str,
        document_type: Optional[str] = None,
        top_k: int = 3,
    ) -> Dict:
        import cv2

        image = None
        if str(file_path).lower().endswith(".pdf"):
            from pdf2image import convert_from_path

            pages = convert_from_path(
                str(file_path),
                first_page=1,
                last_page=1,
                **pdf2image_kwargs(),
            )
            if pages:
                import numpy as np

                image = cv2.cvtColor(np.array(pages[0]), cv2.COLOR_RGB2BGR)
        else:
            image = cv2.imread(str(file_path))

        if image is None:
            raise AIServiceException(f"Could not decode document image: {file_path}")

        return self.classify_document_image(
            image=image,
            document_type=document_type,
            top_k=top_k,
        )

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

            document_classification = self._classify_document_image(image=image, top_k=3)
            document_type_alignment = self._evaluate_document_type_alignment(
                declared_document_type=document_type,
                classification=document_classification,
            )
            if document_type_alignment.get("mismatch_detected"):
                decision_constraints.append(
                    {
                        "code": "document_type_mismatch",
                        "reason": document_type_alignment.get(
                            "mismatch_reason",
                            "Declared document type does not align with model predictions.",
                        ),
                        "details": document_type_alignment.get("details", []),
                    }
                )

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
                    "document_classification": document_classification,
                    "document_type_alignment": document_type_alignment,
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


def classify_document(
    file_path: str,
    document_type: Optional[str] = None,
    top_k: int = 3,
) -> Dict:
    """Convenience function to classify a document file."""
    return get_ai_service().classify_document(
        file_path=file_path,
        document_type=document_type,
        top_k=top_k,
    )

