# backend/apps/admin_dashboard/tests.py
import unittest

from django.conf import settings
from rest_framework import status
from rest_framework.test import APITestCase

from apps.authentication.models import User
from apps.applications.models import VettingCase


APP_ENABLED = "apps.admin_dashboard" in settings.INSTALLED_APPS


@unittest.skipUnless(APP_ENABLED, "Admin dashboard app is not enabled in INSTALLED_APPS.")
class AdminDashboardAPITests(APITestCase):
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
        VettingCase.objects.create(
            applicant=self.regular_user,
            position_applied="Employment",
            department="General",
            status="pending",
            priority="medium",
        )
        VettingCase.objects.create(
            applicant=self.regular_user,
            position_applied="Visa",
            department="General",
            status="approved",
            priority="medium",
        )

    def test_dashboard_as_admin(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get("/api/admin/dashboard/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_applications"], 2)

    def test_dashboard_as_regular_user(self):
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.get("/api/admin/dashboard/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_analytics_as_admin(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get("/api/admin/analytics/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["status_distribution"]), 2)

    def test_cases_as_admin(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get("/api/admin/cases/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 2)

    def test_cases_filter_by_status(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get("/api/admin/cases/?status=pending")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["status"], "pending")
