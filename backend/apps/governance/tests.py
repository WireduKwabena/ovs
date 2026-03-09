from __future__ import annotations

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from django.test import TestCase
from django.test import override_settings
from rest_framework.exceptions import ValidationError as DRFValidationError

from apps.authentication.models import User
from apps.billing.models import BillingSubscription
from apps.core.authz import ROLE_COMMITTEE_CHAIR, ROLE_COMMITTEE_MEMBER, get_user_roles

from .models import Committee, CommitteeMembership, Organization, OrganizationMembership
from .serializers import CommitteeMembershipSerializer


class GovernanceModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="gov.member@example.com",
            password="TestPass123!",
            first_name="Gov",
            last_name="Member",
            user_type="hr_manager",
            organization="Legacy Secretariat",
        )
        self.organization = Organization.objects.create(
            code="legacy-secretariat",
            name="Legacy Secretariat",
            organization_type="agency",
        )
        self.membership = OrganizationMembership.objects.create(
            user=self.user,
            organization=self.organization,
            membership_role="officer",
            is_default=True,
        )
        self.committee = Committee.objects.create(
            organization=self.organization,
            code="vetting-main",
            name="Main Vetting Committee",
            committee_type="vetting",
        )

    def test_user_effective_organization_prefers_governance_membership(self):
        self.assertEqual(self.user.effective_organization_name, "Legacy Secretariat")
        self.assertEqual(self.user.primary_organization_code, "legacy-secretariat")

    def test_user_effective_organization_falls_back_to_legacy_string(self):
        self.membership.is_active = False
        self.membership.is_default = False
        self.membership.save(update_fields=["is_active", "is_default", "updated_at"])

        self.assertEqual(self.user.effective_organization_name, "Legacy Secretariat")
        self.assertEqual(self.user.primary_organization_code, "")

    def test_only_one_active_default_membership_allowed(self):
        second_org = Organization.objects.create(code="alt-org", name="Alt Org")
        with self.assertRaises(IntegrityError):
            OrganizationMembership.objects.create(
                user=self.user,
                organization=second_org,
                is_active=True,
                is_default=True,
            )

    def test_org_membership_unique_user_org_constraint_enforced(self):
        with self.assertRaises(IntegrityError):
            OrganizationMembership.objects.create(
                user=self.user,
                organization=self.organization,
                membership_role="officer",
                is_active=True,
                is_default=False,
            )

    def test_observer_membership_must_be_non_voting(self):
        with self.assertRaises(IntegrityError):
            CommitteeMembership.objects.create(
                committee=self.committee,
                user=self.user,
                organization_membership=self.membership,
                committee_role="observer",
                can_vote=True,
            )

    def test_committee_membership_maps_to_authz_roles(self):
        CommitteeMembership.objects.create(
            committee=self.committee,
            user=self.user,
            organization_membership=self.membership,
            committee_role="member",
            can_vote=True,
        )
        roles = get_user_roles(self.user)
        self.assertIn(ROLE_COMMITTEE_MEMBER, roles)
        self.assertNotIn(ROLE_COMMITTEE_CHAIR, roles)

    def test_committee_chair_membership_maps_to_chair_role(self):
        CommitteeMembership.objects.create(
            committee=self.committee,
            user=self.user,
            organization_membership=self.membership,
            committee_role="chair",
            can_vote=True,
        )
        roles = get_user_roles(self.user)
        self.assertIn(ROLE_COMMITTEE_MEMBER, roles)
        self.assertIn(ROLE_COMMITTEE_CHAIR, roles)

    def test_committee_secretary_membership_maps_to_committee_member_role(self):
        CommitteeMembership.objects.create(
            committee=self.committee,
            user=self.user,
            organization_membership=self.membership,
            committee_role="secretary",
            can_vote=True,
        )
        roles = get_user_roles(self.user)
        self.assertIn(ROLE_COMMITTEE_MEMBER, roles)
        self.assertNotIn(ROLE_COMMITTEE_CHAIR, roles)

    def test_committee_observer_membership_does_not_map_to_committee_actor_roles(self):
        CommitteeMembership.objects.create(
            committee=self.committee,
            user=self.user,
            organization_membership=self.membership,
            committee_role="observer",
            can_vote=False,
        )
        roles = get_user_roles(self.user)
        self.assertNotIn(ROLE_COMMITTEE_MEMBER, roles)
        self.assertNotIn(ROLE_COMMITTEE_CHAIR, roles)

    def test_committee_enforces_single_active_chair(self):
        first_chair = CommitteeMembership.objects.create(
            committee=self.committee,
            user=self.user,
            organization_membership=self.membership,
            committee_role="chair",
            can_vote=True,
        )
        self.assertEqual(first_chair.committee_role, "chair")

        second_user = User.objects.create_user(
            email="gov.second.chair@example.com",
            password="TestPass123!",
            first_name="Gov",
            last_name="SecondChair",
            user_type="hr_manager",
            organization="Legacy Secretariat",
        )
        second_membership = OrganizationMembership.objects.create(
            user=second_user,
            organization=self.organization,
            membership_role="officer",
            is_default=False,
        )

        with self.assertRaises(IntegrityError):
            CommitteeMembership.objects.create(
                committee=self.committee,
                user=second_user,
                organization_membership=second_membership,
                committee_role="chair",
                can_vote=True,
            )

    def test_assign_active_chair_reassigns_existing_chair_safely(self):
        current_chair = CommitteeMembership.objects.create(
            committee=self.committee,
            user=self.user,
            organization_membership=self.membership,
            committee_role="chair",
            can_vote=True,
        )

        next_user = User.objects.create_user(
            email="gov.next.chair@example.com",
            password="TestPass123!",
            first_name="Gov",
            last_name="NextChair",
            user_type="hr_manager",
            organization="Legacy Secretariat",
        )
        next_org_membership = OrganizationMembership.objects.create(
            user=next_user,
            organization=self.organization,
            membership_role="officer",
            is_default=False,
        )
        next_membership = CommitteeMembership.objects.create(
            committee=self.committee,
            user=next_user,
            organization_membership=next_org_membership,
            committee_role="member",
            can_vote=True,
        )

        promoted = CommitteeMembership.assign_active_chair(
            committee=self.committee,
            user=next_user,
            organization_membership=next_org_membership,
            can_vote=True,
        )

        current_chair.refresh_from_db()
        next_membership.refresh_from_db()
        self.assertEqual(str(promoted.id), str(next_membership.id))
        self.assertEqual(next_membership.committee_role, "chair")
        self.assertEqual(current_chair.committee_role, "member")

        active_chairs = CommitteeMembership.objects.filter(
            committee=self.committee,
            committee_role="chair",
            is_active=True,
        )
        self.assertEqual(active_chairs.count(), 1)
        self.assertEqual(active_chairs.first().user_id, next_user.id)

    def test_assign_active_chair_requires_matching_org_membership(self):
        alternate_org = Organization.objects.create(code="alt-chair-org", name="Alt Chair Org")
        mismatch_membership = OrganizationMembership.objects.create(
            user=self.user,
            organization=alternate_org,
            membership_role="officer",
            is_default=False,
        )

        with self.assertRaises(DjangoValidationError):
            CommitteeMembership.assign_active_chair(
                committee=self.committee,
                user=self.user,
                organization_membership=mismatch_membership,
                can_vote=True,
            )

    def test_committee_membership_serializer_rejects_cross_org_membership(self):
        foreign_org = Organization.objects.create(code="foreign-org", name="Foreign Org")
        foreign_membership = OrganizationMembership.objects.create(
            user=self.user,
            organization=foreign_org,
            membership_role="officer",
            is_default=False,
        )

        serializer = CommitteeMembershipSerializer(
            data={
                "committee": str(self.committee.id),
                "user": str(self.user.id),
                "organization_membership": str(foreign_membership.id),
                "committee_role": "member",
                "can_vote": True,
                "is_active": True,
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("organization_membership", serializer.errors)

    @override_settings(
        BILLING_ORG_MEMBER_QUOTA_ENFORCEMENT_ENABLED=True,
        BILLING_PLAN_STARTER_ORG_SEATS=1,
    )
    def test_membership_create_respects_org_seat_quota_when_org_has_active_subscription(self):
        BillingSubscription.objects.create(
            provider="sandbox",
            organization=self.organization,
            status="complete",
            payment_status="paid",
            plan_id="starter",
            plan_name="Starter",
            billing_cycle="monthly",
            payment_method="card",
            amount_usd="149.00",
            reference="GOV-SEAT-ENFORCE-CREATE",
        )
        second_user = User.objects.create_user(
            email="gov.second@example.com",
            password="TestPass123!",
            first_name="Gov",
            last_name="Second",
            user_type="hr_manager",
        )

        with self.assertRaises(DRFValidationError) as exc:
            OrganizationMembership.objects.create(
                user=second_user,
                organization=self.organization,
                membership_role="officer",
                is_active=True,
                is_default=False,
            )

        self.assertEqual(exc.exception.detail.get("code"), "ORG_SEAT_QUOTA_EXCEEDED")
        self.assertFalse(
            OrganizationMembership.objects.filter(
                user=second_user,
                organization=self.organization,
                is_active=True,
            ).exists()
        )

    @override_settings(
        BILLING_ORG_MEMBER_QUOTA_ENFORCEMENT_ENABLED=True,
        BILLING_PLAN_STARTER_ORG_SEATS=1,
    )
    def test_membership_activation_respects_org_seat_quota_when_org_has_active_subscription(self):
        BillingSubscription.objects.create(
            provider="sandbox",
            organization=self.organization,
            status="complete",
            payment_status="paid",
            plan_id="starter",
            plan_name="Starter",
            billing_cycle="monthly",
            payment_method="card",
            amount_usd="149.00",
            reference="GOV-SEAT-ENFORCE-ACTIVATE",
        )
        inactive_user = User.objects.create_user(
            email="gov.inactive@example.com",
            password="TestPass123!",
            first_name="Gov",
            last_name="Inactive",
            user_type="hr_manager",
        )
        inactive_membership = OrganizationMembership.objects.create(
            user=inactive_user,
            organization=self.organization,
            membership_role="officer",
            is_active=False,
            is_default=False,
        )

        inactive_membership.is_active = True
        with self.assertRaises(DRFValidationError) as exc:
            inactive_membership.save(update_fields=["is_active", "updated_at"])

        self.assertEqual(exc.exception.detail.get("code"), "ORG_SEAT_QUOTA_EXCEEDED")
