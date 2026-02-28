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
        with patch("ai_ml_services.views.log_event") as mock_log_event:
            response = client.get(
                "/api/ai-monitor/health/",
                HTTP_X_SERVICE_TOKEN="test-service-token",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "ok")
        self.assertEqual(response.data["monitor"]["backend"], "memory")
        self.assertIn("metrics", response.data)
        self.assertIn("drift", response.data)

        mock_log_event.assert_called_once()
        kwargs = mock_log_event.call_args.kwargs
        self.assertEqual(kwargs["action"], "other")
        self.assertEqual(kwargs["entity_type"], "AIMonitorEndpoint")
        self.assertEqual(kwargs["entity_id"], "health")
        self.assertEqual(kwargs["changes"]["status"], "ok")
        self.assertEqual(kwargs["changes"]["model_name"], "default")

    @patch("ai_ml_services.views.model_monitor")
    @override_settings(SERVICE_TOKEN="test-service-token")
    def test_health_endpoint_rejects_missing_token_for_anonymous(self, mock_monitor):
        mock_monitor.enabled = True
        mock_monitor.backend = "memory"
        mock_monitor.use_redis = False
        mock_monitor.redis_url = "redis://localhost:6379/2"

        client = APIClient()
        with patch("ai_ml_services.views.log_event") as mock_log_event:
            response = client.get("/api/ai-monitor/health/")

        self.assertEqual(response.status_code, 403)
        mock_log_event.assert_not_called()

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
        with patch("ai_ml_services.views.log_event") as mock_log_event:
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

        mock_log_event.assert_called_once()
        kwargs = mock_log_event.call_args.kwargs
        self.assertEqual(kwargs["action"], "other")
        self.assertEqual(kwargs["entity_type"], "AIMonitorEndpoint")
        self.assertEqual(kwargs["entity_id"], "classify-document")
        self.assertEqual(kwargs["changes"]["status"], "ok")
        self.assertEqual(kwargs["changes"]["document_type"], "passport")
        self.assertEqual(kwargs["changes"]["top_k"], 3)
        self.assertEqual(kwargs["changes"]["filename"], "doc.png")

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
        with patch("ai_ml_services.views.log_event") as mock_log_event:
            response = client.post(
                "/api/ai-monitor/classify-document/",
                {"file": upload},
                format="multipart",
            )

        self.assertEqual(response.status_code, 403)
        mock_log_event.assert_not_called()

    @override_settings(SERVICE_TOKEN="test-service-token")
    def test_document_classification_endpoint_invalid_file_returns_400_without_audit(self):
        bad_upload = SimpleUploadedFile(
            "broken.png",
            b"not-an-image",
            content_type="image/png",
        )

        client = APIClient()
        with patch("ai_ml_services.views.log_event") as mock_log_event:
            response = client.post(
                "/api/ai-monitor/classify-document/",
                {"file": bad_upload, "document_type": "passport", "top_k": 3},
                format="multipart",
                HTTP_X_SERVICE_TOKEN="test-service-token",
            )

        self.assertEqual(response.status_code, 400)
        self.assertIn("detail", response.data)
        mock_log_event.assert_not_called()

    @patch("ai_ml_services.views.get_ai_service")
    @override_settings(SERVICE_TOKEN="test-service-token")
    def test_social_profile_check_endpoint_accepts_valid_token(self, mock_get_service):
        mock_service = MagicMock()
        mock_service.check_social_profiles.return_value = {
            "case_id": "CASE-SOC-3",
            "consent_provided": True,
            "profiles_checked": 1,
            "overall_score": 81.0,
            "risk_level": "low",
            "recommendation": "MANUAL_REVIEW",
            "automated_decision_allowed": False,
            "decision_constraints": [
                {
                    "code": "social_check_advisory_only",
                    "reason": "Social profile checks are advisory and must not be auto-decisive.",
                }
            ],
            "profiles": [
                {
                    "platform": "linkedin",
                    "score": 81.0,
                    "risk_level": "low",
                    "findings": [],
                }
            ],
        }
        mock_get_service.return_value = mock_service

        client = APIClient()
        with patch("ai_ml_services.views.log_event") as mock_log_event:
            response = client.post(
                "/api/ai-monitor/check-social-profiles/",
                {
                    "case_id": "CASE-SOC-3",
                    "consent_provided": True,
                    "profiles": [
                        {"platform": "linkedin", "url": "https://linkedin.com/in/user"}
                    ],
                },
                format="json",
                HTTP_X_SERVICE_TOKEN="test-service-token",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "ok")
        self.assertEqual(response.data["overall_score"], 81.0)
        self.assertEqual(response.data["profiles_checked"], 1)

        mock_log_event.assert_called_once()
        kwargs = mock_log_event.call_args.kwargs
        self.assertEqual(kwargs["action"], "other")
        self.assertEqual(kwargs["entity_type"], "AIMonitorEndpoint")
        self.assertEqual(kwargs["entity_id"], "check-social-profiles")
        self.assertEqual(kwargs["changes"]["status"], "ok")
        self.assertEqual(kwargs["changes"]["case_id"], "CASE-SOC-3")
        self.assertEqual(kwargs["changes"]["consent_provided"], True)
        self.assertEqual(kwargs["changes"]["profiles_requested"], 1)
        self.assertEqual(kwargs["changes"]["profiles_checked"], 1)
        self.assertEqual(kwargs["changes"]["overall_score"], 81.0)
        self.assertEqual(kwargs["changes"]["risk_level"], "low")
        self.assertEqual(kwargs["changes"]["recommendation"], "MANUAL_REVIEW")

    @override_settings(SERVICE_TOKEN="test-service-token")
    def test_social_profile_check_endpoint_requires_token_or_admin(self):
        client = APIClient()
        with patch("ai_ml_services.views.log_event") as mock_log_event:
            response = client.post(
                "/api/ai-monitor/check-social-profiles/",
                {
                    "consent_provided": True,
                    "profiles": [{"platform": "linkedin", "url": "https://linkedin.com/in/user"}],
                },
                format="json",
            )

        self.assertEqual(response.status_code, 403)
        mock_log_event.assert_not_called()

    @override_settings(SERVICE_TOKEN="test-service-token")
    def test_social_profile_check_endpoint_invalid_payload_returns_400_without_audit(self):
        client = APIClient()
        with patch("ai_ml_services.views.log_event") as mock_log_event:
            response = client.post(
                "/api/ai-monitor/check-social-profiles/",
                {
                    "case_id": "CASE-SOC-3",
                    "consent_provided": True,
                    "profiles": [],
                },
                format="json",
                HTTP_X_SERVICE_TOKEN="test-service-token",
            )

        self.assertEqual(response.status_code, 400)
        self.assertIn("profiles", response.data)
        mock_log_event.assert_not_called()
