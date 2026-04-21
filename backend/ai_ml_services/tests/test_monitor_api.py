"""API tests for AI monitor operational endpoints."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

try:
    import cv2
    import numpy as np
except ModuleNotFoundError:  # pragma: no cover - optional ML extras
    cv2 = None
    np = None
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from apps.users.models import User


_HAS_CV2_NUMPY = bool(cv2 is not None and np is not None)
_CV2_NUMPY_MISSING_REASON = "Optional dependency missing for monitor API tests: cv2/numpy"


@override_settings(ROOT_URLCONF="ai_ml_services.tests.urls")
@unittest.skipUnless(_HAS_CV2_NUMPY, _CV2_NUMPY_MISSING_REASON)
class MonitorApiBaseTests(APITestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(
            email="aimonitor-admin@example.com",
            password="Pass1234!",
            first_name="AI",
            last_name="Admin",
            user_type="admin",
            is_staff=True,
        )
        self.internal_user = User.objects.create_user(
            email="aimonitor-internal@example.com",
            password="Pass1234!",
            first_name="AI",
            last_name="Internal",
            user_type="internal",
        )

    def authenticate_admin(self):
        self.client.force_authenticate(self.admin_user)

    def authenticate_internal(self):
        self.client.force_authenticate(self.internal_user)

    @staticmethod
    def _sample_image_upload(name: str = "doc.png") -> SimpleUploadedFile:
        canvas = np.full((64, 64, 3), 255, dtype=np.uint8)
        ok, encoded = cv2.imencode(".png", canvas)
        assert ok
        return SimpleUploadedFile(name, encoded.tobytes(), content_type="image/png")


@override_settings(ROOT_URLCONF="ai_ml_services.tests.urls")
@unittest.skipUnless(_HAS_CV2_NUMPY, _CV2_NUMPY_MISSING_REASON)
class MonitorHealthApiTests(MonitorApiBaseTests):
    @patch("ai_ml_services.views.model_monitor")
    def test_health_endpoint_allows_admin(self, mock_monitor):
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

        self.authenticate_admin()
        with patch("ai_ml_services.views.log_event") as mock_log_event:
            response = self.client.get("/api/ai-monitor/health/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
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

    def test_health_endpoint_rejects_internal_user(self):
        self.authenticate_internal()
        with patch("ai_ml_services.views.log_event") as mock_log_event:
            response = self.client.get("/api/ai-monitor/health/")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        mock_log_event.assert_not_called()

    def test_health_endpoint_rejects_anonymous(self):
        with patch("ai_ml_services.views.log_event") as mock_log_event:
            response = self.client.get("/api/ai-monitor/health/")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        mock_log_event.assert_not_called()


@override_settings(ROOT_URLCONF="ai_ml_services.tests.urls")
class MonitorPublicRouteTests(APITestCase):
    _public_host = {"SERVER_NAME": "public.testserver"}

    def setUp(self):
        self.superuser = User.objects.create_user(
            email="aimonitor-superuser@example.com",
            password="Pass1234!",
            first_name="AI",
            last_name="Superuser",
            user_type="admin",
            is_staff=True,
            is_superuser=True,
        )

    @patch("ai_ml_services.views.model_monitor")
    def test_versioned_health_endpoint_is_available_from_public_schema_for_superuser(self, mock_monitor):
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

        self.client.force_authenticate(self.superuser)
        with patch("ai_ml_services.views.log_event") as mock_log_event:
            response = self.client.get("/api/v1/ai-monitor/health/", **self._public_host)

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["status"], "ok")
        self.assertEqual(response.data["monitor"]["backend"], "memory")
        mock_log_event.assert_called_once()


@override_settings(ROOT_URLCONF="ai_ml_services.tests.urls")
@unittest.skipUnless(_HAS_CV2_NUMPY, _CV2_NUMPY_MISSING_REASON)
class MonitorDocumentClassificationApiTests(MonitorApiBaseTests):
    @patch("ai_ml_services.views.get_ai_service")
    def test_document_classification_endpoint_accepts_admin(self, mock_get_service):
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

        self.authenticate_admin()
        upload = self._sample_image_upload()

        with patch("ai_ml_services.views.log_event") as mock_log_event:
            response = self.client.post(
                "/api/ai-monitor/classify-document/",
                {"file": upload, "document_type": "passport", "top_k": 3},
                format="multipart",
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
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

    def test_document_classification_endpoint_rejects_internal_user(self):
        self.authenticate_internal()
        upload = self._sample_image_upload()
        with patch("ai_ml_services.views.log_event") as mock_log_event:
            response = self.client.post(
                "/api/ai-monitor/classify-document/",
                {"file": upload},
                format="multipart",
            )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        mock_log_event.assert_not_called()

    def test_document_classification_endpoint_rejects_anonymous(self):
        upload = self._sample_image_upload()
        with patch("ai_ml_services.views.log_event") as mock_log_event:
            response = self.client.post(
                "/api/ai-monitor/classify-document/",
                {"file": upload},
                format="multipart",
            )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        mock_log_event.assert_not_called()

    def test_document_classification_endpoint_invalid_file_returns_400_without_audit(self):
        self.authenticate_admin()
        bad_upload = SimpleUploadedFile("broken.png", b"not-an-image", content_type="image/png")

        with patch("ai_ml_services.views.log_event") as mock_log_event:
            response = self.client.post(
                "/api/ai-monitor/classify-document/",
                {"file": bad_upload, "document_type": "passport", "top_k": 3},
                format="multipart",
            )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("detail", response.data)
        mock_log_event.assert_not_called()


@override_settings(ROOT_URLCONF="ai_ml_services.tests.urls")
@unittest.skipUnless(_HAS_CV2_NUMPY, _CV2_NUMPY_MISSING_REASON)
class MonitorSocialProfileApiTests(MonitorApiBaseTests):
    @patch("ai_ml_services.views.get_ai_service")
    def test_social_profile_check_endpoint_accepts_admin(self, mock_get_service):
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

        self.authenticate_admin()
        with patch("ai_ml_services.views.log_event") as mock_log_event:
            response = self.client.post(
                "/api/ai-monitor/check-social-profiles/",
                {
                    "case_id": "CASE-SOC-3",
                    "consent_provided": True,
                    "profiles": [{"platform": "linkedin", "url": "https://linkedin.com/in/user"}],
                },
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
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

    def test_social_profile_check_endpoint_rejects_internal_user(self):
        self.authenticate_internal()
        with patch("ai_ml_services.views.log_event") as mock_log_event:
            response = self.client.post(
                "/api/ai-monitor/check-social-profiles/",
                {
                    "consent_provided": True,
                    "profiles": [{"platform": "linkedin", "url": "https://linkedin.com/in/user"}],
                },
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        mock_log_event.assert_not_called()

    def test_social_profile_check_endpoint_rejects_anonymous(self):
        with patch("ai_ml_services.views.log_event") as mock_log_event:
            response = self.client.post(
                "/api/ai-monitor/check-social-profiles/",
                {
                    "consent_provided": True,
                    "profiles": [{"platform": "linkedin", "url": "https://linkedin.com/in/user"}],
                },
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        mock_log_event.assert_not_called()

    def test_social_profile_check_endpoint_invalid_payload_returns_400_without_audit(self):
        self.authenticate_admin()
        with patch("ai_ml_services.views.log_event") as mock_log_event:
            response = self.client.post(
                "/api/ai-monitor/check-social-profiles/",
                {
                    "case_id": "CASE-SOC-3",
                    "consent_provided": True,
                    "profiles": [],
                },
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("profiles", response.data)
        mock_log_event.assert_not_called()
