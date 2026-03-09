from __future__ import annotations

from datetime import date
from unittest.mock import patch

from django.core.checks import Error, Warning
from django.test import TestCase, override_settings

from apps.appointments.models import AppointmentRecord
from apps.applications.models import VettingCase
from apps.authentication.models import User
from apps.campaigns.models import VettingCampaign
from apps.core.checks import enforce_tenant_internal_org_integrity
from apps.governance.models import Organization
from apps.personnel.models import PersonnelRecord
from apps.positions.models import GovernmentPosition


class TenantIntegrityChecksTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="tenant-checks@example.com",
            password="Pass1234!",
            first_name="Tenant",
            last_name="Checks",
            user_type="admin",
            is_staff=True,
            is_superuser=True,
        )

    @override_settings(
        TENANT_ORG_INTEGRITY_CHECK_ENABLED=True,
        TENANT_FAIL_ON_NULL_ORG_INTERNAL_RECORDS=False,
    )
    def test_null_org_internal_rows_emit_warning(self):
        GovernmentPosition.objects.create(
            title="Tenant Null Org Position",
            branch="executive",
            institution="Legacy Office",
            appointment_authority="President",
        )

        findings = enforce_tenant_internal_org_integrity(app_configs=None)

        ids = {item.id for item in findings}
        self.assertIn("core.W010", ids)
        self.assertTrue(any(isinstance(item, Warning) and item.id == "core.W010" for item in findings))

    @override_settings(
        TENANT_ORG_INTEGRITY_CHECK_ENABLED=True,
        TENANT_FAIL_ON_NULL_ORG_INTERNAL_RECORDS=True,
    )
    def test_null_org_internal_rows_emit_error_when_fail_flag_enabled(self):
        PersonnelRecord.objects.create(full_name="Tenant Null Org Personnel")

        findings = enforce_tenant_internal_org_integrity(app_configs=None)

        ids = {item.id for item in findings}
        self.assertIn("core.E010", ids)
        self.assertTrue(any(isinstance(item, Error) and item.id == "core.E010" for item in findings))

    @override_settings(
        TENANT_ORG_INTEGRITY_CHECK_ENABLED=True,
        TENANT_FAIL_ON_CROSS_ORG_LINKAGE_MISMATCH=False,
    )
    def test_cross_org_appointment_linkage_emits_warning(self):
        org_a = Organization.objects.create(code="tenant-check-a", name="Tenant Check Org A")
        org_b = Organization.objects.create(code="tenant-check-b", name="Tenant Check Org B")

        position = GovernmentPosition.objects.create(
            organization=org_b,
            title="Tenant Mismatch Position",
            branch="executive",
            institution="Org B Office",
            appointment_authority="President",
            is_vacant=True,
        )
        nominee = PersonnelRecord.objects.create(
            organization=org_b,
            full_name="Tenant Mismatch Nominee",
        )
        exercise = VettingCampaign.objects.create(
            organization=org_b,
            name="Tenant Mismatch Campaign",
            initiated_by=self.user,
            status="active",
        )
        case = VettingCase.objects.create(
            organization=org_b,
            applicant=self.user,
            assigned_to=self.user,
            position_applied="Tenant Mismatch Position",
            department="Operations",
            priority="medium",
            status="under_review",
        )

        AppointmentRecord.objects.create(
            organization=org_a,
            position=position,
            nominee=nominee,
            appointment_exercise=exercise,
            vetting_case=case,
            nominated_by_user=self.user,
            nominated_by_display="Tenant Check",
            nomination_date=date.today(),
            status="nominated",
        )

        findings = enforce_tenant_internal_org_integrity(app_configs=None)

        ids = {item.id for item in findings}
        self.assertIn("core.W011", ids)
        self.assertTrue(any(isinstance(item, Warning) and item.id == "core.W011" for item in findings))

    @override_settings(
        TENANT_ORG_INTEGRITY_CHECK_ENABLED=True,
    )
    @patch("apps.core.checks._has_pending_migrations", return_value=True)
    def test_pending_migrations_emit_warning_and_skip_row_checks(self, _mock_pending):
        GovernmentPosition.objects.create(
            title="Tenant Pending Migration Position",
            branch="executive",
            institution="Legacy Office",
            appointment_authority="President",
        )

        findings = enforce_tenant_internal_org_integrity(app_configs=None)
        ids = {item.id for item in findings}
        self.assertIn("core.W012", ids)
        self.assertNotIn("core.W010", ids)
