from __future__ import annotations

import unittest

from django.conf import settings
from rest_framework import status
from rest_framework.test import APITestCase

from apps.authentication.models import User

from .models import AuditLog


APP_ENABLED = "apps.audit" in settings.INSTALLED_APPS


@unittest.skipUnless(APP_ENABLED, "Audit app is not enabled in INSTALLED_APPS.")
class AuditApiTests(APITestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(
            email="audit-admin@example.com",
            password="Pass1234!",
            first_name="Audit",
            last_name="Admin",
            user_type="admin",
            is_staff=True,
        )
        self.applicant_user = User.objects.create_user(
            email="audit-applicant@example.com",
            password="Pass1234!",
            first_name="Audit",
            last_name="Applicant",
            user_type="applicant",
        )
        self.other_user = User.objects.create_user(
            email="audit-other@example.com",
            password="Pass1234!",
            first_name="Audit",
            last_name="Other",
            user_type="applicant",
        )

        self.log_own = AuditLog.objects.create(
            user=self.applicant_user,
            action="create",
            entity_type="VettingCase",
            entity_id="1001",
            changes={"status": ["pending", "under_review"]},
        )
        self.log_other = AuditLog.objects.create(
            user=self.other_user,
            action="update",
            entity_type="VettingCase",
            entity_id="1002",
            changes={"priority": ["low", "high"]},
        )
        self.log_admin = AuditLog.objects.create(
            admin_user=self.admin_user,
            action="login",
            entity_type="User",
            entity_id=str(self.admin_user.id),
            changes={},
        )

    def test_regular_user_sees_only_own_logs(self):
        self.client.force_authenticate(self.applicant_user)
        response = self.client.get("/api/audit/logs/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], str(self.log_own.id))

    def test_admin_sees_all_logs(self):
        self.client.force_authenticate(self.admin_user)
        response = self.client.get("/api/audit/logs/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 3)

    def test_by_entity_requires_entity_type_and_entity_id(self):
        self.client.force_authenticate(self.admin_user)
        response = self.client.get("/api/audit/logs/by_entity/")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)

    def test_by_entity_filters_logs(self):
        self.client.force_authenticate(self.admin_user)
        response = self.client.get(
            "/api/audit/logs/by_entity/",
            {"entity_type": "VettingCase", "entity_id": "1001"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["id"], str(self.log_own.id))

    def test_recent_activity_limits_results_to_fifty(self):
        for idx in range(60):
            AuditLog.objects.create(
                user=self.admin_user,
                action="other",
                entity_type="Bulk",
                entity_id=f"BULK-{idx}",
                changes={},
            )

        self.client.force_authenticate(self.admin_user)
        response = self.client.get("/api/audit/logs/recent_activity/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 50)

    def test_statistics_returns_expected_totals(self):
        self.client.force_authenticate(self.admin_user)
        response = self.client.get("/api/audit/logs/statistics/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_logs"], 3)
        self.assertTrue(any(item["action"] == "create" for item in response.data["action_distribution"]))
        self.assertTrue(any(item["entity_type"] == "VettingCase" for item in response.data["entity_distribution"]))
