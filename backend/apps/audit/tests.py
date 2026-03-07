from __future__ import annotations

import unittest

from django.conf import settings
from django.contrib.auth.models import Group
from django.test import RequestFactory
from rest_framework import status
from rest_framework.test import APITestCase

from apps.authentication.models import User

from .contracts import (
    APPOINTMENT_FINAL_DECISION_RECORDED_EVENT,
    APPOINTMENT_NOMINATION_CREATED_EVENT,
    APPOINTMENT_STAGE_ACTION_TAKEN_EVENT,
    APPOINTMENT_STAGE_TRANSITION_EVENT,
    APPOINTMENT_VETTING_LINKAGE_ENSURED_EVENT,
    GOVERNMENT_AUDIT_EVENT_CATALOG,
    PERSONNEL_LINKED_CANDIDATE_EVENT,
    VETTING_DECISION_OVERRIDE_RECORDED_EVENT,
    VETTING_DECISION_RECOMMENDATION_GENERATED_EVENT,
)
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
        self.auditor_user = User.objects.create_user(
            email="audit-reader@example.com",
            password="Pass1234!",
            first_name="Audit",
            last_name="Reader",
            user_type="hr_manager",
        )
        auditor_group, _ = Group.objects.get_or_create(name="auditor")
        self.auditor_user.groups.add(auditor_group)

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
        self.log_position = AuditLog.objects.create(
            admin_user=self.admin_user,
            action="update",
            entity_type="GovernmentPosition",
            entity_id="POS-1",
            changes={"event": "government_position_updated", "field": "title"},
        )
        self.log_personnel = AuditLog.objects.create(
            admin_user=self.admin_user,
            action="delete",
            entity_type="PersonnelRecord",
            entity_id="PER-1",
            changes={"event": "personnel_record_deleted"},
        )
        self.log_appointment = AuditLog.objects.create(
            admin_user=self.admin_user,
            action="create",
            entity_type="AppointmentRecord",
            entity_id="APP-1",
            changes={"event": "appointment_record_created"},
        )

    def test_regular_user_cannot_access_audit_logs(self):
        self.client.force_authenticate(self.applicant_user)
        response = self.client.get("/api/audit/logs/")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_hr_manager_cannot_access_audit_logs(self):
        self.client.force_authenticate(self.hr_user)
        response = self.client.get("/api/audit/logs/")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_auditor_role_can_access_audit_logs(self):
        self.client.force_authenticate(self.auditor_user)
        response = self.client.get("/api/audit/logs/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 6)

    def test_admin_sees_all_logs(self):
        self.client.force_authenticate(self.admin_user)
        response = self.client.get("/api/audit/logs/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 6)

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

    def test_by_user_requires_user_id(self):
        self.client.force_authenticate(self.admin_user)
        response = self.client.get("/api/audit/logs/by_user/")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"], "user_id is required")

    def test_by_user_filters_logs_for_actor_fields(self):
        self.client.force_authenticate(self.admin_user)

        applicant_response = self.client.get(
            "/api/audit/logs/by_user/",
            {"user_id": str(self.applicant_user.id)},
        )
        self.assertEqual(applicant_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(applicant_response.data), 1)
        self.assertEqual(applicant_response.data[0]["id"], str(self.log_own.id))

        admin_response = self.client.get(
            "/api/audit/logs/by_user/",
            {"user_id": str(self.admin_user.id)},
        )
        self.assertEqual(admin_response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(admin_response.data), 3)
        returned_ids = {item["id"] for item in admin_response.data}
        self.assertIn(str(self.log_admin.id), returned_ids)
        self.assertIn(str(self.log_position.id), returned_ids)
        self.assertIn(str(self.log_personnel.id), returned_ids)

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
        self.assertEqual(response.data["total_logs"], 6)
        self.assertTrue(any(item["action"] == "create" for item in response.data["action_distribution"]))
        self.assertTrue(any(item["entity_type"] == "VettingCase" for item in response.data["entity_distribution"]))
        self.assertTrue(
            any(item["entity_type"] == "GovernmentPosition" for item in response.data["entity_distribution"])
        )
        self.assertTrue(
            any(item["entity_type"] == "PersonnelRecord" for item in response.data["entity_distribution"])
        )
        self.assertTrue(
            any(item["entity_type"] == "AppointmentRecord" for item in response.data["entity_distribution"])
        )

    def test_admin_can_filter_list_by_government_entity_type(self):
        self.client.force_authenticate(self.admin_user)

        position_response = self.client.get("/api/audit/logs/", {"entity_type": "GovernmentPosition"})
        self.assertEqual(position_response.status_code, status.HTTP_200_OK)
        self.assertEqual(position_response.data["count"], 1)
        self.assertEqual(position_response.data["results"][0]["id"], str(self.log_position.id))

        personnel_response = self.client.get("/api/audit/logs/", {"entity_type": "PersonnelRecord"})
        self.assertEqual(personnel_response.status_code, status.HTTP_200_OK)
        self.assertEqual(personnel_response.data["count"], 1)
        self.assertEqual(personnel_response.data["results"][0]["id"], str(self.log_personnel.id))

        appointment_response = self.client.get("/api/audit/logs/", {"entity_type": "AppointmentRecord"})
        self.assertEqual(appointment_response.status_code, status.HTTP_200_OK)
        self.assertEqual(appointment_response.data["count"], 1)
        self.assertEqual(appointment_response.data["results"][0]["id"], str(self.log_appointment.id))

    def test_admin_can_filter_list_by_event_key(self):
        self.client.force_authenticate(self.admin_user)

        response = self.client.get("/api/audit/logs/", {"changes__event": "personnel_record_deleted"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], str(self.log_personnel.id))

    def test_admin_can_filter_list_by_entity_and_event_together(self):
        self.client.force_authenticate(self.admin_user)

        response = self.client.get(
            "/api/audit/logs/",
            {"entity_type": "AppointmentRecord", "changes__event": "appointment_record_created"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], str(self.log_appointment.id))

    def test_by_entity_returns_specific_government_records(self):
        self.client.force_authenticate(self.admin_user)

        position_response = self.client.get(
            "/api/audit/logs/by_entity/",
            {"entity_type": "GovernmentPosition", "entity_id": "POS-1"},
        )
        self.assertEqual(position_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(position_response.data), 1)
        self.assertEqual(position_response.data[0]["id"], str(self.log_position.id))

        personnel_response = self.client.get(
            "/api/audit/logs/by_entity/",
            {"entity_type": "PersonnelRecord", "entity_id": "PER-1"},
        )
        self.assertEqual(personnel_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(personnel_response.data), 1)
        self.assertEqual(personnel_response.data[0]["id"], str(self.log_personnel.id))

        appointment_response = self.client.get(
            "/api/audit/logs/by_entity/",
            {"entity_type": "AppointmentRecord", "entity_id": "APP-1"},
        )
        self.assertEqual(appointment_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(appointment_response.data), 1)
        self.assertEqual(appointment_response.data[0]["id"], str(self.log_appointment.id))

    def test_event_catalog_requires_admin(self):
        self.client.force_authenticate(self.hr_user)
        denied = self.client.get("/api/audit/logs/event_catalog/")
        self.assertEqual(denied.status_code, status.HTTP_403_FORBIDDEN)

    def test_event_catalog_allows_auditor_role(self):
        self.client.force_authenticate(self.auditor_user)
        response = self.client.get("/api/audit/logs/event_catalog/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_event_catalog_returns_stable_contract(self):
        self.client.force_authenticate(self.admin_user)
        response = self.client.get("/api/audit/logs/event_catalog/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], len(GOVERNMENT_AUDIT_EVENT_CATALOG))
        self.assertEqual(response.data["results"], GOVERNMENT_AUDIT_EVENT_CATALOG)
        for item in response.data["results"]:
            self.assertEqual(
                set(item.keys()),
                {"key", "entity_type", "action", "description"},
            )

    def test_event_catalog_keys_are_unique_and_include_operational_events(self):
        keys = [item["key"] for item in GOVERNMENT_AUDIT_EVENT_CATALOG]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertIn(PERSONNEL_LINKED_CANDIDATE_EVENT, keys)
        self.assertIn(APPOINTMENT_NOMINATION_CREATED_EVENT, keys)
        self.assertIn(APPOINTMENT_STAGE_TRANSITION_EVENT, keys)
        self.assertIn(APPOINTMENT_STAGE_ACTION_TAKEN_EVENT, keys)
        self.assertIn(APPOINTMENT_FINAL_DECISION_RECORDED_EVENT, keys)
        self.assertIn(APPOINTMENT_VETTING_LINKAGE_ENSURED_EVENT, keys)
        self.assertIn(VETTING_DECISION_RECOMMENDATION_GENERATED_EVENT, keys)
        self.assertIn(VETTING_DECISION_OVERRIDE_RECORDED_EVENT, keys)


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
