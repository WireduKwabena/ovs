"""Unit tests for ai_ml_services Celery task wrappers."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from ai_ml_services.utils.tasks import (
    batch_verify_documents_task,
    check_consistency_task,
    detect_fraud_task,
    health_check_task,
    verify_document_task,
)


class TestTasks(SimpleTestCase):
    @patch("ai_ml_services.utils.tasks.verify_document")
    def test_verify_document_task(self, mock_verify_document):
        mock_verify_document.return_value = {
            "results": {"overall_score": 91.5, "recommendation": "APPROVE"}
        }

        result = verify_document_task.run(1, "file.jpg", "id_card", "CASE-1")

        self.assertTrue(result["success"])
        self.assertEqual(result["document_id"], 1)
        self.assertEqual(result["case_id"], "CASE-1")
        self.assertEqual(result["result"]["results"]["recommendation"], "APPROVE")

    @patch("ai_ml_services.utils.tasks.detect_fraud")
    def test_detect_fraud_task(self, mock_detect_fraud):
        mock_detect_fraud.return_value = {
            "is_fraud": False,
            "fraud_probability": 0.08,
            "risk_level": "LOW",
        }

        result = detect_fraud_task.run("CASE-2", {"email": "a@example.com"})

        self.assertTrue(result["success"])
        self.assertEqual(result["case_id"], "CASE-2")
        self.assertFalse(result["result"]["is_fraud"])

    @patch("ai_ml_services.utils.tasks.check_consistency")
    def test_check_consistency_task(self, mock_check_consistency):
        mock_check_consistency.return_value = {
            "overall_consistent": True,
            "overall_score": 86.4,
        }

        result = check_consistency_task.run("CASE-3", [{"text": "ok"}])

        self.assertTrue(result["success"])
        self.assertTrue(result["result"]["overall_consistent"])

    @patch("ai_ml_services.utils.tasks.batch_verify_documents")
    def test_batch_verify_documents_task(self, mock_batch_verify_documents):
        mock_batch_verify_documents.return_value = {
            "total_documents": 2,
            "results": [{"success": True}, {"success": False}],
        }

        result = batch_verify_documents_task.run(
            "CASE-4", [{"file_path": "a.jpg"}, {"file_path": "b.jpg"}], "id_card"
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["result"]["total_documents"], 2)

    @patch("ai_ml_services.service.get_ai_service")
    def test_health_check_task(self, mock_get_ai_service):
        fraud_scaler = SimpleNamespace(mean_=[0.0], transform=lambda value: value)
        mock_get_ai_service.return_value = SimpleNamespace(
            ocr_service=SimpleNamespace(extract_text_tesseract=lambda *_: "text"),
            authenticity_detector=SimpleNamespace(model=object()),
            fraud_detector=SimpleNamespace(
                model=object(),
                scaler=fraud_scaler,
                predict_fraud=lambda *_: {"is_fraud": False},
            ),
            consistency_checker=SimpleNamespace(nlp=object()),
        )

        result = health_check_task.run()

        self.assertEqual(result["status"], "healthy")
        self.assertEqual(result["services"]["ocr"], "operational")
        self.assertEqual(result["services"]["fraud_detection"], "operational")
