# backend/apps/ml_monitoring/tests.py
import datetime
import unittest
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.conf import settings
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase
from rest_framework import status
from rest_framework.test import APITestCase

from apps.authentication.models import User
from .middleware import PerformanceMonitoringMiddleware, RequestLoggingMiddleware
from .models import MLModelMetrics


APP_ENABLED = "apps.ml_monitoring" in settings.INSTALLED_APPS


@unittest.skipUnless(APP_ENABLED, "ML monitoring app is not enabled in INSTALLED_APPS.")
class MLMonitoringAPITests(APITestCase):
    def setUp(self):
        base_time = datetime.datetime(2026, 1, 1, 0, 0, tzinfo=datetime.UTC)
        self.admin_user = User.objects.create_user(
            email="admin@example.com",
            password="strongpassword123",
            first_name="Admin",
            last_name="User",
            user_type="admin",
            is_staff=True,
        )
        self.regular_user = User.objects.create_user(
            email="test@example.com",
            password="strongpassword123",
            first_name="Test",
            last_name="User",
            user_type="applicant",
        )
        MLModelMetrics.objects.create(
            model_name="authenticity_detector",
            model_version="1.0",
            accuracy=0.95,
            precision=0.92,
            recall=0.98,
            f1_score=0.95,
            trained_at=base_time,
        )
        MLModelMetrics.objects.create(
            model_name="authenticity_detector",
            model_version="1.1",
            accuracy=0.96,
            precision=0.93,
            recall=0.99,
            f1_score=0.96,
            trained_at=base_time + datetime.timedelta(days=1),
        )

    def test_list_metrics_as_admin(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get("/api/ml-monitoring/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 2)

    def test_list_metrics_as_regular_user(self):
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.get("/api/ml-monitoring/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_get_latest_metrics(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get("/api/ml-monitoring/latest/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["model_version"], "1.1")

    def test_metrics_legacy_alias_route(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get("/api/ml-monitoring/metrics/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 2)

    def test_performance_summary_returns_latest_per_model(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get("/api/ml-monitoring/performance-summary/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_models"], 1)
        self.assertEqual(
            response.data["models"]["authenticity_detector"]["version"],
            "1.1",
        )

    def test_history_requires_model_name(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get("/api/ml-monitoring/history/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("model_name", response.data["error"])

    def test_history_rejects_invalid_limit(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get("/api/ml-monitoring/history/?model_name=authenticity_detector&limit=abc")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("limit", response.data["error"])

    def test_history_returns_limited_sorted_rows(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get("/api/ml-monitoring/history/?model_name=authenticity_detector&limit=1")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["limit"], 1)
        self.assertEqual(len(response.data["history"]), 1)
        self.assertEqual(response.data["history"][0]["model_version"], "1.1")


class MLMonitoringMiddlewareTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_performance_middleware_adds_duration_header(self):
        middleware = PerformanceMonitoringMiddleware(get_response=lambda request: HttpResponse("ok"))
        request = self.factory.get("/api/ml-monitoring/")

        with patch("apps.ml_monitoring.middleware.time.perf_counter", side_effect=[10.0, 10.25]):
            middleware.process_request(request)
            response = middleware.process_response(request, HttpResponse("ok"))

        self.assertEqual(response.status_code, 200)
        self.assertIn("X-Request-Duration", response)
        self.assertEqual(response["X-Request-Duration"], "0.250s")

    def test_request_logging_middleware_logs_request(self):
        middleware = RequestLoggingMiddleware(get_response=lambda request: HttpResponse("ok"))
        request = self.factory.get("/api/ml-monitoring/")
        request.user = AnonymousUser()
        request.META["REMOTE_ADDR"] = "127.0.0.1"

        with patch("apps.ml_monitoring.middleware.logger.info") as mock_info:
            middleware.process_request(request)

        mock_info.assert_called_once()

    def test_request_logging_middleware_handles_missing_user_attribute(self):
        middleware = RequestLoggingMiddleware(get_response=lambda request: HttpResponse("ok"))
        request = self.factory.get("/api/ml-monitoring/")
        if hasattr(request, "user"):
            delattr(request, "user")
        request.META["REMOTE_ADDR"] = "127.0.0.1"

        with patch("apps.ml_monitoring.middleware.logger.info") as mock_info:
            middleware.process_request(request)

        mock_info.assert_called_once()
        self.assertEqual(mock_info.call_args[0][4], "Anonymous")
