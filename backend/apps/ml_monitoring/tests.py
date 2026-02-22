# backend/apps/ml_monitoring/tests.py
import datetime
import unittest

from django.conf import settings
from rest_framework import status
from rest_framework.test import APITestCase

from apps.authentication.models import User
from .models import MLModelMetrics


APP_ENABLED = "apps.ml_monitoring" in settings.INSTALLED_APPS


@unittest.skipUnless(APP_ENABLED, "ML monitoring app is not enabled in INSTALLED_APPS.")
class MLMonitoringAPITests(APITestCase):
    def setUp(self):
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
            trained_at=datetime.datetime.now(datetime.UTC),
        )
        MLModelMetrics.objects.create(
            model_name="authenticity_detector",
            model_version="1.1",
            accuracy=0.96,
            precision=0.93,
            recall=0.99,
            f1_score=0.96,
            trained_at=datetime.datetime.now(datetime.UTC),
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
