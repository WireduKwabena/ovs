from datetime import date

from django.conf import settings
from django.contrib.auth.models import Group
from rest_framework.test import APITestCase

from apps.audit.contracts import (
    GOVERNMENT_POSITION_CREATED_EVENT,
    GOVERNMENT_POSITION_DELETED_EVENT,
    GOVERNMENT_POSITION_UPDATED_EVENT,
)
from apps.appointments.models import AppointmentRecord
from apps.authentication.models import User
from apps.governance.models import Organization, OrganizationMembership
from apps.personnel.models import PersonnelRecord
from apps.positions.models import GovernmentPosition


class GovernmentPositionApiTests(APITestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(
            email="positions_admin@example.com",
            password="Pass1234!",
            first_name="Pos",
            last_name="Admin",
            user_type="admin",
        )
        self.internal_user = User.objects.create_user(
            email="positions_hr@example.com",
            password="Pass1234!",
            first_name="Pos",
            last_name="Reviewer",
            user_type="internal",
        )
        self.registry_group, _ = Group.objects.get_or_create(name="registry_admin")
        self.internal_user.groups.add(self.registry_group)
        self.applicant_user = User.objects.create_user(
            email="positions_applicant@example.com",
            password="Pass1234!",
            first_name="Pos",
            last_name="Applicant",
            user_type="applicant",
        )
        GovernmentPosition.objects.create(
            title="Chief Justice",
            branch="judicial",
            institution="Judiciary",
            appointment_authority="President",
            is_public=True,
            is_vacant=True,
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
                entity_type="GovernmentPosition",
                entity_id=str(entity_id),
            )
            .order_by("-created_at")
            .first()
        )
        self.assertIsNotNone(row)
        if expected_event:
            self.assertEqual((row.changes or {}).get("event"), expected_event)

    def test_public_positions_available_without_auth(self):
        response = self.client.get("/api/positions/public/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)
        item = response.json()[0]
        self.assertNotIn("rubric", item)
        self.assertNotIn("required_qualifications", item)
        self.assertNotIn("current_holder", item)

    def test_create_position_requires_internal_or_admin(self):
        response = self.client.post(
            "/api/positions/",
            {
                "title": "Attorney General",
                "branch": "executive",
                "institution": "Ministry of Justice",
                "appointment_authority": "President",
            },
            format="json",
        )
        self.assertIn(response.status_code, {401, 403})

        # Platform admins are restricted to subscription + org status oversight only.
        self.client.force_authenticate(self.admin_user)
        denied = self.client.post(
            "/api/positions/",
            {
                "title": "Attorney General",
                "branch": "executive",
                "institution": "Ministry of Justice",
                "appointment_authority": "President",
            },
            format="json",
        )
        self.assertEqual(denied.status_code, 403)

        create_org = Organization.objects.create(code="positions-create-admin-guard", name="Positions Create Admin Guard")
        OrganizationMembership.objects.create(
            user=self.internal_user,
            organization=create_org,
            membership_role="registry_admin",
            is_active=True,
            is_default=True,
        )
        self.client.force_authenticate(self.internal_user)
        success = self.client.post(
            "/api/positions/",
            {
                "title": "Attorney General",
                "branch": "executive",
                "institution": "Ministry of Justice",
                "appointment_authority": "President",
                "organization": str(create_org.id),
            },
            format="json",
        )
        self.assertEqual(success.status_code, 201)
        self._assert_audit_row_exists(
            action="create",
            entity_id=success.json()["id"],
            expected_event=GOVERNMENT_POSITION_CREATED_EVENT,
        )

    def test_positions_list_allows_internal_and_admin_but_blocks_applicant(self):
        unauthenticated = self.client.get("/api/positions/")
        self.assertIn(unauthenticated.status_code, {401, 403})

        self.client.force_authenticate(self.applicant_user)
        denied = self.client.get("/api/positions/")
        self.assertEqual(denied.status_code, 403)

        self.client.force_authenticate(self.internal_user)
        internal_allowed = self.client.get("/api/positions/")
        self.assertEqual(internal_allowed.status_code, 200)
        self.assertGreaterEqual(len(self._extract_results(internal_allowed)), 1)

        self.client.force_authenticate(self.admin_user)
        denied = self.client.get("/api/positions/")
        self.assertEqual(denied.status_code, 403)

    def test_positions_create_allows_internal_and_admin_but_blocks_applicant(self):
        create_org = Organization.objects.create(code="positions-create-org", name="Positions Create Org")
        OrganizationMembership.objects.create(
            user=self.internal_user,
            organization=create_org,
            is_active=True,
            is_default=True,
        )
        payload = {
            "title": "Minister of Communications",
            "branch": "executive",
            "institution": "Ministry of Communications",
            "appointment_authority": "President",
            "organization": str(create_org.id),
        }

        self.client.force_authenticate(self.applicant_user)
        denied = self.client.post("/api/positions/", payload, format="json")
        self.assertEqual(denied.status_code, 403)

        self.client.force_authenticate(self.internal_user)
        internal_allowed = self.client.post(
            "/api/positions/",
            {**payload, "title": "Minister of Communications (Internal)"},
            format="json",
        )
        self.assertEqual(internal_allowed.status_code, 201)
        self._assert_audit_row_exists(
            action="create",
            entity_id=internal_allowed.json()["id"],
            expected_event=GOVERNMENT_POSITION_CREATED_EVENT,
        )

        self.client.force_authenticate(self.admin_user)
        admin_denied = self.client.post(
            "/api/positions/",
            {**payload, "title": "Minister of Communications (Admin)"},
            format="json",
        )
        self.assertEqual(admin_denied.status_code, 403)

    def test_positions_update_allows_internal_and_admin_but_blocks_applicant(self):
        position = GovernmentPosition.objects.first()
        self.assertIsNotNone(position)
        detail_url = f"/api/positions/{position.id}/"

        self.client.force_authenticate(self.applicant_user)
        denied = self.client.patch(detail_url, {"title": "Blocked Update"}, format="json")
        self.assertEqual(denied.status_code, 403)

        self.client.force_authenticate(self.internal_user)
        internal_allowed = self.client.patch(
            detail_url,
            {"title": "Updated By Internal Reviewer"},
            format="json",
        )
        self.assertEqual(internal_allowed.status_code, 200)
        self._assert_audit_row_exists(
            action="update",
            entity_id=str(position.id),
            expected_event=GOVERNMENT_POSITION_UPDATED_EVENT,
        )

        self.client.force_authenticate(self.admin_user)
        admin_denied = self.client.patch(detail_url, {"title": "Updated By Admin"}, format="json")
        self.assertEqual(admin_denied.status_code, 403)

    def test_positions_delete_allows_internal_and_admin_but_blocks_applicant(self):
        blocked_position = GovernmentPosition.objects.create(
            title="Delete Blocked Position",
            branch="executive",
            institution="Office A",
            appointment_authority="President",
            is_public=False,
            is_vacant=True,
        )
        internal_position = GovernmentPosition.objects.create(
            title="Delete Internal Position",
            branch="executive",
            institution="Office B",
            appointment_authority="President",
            is_public=False,
            is_vacant=True,
        )
        admin_position = GovernmentPosition.objects.create(
            title="Delete Admin Position",
            branch="executive",
            institution="Office C",
            appointment_authority="President",
            is_public=False,
            is_vacant=True,
        )

        self.client.force_authenticate(self.applicant_user)
        denied = self.client.delete(f"/api/positions/{blocked_position.id}/")
        self.assertEqual(denied.status_code, 403)
        self.assertTrue(GovernmentPosition.objects.filter(id=blocked_position.id).exists())

        self.client.force_authenticate(self.internal_user)
        internal_allowed = self.client.delete(f"/api/positions/{internal_position.id}/")
        self.assertEqual(internal_allowed.status_code, 204)
        self.assertFalse(GovernmentPosition.objects.filter(id=internal_position.id).exists())
        self._assert_audit_row_exists(
            action="delete",
            entity_id=str(internal_position.id),
            expected_event=GOVERNMENT_POSITION_DELETED_EVENT,
        )

        self.client.force_authenticate(self.admin_user)
        admin_denied = self.client.delete(f"/api/positions/{admin_position.id}/")
        self.assertEqual(admin_denied.status_code, 403)
        self.assertTrue(GovernmentPosition.objects.filter(id=admin_position.id).exists())

    def test_appointment_history_hides_non_public_records_for_non_internal_users(self):
        position = GovernmentPosition.objects.first()
        self.assertIsNotNone(position)
        public_nominee = PersonnelRecord.objects.create(full_name="Public Nominee")
        private_nominee = PersonnelRecord.objects.create(full_name="Private Nominee")
        AppointmentRecord.objects.create(
            position=position,
            nominee=public_nominee,
            nominated_by_display="Public Appointment",
            nomination_date=date.today(),
            status="nominated",
            is_public=True,
        )
        AppointmentRecord.objects.create(
            position=position,
            nominee=private_nominee,
            nominated_by_display="Private Appointment",
            nomination_date=date.today(),
            status="nominated",
            is_public=False,
        )

        self.client.force_authenticate(self.applicant_user)
        applicant_response = self.client.get(f"/api/positions/{position.id}/appointment-history/")
        self.assertEqual(applicant_response.status_code, 200)
        applicant_rows = applicant_response.json()
        self.assertEqual(len(applicant_rows), 1)
        self.assertTrue(all(row["is_public"] for row in applicant_rows))

        self.client.force_authenticate(self.internal_user)
        internal_response = self.client.get(f"/api/positions/{position.id}/appointment-history/")
        self.assertEqual(internal_response.status_code, 200)
        internal_rows = internal_response.json()
        self.assertEqual(len(internal_rows), 2)

    def test_internal_without_registry_role_is_denied_registry_endpoints(self):
        plain_internal_user = User.objects.create_user(
            email="positions_plain_internal@example.com",
            password="Pass1234!",
            first_name="Plain",
            last_name="Reviewer",
            user_type="internal",
        )
        self.client.force_authenticate(plain_internal_user)

        list_response = self.client.get("/api/positions/")
        create_response = self.client.post(
            "/api/positions/",
            {
                "title": "Unauthorized Position",
                "branch": "executive",
                "institution": "Unauthorized Registry",
                "appointment_authority": "President",
            },
            format="json",
        )

        self.assertEqual(list_response.status_code, 403)
        self.assertEqual(create_response.status_code, 403)


class GovernmentPositionOrganizationScopeTests(APITestCase):
    def setUp(self):
        self.org_a = Organization.objects.create(code="pos-org-a", name="Positions Org A")
        self.org_b = Organization.objects.create(code="pos-org-b", name="Positions Org B")

        self.internal_a = User.objects.create_user(
            email="positions_scope_a@example.com",
            password="Pass1234!",
            first_name="Scope",
            last_name="A",
            user_type="internal",
        )
        self.internal_b = User.objects.create_user(
            email="positions_scope_b@example.com",
            password="Pass1234!",
            first_name="Scope",
            last_name="B",
            user_type="internal",
        )
        self.registry_group, _ = Group.objects.get_or_create(name="registry_admin")
        self.internal_a.groups.add(self.registry_group)
        self.internal_b.groups.add(self.registry_group)
        self.admin_user = User.objects.create_user(
            email="positions_scope_admin@example.com",
            password="Pass1234!",
            first_name="Scope",
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
        OrganizationMembership.objects.create(
            user=self.internal_b,
            organization=self.org_b,
            is_active=True,
            is_default=True,
        )

        self.position_org_a = GovernmentPosition.objects.create(
            organization=self.org_a,
            title="Scoped Position A",
            branch="executive",
            institution="Org A Office",
            appointment_authority="President",
        )
        self.position_org_b = GovernmentPosition.objects.create(
            organization=self.org_b,
            title="Scoped Position B",
            branch="executive",
            institution="Org B Office",
            appointment_authority="President",
        )
        self.position_legacy = GovernmentPosition.objects.create(
            title="Legacy Position",
            branch="executive",
            institution="Legacy Office",
            appointment_authority="President",
        )

    def _extract_results(self, response):
        payload = response.json()
        if isinstance(payload, dict) and "results" in payload:
            return payload["results"]
        return payload

    def test_list_is_scoped_to_membership_org_and_excludes_legacy_null_scope(self):
        self.client.force_authenticate(self.internal_a)
        response = self.client.get("/api/positions/")
        self.assertEqual(response.status_code, 200)
        ids = {item["id"] for item in self._extract_results(response)}
        self.assertIn(str(self.position_org_a.id), ids)
        self.assertNotIn(str(self.position_legacy.id), ids)
        self.assertNotIn(str(self.position_org_b.id), ids)

    def test_update_outside_membership_org_is_denied_for_internal_but_allowed_for_admin(self):
        self.client.force_authenticate(self.internal_a)
        denied = self.client.patch(
            f"/api/positions/{self.position_org_b.id}/",
            {"title": "Blocked Cross Org Update"},
            format="json",
        )
        self.assertIn(denied.status_code, {403, 404})

        self.client.force_authenticate(self.admin_user)
        denied_admin = self.client.patch(
            f"/api/positions/{self.position_org_b.id}/",
            {"title": "Admin Cross Org Update"},
            format="json",
        )
        self.assertEqual(denied_admin.status_code, 403)

    def test_membershipless_internal_without_registry_role_is_denied_registry_list(self):
        membershipless_internal = User.objects.create_user(
            email="positions_scope_legacy_only@example.com",
            password="Pass1234!",
            first_name="Scope",
            last_name="LegacyOnly",
            user_type="internal",
        )
        self.client.force_authenticate(membershipless_internal)
        response = self.client.get("/api/positions/")
        self.assertEqual(response.status_code, 403)

    def test_membershipless_internal_cannot_create_position_without_org_context(self):
        membershipless_internal = User.objects.create_user(
            email="positions_scope_create_denied@example.com",
            password="Pass1234!",
            first_name="Scope",
            last_name="CreateDenied",
            user_type="internal",
        )
        self.client.force_authenticate(membershipless_internal)
        response = self.client.post(
            "/api/positions/",
            {
                "title": "Membershipless Create Position",
                "branch": "executive",
                "institution": "Legacy Office",
                "appointment_authority": "President",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 403)



