"""API tests for AI monitor operational endpoints."""

from __future__ import annotations

from unittest.mock import MagicMock
from unittest.mock import patch

import cv2
import numpy as np
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, override_settings
from rest_framework.test import APIClient


@override_settings(ROOT_URLCONF="ai_ml_services.tests.urls")
class TestMonitorHealthAPI(SimpleTestCase):
    @patch("ai_ml_services.views.model_monitor")
    @override_settings(SERVICE_TOKEN="test-service-token")
    def test_health_endpoint_allows_valid_service_token(self, mock_monitor):
        mock_monitor.enabled = True
        mock_monitor.backend = "memory"
        mock_monitor.use_redis = False
        mock_monitor.redis_url = "redis://localhost:6379/2"
        mock_monitor.get_metrics.return_value = {
            "status": "no_data",
            "model_name": "default",
            "backend": "memory",
        }
        mock_monitor.check_data_drift.return_value = {
            "drift_detected": False,
            "model_name": "default",
            "reason": "Insufficient data",
        }

        client = APIClient()
        response = client.get(
            "/api/ai-monitor/health/",
            HTTP_X_SERVICE_TOKEN="test-service-token",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "ok")
        self.assertEqual(response.data["monitor"]["backend"], "memory")
        self.assertIn("metrics", response.data)
        self.assertIn("drift", response.data)

    @patch("ai_ml_services.views.model_monitor")
    @override_settings(SERVICE_TOKEN="test-service-token")
    def test_health_endpoint_rejects_missing_token_for_anonymous(self, mock_monitor):
        mock_monitor.enabled = True
        mock_monitor.backend = "memory"
        mock_monitor.use_redis = False
        mock_monitor.redis_url = "redis://localhost:6379/2"

        client = APIClient()
        response = client.get("/api/ai-monitor/health/")

        self.assertEqual(response.status_code, 403)

    @patch("ai_ml_services.views.get_ai_service")
    @override_settings(SERVICE_TOKEN="test-service-token")
    def test_document_classification_endpoint_accepts_valid_token(self, mock_get_service):
        mock_service = MagicMock()
        mock_service.classify_document_image.return_value = {
            "document_classification": {
                "rvl_cdip": {"available": True, "predicted_label": "invoice", "confidence": 0.81},
                "midv500": {"available": True, "predicted_label": "16_deu_passport_new", "confidence": 0.77},
            },
            "document_type_alignment": {
                "enabled": True,
                "mismatch_detected": False,
                "details": [],
            },
        }
        mock_get_service.return_value = mock_service

        canvas = np.full((64, 64, 3), 255, dtype=np.uint8)
        ok, encoded = cv2.imencode(".png", canvas)
        self.assertTrue(ok)
        upload = SimpleUploadedFile(
            "doc.png",
            encoded.tobytes(),
            content_type="image/png",
        )

        client = APIClient()
        response = client.post(
            "/api/ai-monitor/classify-document/",
            {"file": upload, "document_type": "passport", "top_k": 3},
            format="multipart",
            HTTP_X_SERVICE_TOKEN="test-service-token",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "ok")
        self.assertIn("document_classification", response.data)
        self.assertIn("document_type_alignment", response.data)

    @override_settings(SERVICE_TOKEN="test-service-token")
    def test_document_classification_endpoint_requires_token_or_admin(self):
        canvas = np.full((64, 64, 3), 255, dtype=np.uint8)
        ok, encoded = cv2.imencode(".png", canvas)
        self.assertTrue(ok)
        upload = SimpleUploadedFile(
            "doc.png",
            encoded.tobytes(),
            content_type="image/png",
        )

        client = APIClient()
        response = client.post(
            "/api/ai-monitor/classify-document/",
            {"file": upload},
            format="multipart",
        )
        self.assertEqual(response.status_code, 403)
