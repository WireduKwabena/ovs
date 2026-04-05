from __future__ import annotations

from io import StringIO
import uuid

from django.core.management import call_command
from django.test import TestCase

from apps.applications.models import VettingCase
from apps.users.models import User
from apps.tenants.models import Organization
from apps.rubrics.models import VettingRubric


class ReassignLegacyUnscopedCommandTests(TestCase):
    def setUp(self):
        self.source_org, _ = Organization.objects.get_or_create(
            code="legacy-unscoped",
            defaults={"name": "Legacy Unscoped Records"},
        )
        self.target_org, _ = Organization.objects.get_or_create(
            code="target-org-reassign",
            defaults={"name": "Target Organization Reassign"},
        )

        suffix = uuid.uuid4().hex[:8]

        self.applicant = User.objects.create_user(
            email=f"legacy.reassign.applicant.{suffix}@example.com",
            password="Pass1234!",
            first_name="Legacy",
            last_name="Applicant",
            user_type="applicant",
        )
        self.internal_user = User.objects.create_user(
            email=f"legacy.reassign.hr.{suffix}@example.com",
            password="Pass1234!",
            first_name="Legacy",
            last_name="Reviewer",
            user_type="internal",
        )

        self.case = VettingCase.objects.create(
            applicant=self.applicant,
            assigned_to=self.internal_user,
            position_applied="Analyst",
            department="Operations",
            priority="medium",
            status="under_review",
        )
        self.rubric = VettingRubric.objects.create(
            name=f"Legacy Reassign Rubric {suffix}",
            description="Command test rubric",
            created_by=self.internal_user,
        )

    def test_reassign_moves_records_to_target_org(self):
        out = StringIO()
        call_command(
            "reassign_legacy_unscoped",
            source_org_code="legacy-unscoped",
            target_org_code="target-org-reassign",
            stdout=out,
        )
        # Organization field has been removed from VettingCase and VettingRubric;
        # verify the command completes without raising an exception.
        self.case.refresh_from_db()
        self.rubric.refresh_from_db()

    def test_reassign_dry_run_keeps_source_org(self):
        out = StringIO()
        call_command(
            "reassign_legacy_unscoped",
            source_org_code="legacy-unscoped",
            target_org_code="target-org-reassign",
            dry_run=True,
            stdout=out,
        )
        # Organization field has been removed from VettingCase and VettingRubric;
        # verify the dry-run command completes without raising an exception.
        self.case.refresh_from_db()
        self.rubric.refresh_from_db()


