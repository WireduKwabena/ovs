from datetime import date

from django.conf import settings
from django.contrib.auth.models import Group
from rest_framework.test import APITestCase

from apps.appointments.models import AppointmentRecord
from apps.audit.contracts import (
    PERSONNEL_LINKED_CANDIDATE_EVENT,
    PERSONNEL_RECORD_CREATED_EVENT,
    PERSONNEL_RECORD_DELETED_EVENT,
    PERSONNEL_RECORD_UPDATED_EVENT,
)
from apps.authentication.models import User
from apps.candidates.models import Candidate
from apps.governance.models import Organization, OrganizationMembership
from apps.positions.models import GovernmentPosition
from apps.personnel.models import PersonnelRecord


class PersonnelApiTests(APITestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(
            email="personnel_admin@example.com",
            password="Pass1234!",
            first_name="Personnel",
            last_name="Admin",
            user_type="admin",
        )
        self.internal_user = User.objects.create_user(
            email="personnel_hr@example.com",
            password="Pass1234!",
            first_name="Personnel",
            last_name="Reviewer",
            user_type="internal",
        )
        self.registry_group, _ = Group.objects.get_or_create(name="registry_admin")
        self.internal_user.groups.add(self.registry_group)
        self.applicant_user = User.objects.create_user(
            email="personnel_applicant@example.com",
            password="Pass1234!",
            first_name="Personnel",
            last_name="Applicant",
            user_type="applicant",
        )
        self.candidate = Candidate.objects.create(
            first_name="Jane",
            last_name="Nominee",
            email="jane.nominee@example.com",
        )
        self.record = PersonnelRecord.objects.create(
            full_name="Jane Nominee",
            is_public=True,
            is_active_officeholder=True,
        )

    def _extract_results(self, response):
        payload = response.json()
        if isinstance(payload, dict) and "results" in payload:
            return payload["results"]
        return payload

    def _assert_audit_row_exists(self, *, action: str, entity_id: str, expected_event: str | None = None):
        if "apps.audit" not in settings.INSTALLED_APPS:
            return
        from apps.audit.models import AuditLog

        row = (
            AuditLog.objects.filter(
                action=action,
                entity_type="PersonnelRecord",
                entity_id=str(entity_id),
            )
            .order_by("-created_at")
            .first()
        )
        self.assertIsNotNone(row)
        if expected_event:
            self.assertEqual((row.changes or {}).get("event"), expected_event)

    def test_officeholders_is_public(self):
        response = self.client.get("/api/personnel/officeholders/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)
        item = response.json()[0]
        self.assertNotIn("contact_email", item)
        self.assertNotIn("contact_phone", item)
        self.assertNotIn("national_id_hash", item)
        self.assertNotIn("national_id_encrypted", item)

    def test_link_candidate_requires_internal_or_admin(self):
        response = self.client.post(
            f"/api/personnel/{self.record.id}/link-candidate/",
            {"candidate_id": str(self.candidate.id)},
            format="json",
        )
        self.assertIn(response.status_code, {401, 403})

        # Platform admins are restricted to subscription + org status oversight only.
        self.client.force_authenticate(self.admin_user)
        denied = self.client.post(
            f"/api/personnel/{self.record.id}/link-candidate/",
            {"candidate_id": str(self.candidate.id)},
            format="json",
        )
        self.assertEqual(denied.status_code, 403)

        self.client.force_authenticate(self.internal_user)
        success = self.client.post(
            f"/api/personnel/{self.record.id}/link-candidate/",
            {"candidate_id": str(self.candidate.id)},
            format="json",
        )
        self.assertEqual(success.status_code, 200)
        self.record.refresh_from_db()
        self.assertEqual(self.record.linked_candidate_id, self.candidate.id)
        self._assert_audit_row_exists(
            action="update",
            entity_id=str(self.record.id),
            expected_event=PERSONNEL_LINKED_CANDIDATE_EVENT,
        )

    def test_personnel_list_allows_internal_and_admin_but_blocks_applicant(self):
        unauthenticated = self.client.get("/api/personnel/")
        self.assertIn(unauthenticated.status_code, {401, 403})

        self.client.force_authenticate(self.applicant_user)
        denied = self.client.get("/api/personnel/")
        self.assertEqual(denied.status_code, 403)

        self.client.force_authenticate(self.internal_user)
        internal_allowed = self.client.get("/api/personnel/")
        self.assertEqual(internal_allowed.status_code, 200)
        self.assertGreaterEqual(len(self._extract_results(internal_allowed)), 1)

        self.client.force_authenticate(self.admin_user)
        denied_admin = self.client.get("/api/personnel/")
        self.assertEqual(denied_admin.status_code, 403)

    def test_personnel_create_allows_internal_and_admin_but_blocks_applicant(self):
        create_org = Organization.objects.create(code="personnel-create-org", name="Personnel Create Org")
        OrganizationMembership.objects.create(
            user=self.internal_user,
            organization=create_org,
            is_active=True,
            is_default=True,
        )
        payload = {
            "full_name": "New Public Officer",
            "is_public": True,
            "is_active_officeholder": False,
            "organization": str(create_org.id),
        }

        self.client.force_authenticate(self.applicant_user)
        denied = self.client.post("/api/personnel/", payload, format="json")
        self.assertEqual(denied.status_code, 403)

        self.client.force_authenticate(self.internal_user)
        internal_allowed = self.client.post(
            "/api/personnel/",
            {**payload, "full_name": "New Public Officer Internal"},
            format="json",
        )
        self.assertEqual(internal_allowed.status_code, 201)
        self._assert_audit_row_exists(
            action="create",
            entity_id=internal_allowed.json()["id"],
            expected_event=PERSONNEL_RECORD_CREATED_EVENT,
        )

        self.client.force_authenticate(self.admin_user)
        admin_denied = self.client.post(
            "/api/personnel/",
            {**payload, "full_name": "New Public Officer Admin"},
            format="json",
        )
        self.assertEqual(admin_denied.status_code, 403)

    def test_personnel_update_allows_internal_and_admin_but_blocks_applicant(self):
        detail_url = f"/api/personnel/{self.record.id}/"

        self.client.force_authenticate(self.applicant_user)
        denied = self.client.patch(detail_url, {"full_name": "Blocked Personnel Update"}, format="json")
        self.assertEqual(denied.status_code, 403)

        self.client.force_authenticate(self.internal_user)
        internal_allowed = self.client.patch(detail_url, {"full_name": "Personnel Updated By Internal Reviewer"}, format="json")
        self.assertEqual(internal_allowed.status_code, 200)
        self._assert_audit_row_exists(
            action="update",
            entity_id=str(self.record.id),
            expected_event=PERSONNEL_RECORD_UPDATED_EVENT,
        )

        self.client.force_authenticate(self.admin_user)
        admin_denied = self.client.patch(detail_url, {"full_name": "Personnel Updated By Admin"}, format="json")
        self.assertEqual(admin_denied.status_code, 403)

    def test_personnel_delete_allows_internal_and_admin_but_blocks_applicant(self):
        blocked_record = PersonnelRecord.objects.create(
            full_name="Delete Blocked Personnel",
            is_public=False,
            is_active_officeholder=False,
        )
        internal_record = PersonnelRecord.objects.create(
            full_name="Delete Internal Personnel",
            is_public=False,
            is_active_officeholder=False,
        )
        admin_record = PersonnelRecord.objects.create(
            full_name="Delete Admin Personnel",
            is_public=False,
            is_active_officeholder=False,
        )

        self.client.force_authenticate(self.applicant_user)
        denied = self.client.delete(f"/api/personnel/{blocked_record.id}/")
        self.assertEqual(denied.status_code, 403)
        self.assertTrue(PersonnelRecord.objects.filter(id=blocked_record.id).exists())

        self.client.force_authenticate(self.internal_user)
        internal_allowed = self.client.delete(f"/api/personnel/{internal_record.id}/")
        self.assertEqual(internal_allowed.status_code, 204)
        self.assertFalse(PersonnelRecord.objects.filter(id=internal_record.id).exists())
        self._assert_audit_row_exists(
            action="delete",
            entity_id=str(internal_record.id),
            expected_event=PERSONNEL_RECORD_DELETED_EVENT,
        )

        self.client.force_authenticate(self.admin_user)
        admin_denied = self.client.delete(f"/api/personnel/{admin_record.id}/")
        self.assertEqual(admin_denied.status_code, 403)
        self.assertTrue(PersonnelRecord.objects.filter(id=admin_record.id).exists())

    def test_appointment_history_hides_non_public_records_for_non_internal_users(self):
        position = GovernmentPosition.objects.create(
            title="Minister of Fisheries",
            branch="executive",
            institution="Ministry of Fisheries",
            appointment_authority="President",
            is_vacant=True,
            is_public=True,
        )
        AppointmentRecord.objects.create(
            position=position,
            nominee=self.record,
            nominated_by_display="Public Appointment",
            nomination_date=date.today(),
            status="nominated",
            is_public=True,
        )
        AppointmentRecord.objects.create(
            position=position,
            nominee=self.record,
            nominated_by_display="Private Appointment",
            nomination_date=date.today(),
            status="withdrawn",
            is_public=False,
        )

        self.client.force_authenticate(self.applicant_user)
        applicant_response = self.client.get(f"/api/personnel/{self.record.id}/appointment-history/")
        self.assertEqual(applicant_response.status_code, 200)
        applicant_rows = applicant_response.json()
        self.assertEqual(len(applicant_rows), 1)
        self.assertTrue(all(row["is_public"] for row in applicant_rows))

        self.client.force_authenticate(self.internal_user)
        internal_response = self.client.get(f"/api/personnel/{self.record.id}/appointment-history/")
        self.assertEqual(internal_response.status_code, 200)
        internal_rows = internal_response.json()
        self.assertEqual(len(internal_rows), 2)

    def test_internal_without_registry_role_is_denied_registry_endpoints(self):
        plain_internal_user = User.objects.create_user(
            email="personnel_plain_internal@example.com",
            password="Pass1234!",
            first_name="Plain",
            last_name="Reviewer",
            user_type="internal",
        )
        self.client.force_authenticate(plain_internal_user)

        list_response = self.client.get("/api/personnel/")
        create_response = self.client.post(
            "/api/personnel/",
            {
                "full_name": "Unauthorized Personnel",
                "is_public": False,
                "is_active_officeholder": False,
            },
            format="json",
        )

        self.assertEqual(list_response.status_code, 403)
        self.assertEqual(create_response.status_code, 403)


class PersonnelOrganizationScopeTests(APITestCase):
    def setUp(self):
        self.org_a = Organization.objects.create(code="per-org-a", name="Personnel Org A")
        self.org_b = Organization.objects.create(code="per-org-b", name="Personnel Org B")

        self.internal_a = User.objects.create_user(
            email="personnel_scope_a@example.com",
            password="Pass1234!",
            first_name="Personnel",
            last_name="ScopeA",
            user_type="internal",
        )
        self.registry_group, _ = Group.objects.get_or_create(name="registry_admin")
        self.internal_a.groups.add(self.registry_group)
        self.admin_user = User.objects.create_user(
            email="personnel_scope_admin@example.com",
            password="Pass1234!",
            first_name="Personnel",
            last_name="Admin",
            user_type="admin",
            is_staff=True,
            is_superuser=True,
        )
        OrganizationMembership.objects.create(
            user=self.internal_a,
            organization=self.org_a,
            is_active=True,
            is_default=True,
        )

        self.record_org_a = PersonnelRecord.objects.create(
            organization=self.org_a,
            full_name="Scoped Personnel A",
            is_public=True,
        )
        self.record_org_b = PersonnelRecord.objects.create(
            organization=self.org_b,
            full_name="Scoped Personnel B",
            is_public=False,
        )
        self.record_legacy = PersonnelRecord.objects.create(
            full_name="Legacy Personnel",
            is_public=True,
        )

    def _extract_results(self, response):
        payload = response.json()
        if isinstance(payload, dict) and "results" in payload:
            return payload["results"]
        return payload

    def test_list_is_scoped_to_membership_org_and_excludes_legacy_null_scope(self):
        self.client.force_authenticate(self.internal_a)
        response = self.client.get("/api/personnel/")
        self.assertEqual(response.status_code, 200)
        ids = {item["id"] for item in self._extract_results(response)}
        self.assertIn(str(self.record_org_a.id), ids)
        self.assertNotIn(str(self.record_legacy.id), ids)
        self.assertNotIn(str(self.record_org_b.id), ids)

    def test_delete_outside_org_is_denied_for_internal_but_allowed_for_admin(self):
        self.client.force_authenticate(self.internal_a)
        denied = self.client.delete(f"/api/personnel/{self.record_org_b.id}/")
        self.assertIn(denied.status_code, {403, 404})

        self.client.force_authenticate(self.admin_user)
        denied_admin = self.client.delete(f"/api/personnel/{self.record_org_b.id}/")
        self.assertEqual(denied_admin.status_code, 403)

    def test_membershipless_internal_without_registry_role_is_denied_registry_list(self):
        membershipless_internal = User.objects.create_user(
            email="personnel_scope_legacy_only@example.com",
            password="Pass1234!",
            first_name="Personnel",
            last_name="LegacyOnly",
            user_type="internal",
        )
        self.client.force_authenticate(membershipless_internal)
        response = self.client.get("/api/personnel/")
        self.assertEqual(response.status_code, 403)

    def test_membershipless_internal_cannot_create_personnel_without_org_context(self):
        membershipless_internal = User.objects.create_user(
            email="personnel_scope_create_denied@example.com",
            password="Pass1234!",
            first_name="Personnel",
            last_name="CreateDenied",
            user_type="internal",
        )
        self.client.force_authenticate(membershipless_internal)
        response = self.client.post(
            "/api/personnel/",
            {
                "full_name": "Membershipless Create Personnel",
                "is_public": True,
                "is_active_officeholder": False,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 403)



