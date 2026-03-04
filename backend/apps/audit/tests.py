from __future__ import annotations

import unittest

from django.conf import settings
from django.test import RequestFactory
from rest_framework import status
from rest_framework.test import APITestCase

from apps.authentication.models import User

from .events import log_event, request_ip_address
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
        self.hr_user = User.objects.create_user(
            email="audit-hr@example.com",
            password="Pass1234!",
            first_name="Audit",
            last_name="HR",
            user_type="hr_manager",
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

    def test_regular_user_cannot_access_audit_logs(self):
        self.client.force_authenticate(self.applicant_user)
        response = self.client.get("/api/audit/logs/")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_hr_manager_cannot_access_audit_logs(self):
        self.client.force_authenticate(self.hr_user)
        response = self.client.get("/api/audit/logs/")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

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


    def test_log_event_creates_audit_row_with_request_metadata(self):
        request = RequestFactory().post(
            "/api/applications/cases/123/recheck-social-profiles/",
            HTTP_USER_AGENT="audit-tests",
            HTTP_X_FORWARDED_FOR="203.0.113.10, 10.0.0.4",
        )
        request.user = self.admin_user

        created = log_event(
            request=request,
            action="other",
            entity_type="VettingCase",
            entity_id="CASE-2001",
            changes={"event": "social_profile_recheck", "status": "ok"},
        )

        self.assertTrue(created)
        row = AuditLog.objects.get(entity_type="VettingCase", entity_id="CASE-2001")
        self.assertEqual(row.user, self.admin_user)
        self.assertEqual(row.admin_user, self.admin_user)
        self.assertEqual(row.ip_address, "203.0.113.10")
        self.assertEqual(row.user_agent, "audit-tests")

    def test_request_ip_address_prefers_forwarded_for_header(self):
        request = RequestFactory().get(
            "/",
            HTTP_X_FORWARDED_FOR="198.51.100.3, 10.1.0.8",
            REMOTE_ADDR="127.0.0.1",
        )

        self.assertEqual(request_ip_address(request), "198.51.100.3")


    def test_log_event_sanitizes_non_json_changes(self):
        class NonSerializable:
            def __str__(self):
                return "non-serializable"

        request = RequestFactory().post("/api/audit/test")
        request.user = self.admin_user

        created = log_event(
            request=request,
            action="other",
            entity_type="SanitizeTest",
            entity_id="S-1",
            changes={
                "plain": "ok",
                "obj": NonSerializable(),
                "nested": [NonSerializable(), {"inner": NonSerializable()}],
            },
        )

        self.assertTrue(created)
        row = AuditLog.objects.get(entity_type="SanitizeTest", entity_id="S-1")
        self.assertEqual(row.changes["plain"], "ok")
        self.assertIsInstance(row.changes["obj"], str)
        self.assertEqual(row.changes["obj"], "non-serializable")
        self.assertIsInstance(row.changes["nested"][0], str)
        self.assertEqual(row.changes["nested"][0], "non-serializable")
        self.assertEqual(row.changes["nested"][1]["inner"], "non-serializable")

    def test_log_event_wraps_non_dict_changes(self):
        request = RequestFactory().post("/api/audit/test")
        request.user = self.admin_user

        created = log_event(
            request=request,
            action="other",
            entity_type="SanitizeTest",
            entity_id="S-2",
            changes=["a", "b"],
        )

        self.assertTrue(created)
        row = AuditLog.objects.get(entity_type="SanitizeTest", entity_id="S-2")
        self.assertEqual(row.changes, {"value": ["a", "b"]})
