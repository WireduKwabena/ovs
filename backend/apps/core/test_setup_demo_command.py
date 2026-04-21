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
from apps.users.models import User
from apps.billing.models import BillingSubscription, OrganizationOnboardingToken
from apps.campaigns.models import VettingCampaign
from apps.core.management.commands.setup_demo import APPOINTMENT_ROLE_GROUPS
from apps.governance.models import Committee, CommitteeMembership, OrganizationMembership
from apps.tenants.models import Organization
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
        self.assertFalse(admin_user.groups.filter(name__in=APPOINTMENT_ROLE_GROUPS).exists())
        self.assertFalse(OrganizationMembership.objects.filter(user=admin_user).exists())
        self.assertFalse(User.objects.get(email="gams.vetting@demo.local").is_staff)
        self.assertFalse(User.objects.get(email="gams.committee@demo.local").is_staff)
        self.assertFalse(User.objects.get(email="gams.committeechair@demo.local").is_staff)
        self.assertFalse(User.objects.get(email="gams.authority@demo.local").is_staff)
        self.assertFalse(User.objects.get(email="gams.registry@demo.local").is_staff)
        self.assertFalse(User.objects.get(email="gams.publication@demo.local").is_staff)
        self.assertFalse(User.objects.get(email="gams.auditor@demo.local").is_staff)

        expected_org_codes = {
            "public-service-commission",
            "appointments-secretariat",
            "parliamentary-appointments-committee",
            "office-of-the-president",
            "gazette-and-records-office",
            "audit-service",
            "legacy-unscoped",
        }
        self.assertSetEqual(set(Organization.objects.values_list("code", flat=True)), expected_org_codes)

        for email in {
            "gams.vetting@demo.local",
            "gams.committee@demo.local",
            "gams.committeechair@demo.local",
            "gams.authority@demo.local",
            "gams.registry@demo.local",
            "gams.publication@demo.local",
            "gams.auditor@demo.local",
        }:
            user = User.objects.get(email=email)
            self.assertTrue(OrganizationMembership.objects.filter(user=user, is_active=True).exists())
            self.assertEqual(OrganizationMembership.objects.filter(user=user, is_default=True, is_active=True).count(), 1)

        committee = Committee.objects.get(
            code="parliamentary-appointments-main",
            organization__code="public-service-commission",
        )
        committee_user = User.objects.get(email="gams.committee@demo.local")
        self.assertTrue(
            CommitteeMembership.objects.filter(committee=committee, user=committee_user, is_active=True).exists()
        )
        committee_chair_user = User.objects.get(email="gams.committeechair@demo.local")
        self.assertTrue(
            CommitteeMembership.objects.filter(
                committee=committee,
                user=committee_chair_user,
                committee_role="chair",
                is_active=True,
            ).exists()
        )

        campaign = VettingCampaign.objects.get(name="GAMS Demo Ministerial Exercise")
        self.assertEqual(campaign.status, "active")
        self.assertEqual(campaign.positions.count(), 2)
        self.assertIsNotNone(campaign.approval_template)
        committee_review_stage = campaign.approval_template.stages.filter(
            maps_to_status="committee_review"
        ).first()
        self.assertIsNotNone(committee_review_stage)
        self.assertEqual(committee_review_stage.committee_id, committee.id)

        minister_position = GovernmentPosition.objects.get(
            title="GAMS Demo Minister of Health",
            institution="Ministry of Health",
        )
        nomination_record = AppointmentRecord.objects.get(position=minister_position)
        self.assertEqual(nomination_record.status, "nominated")
        self.assertFalse(nomination_record.is_public)
        self.assertEqual(nomination_record.committee_id, committee.id)
        self.assertIsNone(nomination_record.appointment_date)
        self.assertEqual(nomination_record.publication.status, "draft")

        chief_justice_position = GovernmentPosition.objects.get(
            title="GAMS Demo Chief Justice",
            institution="Judiciary",
        )
        serving_record = AppointmentRecord.objects.get(position=chief_justice_position, status="serving")
        self.assertTrue(serving_record.is_public)
        self.assertEqual(serving_record.committee_id, committee.id)
        self.assertIsNotNone(serving_record.appointment_date)
        self.assertEqual(serving_record.publication.status, "published")
        self.assertIsNotNone(serving_record.publication.published_at)
        self.assertEqual(serving_record.publication.published_by.email, "gams.publication@demo.local")

        workflow_org = Organization.objects.get(code="public-service-commission")
        self.assertTrue(
            BillingSubscription.objects.filter(
                reference="GAMS-DEMO-ORG-SUBSCRIPTION",
                status="complete",
                payment_status="paid",
            ).exists()
        )
        self.assertTrue(
            OrganizationOnboardingToken.objects.filter(
                is_active=True,
            ).exists()
        )

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

        admin_user = User.objects.get(email="gams.admin@demo.local")
        admin_user.groups.add(*Group.objects.filter(name__in=APPOINTMENT_ROLE_GROUPS))
        OrganizationMembership.objects.create(
            user=admin_user,
            membership_role="system_admin",
            is_active=True,
            is_default=True,
            joined_at=timezone.now(),
        )

        call_command("setup_demo")

        nomination_record.refresh_from_db()
        publication.refresh_from_db()
        minister_position.refresh_from_db()
        admin_user.refresh_from_db()

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
        self.assertEqual(Organization.objects.filter(code="public-service-commission").count(), 1)
        self.assertEqual(
            OrganizationMembership.objects.filter(user__email="gams.admin@demo.local").count(),
            0,
        )
        self.assertFalse(admin_user.groups.filter(name__in=APPOINTMENT_ROLE_GROUPS).exists())
        self.assertEqual(Committee.objects.filter(code="parliamentary-appointments-main").count(), 1)
        self.assertEqual(
            CommitteeMembership.objects.filter(
                committee__code="parliamentary-appointments-main",
                user__email="gams.committee@demo.local",
                is_active=True,
            ).count(),
            1,
        )
        self.assertEqual(
            CommitteeMembership.objects.filter(
                committee__code="parliamentary-appointments-main",
                user__email="gams.committeechair@demo.local",
                committee_role="chair",
                is_active=True,
            ).count(),
            1,
        )
        self.assertEqual(
            BillingSubscription.objects.filter(
                organization__code="public-service-commission",
                reference="GAMS-DEMO-ORG-SUBSCRIPTION",
            ).count(),
            1,
        )
        self.assertEqual(
            OrganizationOnboardingToken.objects.filter(
                organization__code="public-service-commission",
                is_active=True,
            ).count(),
            1,
        )
