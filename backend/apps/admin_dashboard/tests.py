# backend/apps/admin_dashboard/tests.py
import unittest

from django.conf import settings
from django.contrib.auth.models import Group
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
        self.hr_user = User.objects.create_user(
            email="hr@example.com",
            password="strongpassword123",
            first_name="HR",
            last_name="Manager",
            user_type="hr_manager",
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

    def test_dashboard_as_hr_manager_is_forbidden(self):
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.get("/api/admin/dashboard/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_dashboard_as_staff_non_admin_is_forbidden(self):
        staff_user = User.objects.create_user(
            email="staff-non-admin@example.com",
            password="strongpassword123",
            first_name="Staff",
            last_name="NonAdmin",
            user_type="hr_manager",
            is_staff=True,
        )
        self.client.force_authenticate(user=staff_user)
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

    def test_analytics_invalid_months_falls_back_to_default_window(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get("/api/admin/analytics/?months=invalid")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["monthly_trend"]), 6)

    def test_cases_invalid_page_and_page_size_use_defaults(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get("/api/admin/cases/?page=abc&page_size=-5")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["page"], 1)
        self.assertEqual(response.data["page_size"], 20)

    def test_cases_supports_ordering(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get("/api/admin/cases/?ordering=created_at")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["ordering"], "created_at")
        self.assertEqual(response.data["results"][0]["application_type"], "Employment")

    def test_cases_invalid_ordering_falls_back_to_default(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get("/api/admin/cases/?ordering=unsupported_field")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["ordering"], "-created_at")

    def test_users_list_as_admin(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get("/api/admin/users/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(response.data["count"], 3)
        self.assertEqual(response.data["page"], 1)

    def test_users_filter_by_type(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get("/api/admin/users/?user_type=hr_manager")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["email"], "hr@example.com")

    def test_admin_can_disable_non_self_user(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.patch(
            f"/api/admin/users/{self.hr_user.id}/",
            {"is_active": False},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.hr_user.refresh_from_db()
        self.assertFalse(self.hr_user.is_active)

    def test_admin_cannot_disable_self(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.patch(
            f"/api/admin/users/{self.admin_user.id}/",
            {"is_active": False},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_admin_can_assign_government_group_roles(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.patch(
            f"/api/admin/users/{self.hr_user.id}/",
            {"group_roles": ["vetting_officer", "auditor"]},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.hr_user.refresh_from_db()
        assigned_roles = set(self.hr_user.groups.values_list("name", flat=True))
        self.assertIn("vetting_officer", assigned_roles)
        self.assertIn("auditor", assigned_roles)
        self.assertTrue(Group.objects.filter(name="vetting_officer").exists())

    def test_admin_cannot_assign_internal_roles_to_applicant_user(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.patch(
            f"/api/admin/users/{self.regular_user.id}/",
            {"group_roles": ["vetting_officer"]},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
