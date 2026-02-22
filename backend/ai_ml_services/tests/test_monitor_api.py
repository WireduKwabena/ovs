"""API tests for AI monitor operational endpoints."""

from __future__ import annotations

from unittest.mock import patch

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
