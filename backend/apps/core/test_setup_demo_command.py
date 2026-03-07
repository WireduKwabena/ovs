from __future__ import annotations

from datetime import date
from io import StringIO
from unittest.mock import patch

from django.contrib.auth.models import Group
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import timezone

from apps.appointments.models import AppointmentRecord
from apps.authentication.models import User
from apps.campaigns.models import VettingCampaign
from apps.core.management.commands.setup_demo import APPOINTMENT_ROLE_GROUPS
from apps.personnel.models import PersonnelRecord
from apps.positions.models import GovernmentPosition


class SetupDemoCommandTests(TestCase):
    def test_setup_demo_surfaces_migration_preflight_error(self):
        with patch("apps.core.management.commands.setup_demo.connection.introspection.table_names", return_value=[]):
            with self.assertRaises(CommandError) as ctx:
                call_command("setup_demo")

        self.assertIn("Run `python manage.py migrate`", str(ctx.exception))

    def test_setup_demo_creates_expected_gams_demo_records(self):
        stdout = StringIO()
        call_command("setup_demo", stdout=stdout)

        for group_name in APPOINTMENT_ROLE_GROUPS:
            self.assertTrue(Group.objects.filter(name=group_name).exists())

        admin_user = User.objects.get(email="gams.admin@demo.local")
        self.assertTrue(admin_user.is_superuser)
        self.assertTrue(admin_user.is_staff)
        self.assertFalse(User.objects.get(email="gams.vetting@demo.local").is_staff)
        self.assertFalse(User.objects.get(email="gams.committee@demo.local").is_staff)
        self.assertFalse(User.objects.get(email="gams.authority@demo.local").is_staff)
        self.assertFalse(User.objects.get(email="gams.registry@demo.local").is_staff)
        self.assertFalse(User.objects.get(email="gams.publication@demo.local").is_staff)
        self.assertFalse(User.objects.get(email="gams.auditor@demo.local").is_staff)

        campaign = VettingCampaign.objects.get(name="GAMS Demo Ministerial Exercise")
        self.assertEqual(campaign.status, "active")
        self.assertEqual(campaign.positions.count(), 2)
        self.assertIsNotNone(campaign.approval_template)

        minister_position = GovernmentPosition.objects.get(
            title="GAMS Demo Minister of Health",
            institution="Ministry of Health",
        )
        nomination_record = AppointmentRecord.objects.get(position=minister_position)
        self.assertEqual(nomination_record.status, "nominated")
        self.assertFalse(nomination_record.is_public)
        self.assertIsNone(nomination_record.appointment_date)
        self.assertEqual(nomination_record.publication.status, "draft")

        chief_justice_position = GovernmentPosition.objects.get(
            title="GAMS Demo Chief Justice",
            institution="Judiciary",
        )
        serving_record = AppointmentRecord.objects.get(position=chief_justice_position, status="serving")
        self.assertTrue(serving_record.is_public)
        self.assertIsNotNone(serving_record.appointment_date)
        self.assertEqual(serving_record.publication.status, "published")
        self.assertIsNotNone(serving_record.publication.published_at)

    def test_setup_demo_is_idempotent_and_resets_demo_nomination_state(self):
        call_command("setup_demo")

        minister_position = GovernmentPosition.objects.get(
            title="GAMS Demo Minister of Health",
            institution="Ministry of Health",
        )
        nomination_record = AppointmentRecord.objects.get(position=minister_position)
        nominee = PersonnelRecord.objects.get(id=nomination_record.nominee_id)
        nomination_record.status = "serving"
        nomination_record.appointment_date = date.today()
        nomination_record.is_public = True
        nomination_record.gazette_number = "TEMP-GAZ-001"
        nomination_record.gazette_date = date.today()
        nomination_record.final_decision_by_display = "Temporary Decision"
        nomination_record.save(
            update_fields=[
                "status",
                "appointment_date",
                "is_public",
                "gazette_number",
                "gazette_date",
                "final_decision_by_display",
                "updated_at",
            ]
        )

        publication = nomination_record.publication
        publication.status = "revoked"
        publication.published_at = timezone.now()
        publication.revoked_at = timezone.now()
        publication.revocation_reason = "Temporary test mutation"
        publication.save(update_fields=["status", "published_at", "revoked_at", "revocation_reason", "updated_at"])

        minister_position.current_holder = nominee
        minister_position.is_vacant = False
        minister_position.save(update_fields=["current_holder", "is_vacant", "updated_at"])

        call_command("setup_demo")

        nomination_record.refresh_from_db()
        publication.refresh_from_db()
        minister_position.refresh_from_db()

        self.assertEqual(nomination_record.status, "nominated")
        self.assertFalse(nomination_record.is_public)
        self.assertIsNone(nomination_record.appointment_date)
        self.assertEqual(nomination_record.gazette_number, "")
        self.assertIsNone(nomination_record.gazette_date)
        self.assertEqual(nomination_record.final_decision_by_display, "")

        self.assertEqual(publication.status, "draft")
        self.assertIsNone(publication.published_at)
        self.assertIsNone(publication.revoked_at)
        self.assertEqual(publication.revocation_reason, "")
        self.assertEqual(publication.publication_reference, "")

        self.assertTrue(minister_position.is_vacant)
        self.assertIsNone(minister_position.current_holder)

        self.assertEqual(VettingCampaign.objects.filter(name="GAMS Demo Ministerial Exercise").count(), 1)
        self.assertEqual(User.objects.filter(email="gams.admin@demo.local").count(), 1)
