"""Unit tests for ai_ml_services service API."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings
try:
    import numpy as np
except ModuleNotFoundError:  # pragma: no cover - optional ML extras
    np = None

from ai_ml_services.service import (
    AIOrchestrator,
    AIServiceException,
    batch_verify_documents,
    classify_document,
    check_consistency,
    check_social_profiles,
    detect_fraud,
    get_ai_service,
    verify_document,
)


class TestAIServiceException(SimpleTestCase):
    def test_exception_message(self):
        with self.assertRaises(AIServiceException) as ctx:
            raise AIServiceException("boom")
        self.assertEqual(str(ctx.exception), "boom")


class TestServiceDelegation(SimpleTestCase):
    @patch("ai_ml_services.service.get_ai_service")
    def test_verify_document_delegates_to_orchestrator(self, mock_get_service):
        orchestrator = MagicMock()
        orchestrator.verify_document.return_value = {"success": True}
        mock_get_service.return_value = orchestrator

        result = verify_document("file.jpg", "id_card", "CASE-1")

        orchestrator.verify_document.assert_called_once_with(
            "file.jpg", "id_card", "CASE-1"
        )
        self.assertEqual(result, {"success": True})

    @patch("ai_ml_services.service.get_ai_service")
    def test_check_consistency_delegates_to_orchestrator(self, mock_get_service):
        orchestrator = MagicMock()
        orchestrator.check_consistency.return_value = {"overall_score": 88.0}
        mock_get_service.return_value = orchestrator

        documents = [{"text": "John Doe", "document_type": "id_card"}]
        result = check_consistency(documents)

        orchestrator.check_consistency.assert_called_once_with(documents)
        self.assertEqual(result["overall_score"], 88.0)

    @patch("ai_ml_services.service.get_ai_service")
    def test_detect_fraud_delegates_to_orchestrator(self, mock_get_service):
        orchestrator = MagicMock()
        orchestrator.detect_fraud.return_value = {"is_fraud": False}
        mock_get_service.return_value = orchestrator

        payload = {"email": "a@example.com"}
        result = detect_fraud(payload)

        orchestrator.detect_fraud.assert_called_once_with(payload)
        self.assertFalse(result["is_fraud"])

    @patch("ai_ml_services.service.get_ai_service")
    def test_check_social_profiles_delegates_to_orchestrator(self, mock_get_service):
        orchestrator = MagicMock()
        orchestrator.check_social_profiles.return_value = {"overall_score": 72.5}
        mock_get_service.return_value = orchestrator

        profiles = [{"platform": "linkedin", "url": "https://linkedin.com/in/sample"}]
        result = check_social_profiles(
            profiles=profiles,
            consent_provided=True,
            case_id="CASE-SOC-1",
        )

        orchestrator.check_social_profiles.assert_called_once_with(
            profiles=profiles,
            consent_provided=True,
            case_id="CASE-SOC-1",
        )
        self.assertEqual(result["overall_score"], 72.5)

    @patch("ai_ml_services.service.get_ai_service", side_effect=ModuleNotFoundError("No module named 'cv2'"))
    def test_check_social_profiles_falls_back_when_optional_dependency_missing(self, _mock_get_service):
        profiles = [{"platform": "linkedin", "url": "https://linkedin.com/in/sample"}]

        result = check_social_profiles(
            profiles=profiles,
            consent_provided=True,
            case_id="CASE-SOC-FALLBACK",
        )

        self.assertEqual(result["recommendation"], "MANUAL_REVIEW")
        self.assertFalse(result["automated_decision_allowed"])
        self.assertEqual(result["profiles_checked"], 1)
        self.assertEqual(result["case_id"], "CASE-SOC-FALLBACK")

    @patch("ai_ml_services.service.get_ai_service")
    def test_batch_verify_documents_delegates_to_orchestrator(self, mock_get_service):
        orchestrator = MagicMock()
        orchestrator.batch_verify_documents.return_value = {"total_documents": 2}
        mock_get_service.return_value = orchestrator

        result = batch_verify_documents(["a.jpg", "b.jpg"], "id_card", "CASE-2")

        orchestrator.batch_verify_documents.assert_called_once_with(
            ["a.jpg", "b.jpg"], "id_card", "CASE-2"
        )
        self.assertEqual(result["total_documents"], 2)

    @patch("ai_ml_services.service.get_ai_service")
    def test_classify_document_delegates_to_orchestrator(self, mock_get_service):
        orchestrator = MagicMock()
        orchestrator.classify_document.return_value = {
            "document_classification": {"rvl_cdip": {"predicted_label": "invoice"}}
        }
        mock_get_service.return_value = orchestrator

        result = classify_document("file.jpg", "invoice", top_k=3)

        orchestrator.classify_document.assert_called_once_with(
            file_path="file.jpg",
            document_type="invoice",
            top_k=3,
        )
        self.assertIn("document_classification", result)

    @patch("ai_ml_services.service.AIOrchestrator")
    def test_get_ai_service_singleton(self, mock_orchestrator_cls):
        from ai_ml_services import service as service_module

        service_module._orchestrator = None
        mock_instance = MagicMock()
        mock_orchestrator_cls.return_value = mock_instance

        first = get_ai_service()
        second = get_ai_service()

        self.assertIs(first, second)
        mock_orchestrator_cls.assert_called_once()


@unittest.skipUnless(np is not None, "Optional dependency missing for AI service orchestration tests: numpy")
class TestOrchestratorHardening(SimpleTestCase):
    @patch("cv2.imread")
    def test_verify_document_forces_manual_review_when_fallback_mode(self, mock_imread):
        orchestrator = AIOrchestrator.__new__(AIOrchestrator)
        orchestrator.ocr_service = MagicMock()
        orchestrator.authenticity_detector = MagicMock()
        orchestrator.cv_detector = MagicMock()

        mock_imread.return_value = np.zeros((32, 32, 3), dtype=np.uint8)
        orchestrator.ocr_service.extract_structured_data.return_value = {"confidence": 99.0}
        orchestrator.authenticity_detector.predict.return_value = {
            "authenticity_score": 96.0,
            "is_authentic": True,
            "confidence": 90.0,
            "mode": "fallback",
        }
        orchestrator.cv_detector.check_metadata.return_value = {
            "suspicious": False,
            "score": 100.0,
        }
        orchestrator.cv_detector.detect_copy_move.return_value = {
            "copy_move_detected": False,
            "confidence": 0.0,
            "score": 100.0,
        }
        orchestrator.cv_detector.check_compression_artifacts.return_value = {
            "suspicious": False,
            "score": 100.0,
        }

        result = AIOrchestrator.verify_document(
            orchestrator,
            file_path="sample.jpg",
            document_type="id_card",
            case_id="CASE-STRICT-1",
        )

        self.assertEqual(result["results"]["recommendation"], "MANUAL_REVIEW")
        self.assertFalse(result["results"]["automated_decision_allowed"])
        codes = {
            item["code"] for item in result["results"]["decision_constraints"]
        }
        self.assertIn("authenticity_model_unavailable", codes)

    def test_detect_fraud_forces_manual_review_when_model_is_not_ready(self):
        orchestrator = AIOrchestrator.__new__(AIOrchestrator)
        orchestrator.fraud_detector = MagicMock()
        orchestrator.fraud_detector.predict_fraud.return_value = {
            "is_fraud": False,
            "is_fraudulent": False,
            "fraud_probability": 22.0,
            "risk_level": "low",
            "recommendation": "APPROVE",
            "mode": "heuristic",
        }

        result = AIOrchestrator.detect_fraud(orchestrator, {"email": "a@example.com"})

        self.assertEqual(result["recommendation"], "MANUAL_REVIEW")
        self.assertFalse(result["automated_decision_allowed"])
        codes = {item["code"] for item in result["decision_constraints"]}
        self.assertIn("fraud_model_unavailable", codes)

    @patch("cv2.imread")
    def test_verify_document_includes_signature_result_for_signature_docs(self, mock_imread):
        orchestrator = AIOrchestrator.__new__(AIOrchestrator)
        orchestrator.ocr_service = MagicMock()
        orchestrator.authenticity_detector = MagicMock()
        orchestrator.cv_detector = MagicMock()
        orchestrator.signature_detector = MagicMock()

        mock_imread.return_value = np.zeros((32, 32, 3), dtype=np.uint8)
        orchestrator.ocr_service.extract_structured_data.return_value = {"confidence": 80.0}
        orchestrator.authenticity_detector.predict.return_value = {
            "authenticity_score": 60.0,
            "is_authentic": True,
            "confidence": 70.0,
            "mode": "model",
        }
        orchestrator.cv_detector.check_metadata.return_value = {
            "suspicious": False,
            "score": 100.0,
        }
        orchestrator.cv_detector.detect_copy_move.return_value = {
            "copy_move_detected": False,
            "confidence": 0.0,
            "score": 100.0,
        }
        orchestrator.cv_detector.check_compression_artifacts.return_value = {
            "suspicious": False,
            "score": 100.0,
        }
        orchestrator.signature_detector.predict.return_value = {
            "authenticity_score": 82.0,
            "is_authentic": True,
            "confidence": 64.0,
            "mode": "model",
        }

        result = AIOrchestrator.verify_document(
            orchestrator,
            file_path="signature.png",
            document_type="signature",
            case_id="CASE-SIGN-1",
        )

        self.assertEqual(result["results"]["signature"]["authenticity_score"], 82.0)
        self.assertAlmostEqual(result["results"]["overall_score"], 84.0, places=2)

    @patch("cv2.imread")
    def test_verify_document_includes_document_classification_results(self, mock_imread):
        orchestrator = AIOrchestrator.__new__(AIOrchestrator)
        orchestrator.ocr_service = MagicMock()
        orchestrator.authenticity_detector = MagicMock()
        orchestrator.cv_detector = MagicMock()
        orchestrator.rvl_document_classifier = MagicMock()
        orchestrator.midv_document_classifier = MagicMock()

        mock_imread.return_value = np.zeros((32, 32, 3), dtype=np.uint8)
        orchestrator.ocr_service.extract_structured_data.return_value = {"confidence": 80.0}
        orchestrator.authenticity_detector.predict.return_value = {
            "authenticity_score": 60.0,
            "is_authentic": True,
            "confidence": 70.0,
            "mode": "model",
        }
        orchestrator.cv_detector.check_metadata.return_value = {
            "suspicious": False,
            "score": 100.0,
        }
        orchestrator.cv_detector.detect_copy_move.return_value = {
            "copy_move_detected": False,
            "confidence": 0.0,
            "score": 100.0,
        }
        orchestrator.cv_detector.check_compression_artifacts.return_value = {
            "suspicious": False,
            "score": 100.0,
        }
        orchestrator.rvl_document_classifier.predict_image.return_value = {
            "available": True,
            "predicted_label": "invoice",
            "confidence": 0.9,
            "top_k": [{"label": "invoice", "score": 0.9}],
        }
        orchestrator.midv_document_classifier.predict_image.return_value = {
            "available": True,
            "predicted_label": "usa_passportcard",
            "confidence": 0.7,
            "top_k": [{"label": "usa_passportcard", "score": 0.7}],
        }

        result = AIOrchestrator.verify_document(
            orchestrator,
            file_path="doc.png",
            document_type="id_card",
            case_id="CASE-CLS-1",
        )

        self.assertIn("document_classification", result["results"])
        self.assertEqual(
            result["results"]["document_classification"]["rvl_cdip"]["predicted_label"],
            "invoice",
        )
        self.assertEqual(
            result["results"]["document_classification"]["midv500"]["predicted_label"],
            "usa_passportcard",
        )

    @override_settings(
        AI_ML_DOC_TYPE_MISMATCH_ENABLED=True,
        AI_ML_DOC_TYPE_MISMATCH_CONFIDENCE=0.6,
    )
    @patch("cv2.imread")
    def test_verify_document_adds_mismatch_constraint_when_doc_type_conflicts(self, mock_imread):
        orchestrator = AIOrchestrator.__new__(AIOrchestrator)
        orchestrator.ocr_service = MagicMock()
        orchestrator.authenticity_detector = MagicMock()
        orchestrator.cv_detector = MagicMock()
        orchestrator.rvl_document_classifier = MagicMock()
        orchestrator.midv_document_classifier = MagicMock()

        mock_imread.return_value = np.zeros((32, 32, 3), dtype=np.uint8)
        orchestrator.ocr_service.extract_structured_data.return_value = {"confidence": 92.0}
        orchestrator.authenticity_detector.predict.return_value = {
            "authenticity_score": 95.0,
            "is_authentic": True,
            "confidence": 90.0,
            "mode": "model",
        }
        orchestrator.cv_detector.check_metadata.return_value = {
            "suspicious": False,
            "score": 100.0,
        }
        orchestrator.cv_detector.detect_copy_move.return_value = {
            "copy_move_detected": False,
            "confidence": 0.0,
            "score": 100.0,
        }
        orchestrator.cv_detector.check_compression_artifacts.return_value = {
            "suspicious": False,
            "score": 100.0,
        }
        orchestrator.rvl_document_classifier.predict_image.return_value = {
            "available": True,
            "predicted_label": "resume",
            "confidence": 0.88,
            "top_k": [{"label": "resume", "score": 0.88}],
        }
        orchestrator.midv_document_classifier.predict_image.return_value = {
            "available": True,
            "predicted_label": "40_srb_id",
            "confidence": 0.91,
            "top_k": [{"label": "40_srb_id", "score": 0.91}],
        }

        result = AIOrchestrator.verify_document(
            orchestrator,
            file_path="doc.png",
            document_type="passport",
            case_id="CASE-MISMATCH-1",
        )

        codes = {item["code"] for item in result["results"]["decision_constraints"]}
        self.assertIn("document_type_mismatch", codes)
        self.assertEqual(result["results"]["recommendation"], "MANUAL_REVIEW")
        self.assertTrue(result["results"]["document_type_alignment"]["mismatch_detected"])

