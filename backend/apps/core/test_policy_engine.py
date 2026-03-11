from __future__ import annotations

from django.contrib.auth.models import Group
from django.test import TestCase

from apps.authentication.models import User
from apps.core.authz import get_user_capabilities, get_user_roles
from apps.core.permissions import is_internal_or_admin_user
from apps.core.policies.appointment_policy import (
    actor_matches_stage_role,
    can_appoint,
    can_publish,
    can_take_committee_action,
    can_view_internal_record,
)
from apps.core.policies.audit_policy import can_view_audit
from apps.core.policies.registry_policy import can_manage_registry
from apps.governance.models import Committee, CommitteeMembership, Organization, OrganizationMembership


class PolicyEngineTests(TestCase):
    def setUp(self):
        self.org_a = Organization.objects.create(code="policy-org-a", name="Policy Org A")
        self.org_b = Organization.objects.create(code="policy-org-b", name="Policy Org B")
        self.committee_a = Committee.objects.create(
            organization=self.org_a,
            code="policy-committee-a",
            name="Policy Committee A",
            committee_type="approval",
        )

        self.admin = User.objects.create_user(
            email="policy.admin@example.com",
            password="Pass1234!",
            user_type="admin",
            is_staff=True,
            is_superuser=True,
        )
        self.hr = User.objects.create_user(
            email="policy.hr@example.com",
            password="Pass1234!",
            user_type="internal",
        )
        self.registry_admin = User.objects.create_user(
            email="policy.registry.admin@example.com",
            password="Pass1234!",
            user_type="internal",
        )
        self.authority = User.objects.create_user(
            email="policy.authority@example.com",
            password="Pass1234!",
            user_type="internal",
        )
        self.publisher = User.objects.create_user(
            email="policy.publisher@example.com",
            password="Pass1234!",
            user_type="internal",
        )
        self.auditor = User.objects.create_user(
            email="policy.auditor@example.com",
            password="Pass1234!",
            user_type="internal",
        )
        self.committee_member = User.objects.create_user(
            email="policy.committee.member@example.com",
            password="Pass1234!",
            user_type="internal",
        )
        self.group_only_committee_user = User.objects.create_user(
            email="policy.committee.group.only@example.com",
            password="Pass1234!",
            user_type="internal",
        )
        self.applicant = User.objects.create_user(
            email="policy.applicant@example.com",
            password="Pass1234!",
            user_type="applicant",
        )

        appointing_group, _ = Group.objects.get_or_create(name="appointing_authority")
        publication_group, _ = Group.objects.get_or_create(name="publication_officer")
        auditor_group, _ = Group.objects.get_or_create(name="auditor")
        committee_group, _ = Group.objects.get_or_create(name="committee_member")
        registry_group, _ = Group.objects.get_or_create(name="registry_admin")

        self.authority.groups.add(appointing_group)
        self.publisher.groups.add(publication_group)
        self.auditor.groups.add(auditor_group)
        self.committee_member.groups.add(committee_group)
        self.group_only_committee_user.groups.add(committee_group)
        self.registry_admin.groups.add(registry_group)

        self.internal_membership = OrganizationMembership.objects.create(
            user=self.hr,
            organization=self.org_a,
            is_active=True,
            is_default=True,
        )
        self.authority_membership = OrganizationMembership.objects.create(
            user=self.authority,
            organization=self.org_a,
            is_active=True,
            is_default=True,
        )
        self.registry_admin_membership = OrganizationMembership.objects.create(
            user=self.registry_admin,
            organization=self.org_a,
            is_active=True,
            is_default=True,
        )
        self.publisher_membership = OrganizationMembership.objects.create(
            user=self.publisher,
            organization=self.org_a,
            is_active=True,
            is_default=True,
        )
        self.committee_membership = OrganizationMembership.objects.create(
            user=self.committee_member,
            organization=self.org_a,
            is_active=True,
            is_default=True,
        )
        CommitteeMembership.objects.create(
            committee=self.committee_a,
            user=self.committee_member,
            organization_membership=self.committee_membership,
            committee_role="member",
            is_active=True,
        )

    def test_registry_policy_enforces_org_scope(self):
        self.assertTrue(
            can_manage_registry(
                self.registry_admin,
                organization_id=self.org_a.id,
                allow_membershipless_fallback=False,
            )
        )
        self.assertFalse(
            can_manage_registry(
                self.registry_admin,
                organization_id=self.org_b.id,
                allow_membershipless_fallback=False,
            )
        )
        self.assertFalse(
            can_manage_registry(
                self.hr,
                organization_id=self.org_a.id,
                allow_membershipless_fallback=False,
            )
        )

    def test_appoint_and_publish_policies_preserve_role_requirements(self):
        self.assertTrue(can_appoint(self.admin, organization_id=self.org_b.id))
        self.assertTrue(can_appoint(self.authority, organization_id=self.org_a.id))
        self.assertFalse(can_appoint(self.hr, organization_id=self.org_a.id))

        self.assertTrue(can_publish(self.publisher, organization_id=self.org_a.id))
        self.assertTrue(can_publish(self.authority, organization_id=self.org_a.id))
        self.assertFalse(can_publish(self.hr, organization_id=self.org_a.id))

    def test_committee_action_policy_requires_active_membership(self):
        self.assertTrue(
            can_take_committee_action(
                self.committee_member,
                committee=self.committee_a,
                appointment_organization_id=self.org_a.id,
            )
        )
        self.assertFalse(
            can_take_committee_action(
                self.group_only_committee_user,
                committee=self.committee_a,
                appointment_organization_id=self.org_a.id,
            )
        )
        self.assertTrue(
            can_take_committee_action(
                self.committee_member,
                committee_ids=[self.committee_a.id],
            )
        )

    def test_view_internal_record_policy_supports_org_enforcement_modes(self):
        self.assertTrue(
            can_view_internal_record(
                self.registry_admin,
                organization_id=self.org_a.id,
            )
        )
        self.assertFalse(
            can_view_internal_record(
                self.registry_admin,
                organization_id=self.org_b.id,
            )
        )
        self.assertFalse(
            can_view_internal_record(
                self.hr,
                organization_id=self.org_a.id,
            )
        )
        self.assertFalse(
            can_view_internal_record(
                self.hr,
                organization_id=None,
                allow_membershipless_fallback=False,
                enforce_org_scope_for_null=True,
            )
        )

    def test_audit_policy_and_stage_role_policy(self):
        self.assertTrue(can_view_audit(self.admin))
        self.assertTrue(can_view_audit(self.auditor))
        self.assertFalse(can_view_audit(self.hr))
        self.assertFalse(can_view_audit(self.applicant))

        self.assertTrue(actor_matches_stage_role(self.authority, "appointing_authority"))
        self.assertFalse(actor_matches_stage_role(self.hr, "appointing_authority"))

    def test_org_membership_roles_resolve_governance_capabilities(self):
        membership_role_user = User.objects.create_user(
            email="policy.membership.role@example.com",
            password="Pass1234!",
            user_type="internal",
        )
        OrganizationMembership.objects.create(
            user=membership_role_user,
            organization=self.org_a,
            membership_role="vetting_officer",
            is_active=True,
            is_default=True,
        )

        plain_internal_user = User.objects.create_user(
            email="policy.plain.hr@example.com",
            password="Pass1234!",
            user_type="internal",
        )

        derived_roles = get_user_roles(membership_role_user)
        self.assertIn("vetting_officer", derived_roles)
        self.assertIn("gams.appointment.stage", get_user_capabilities(membership_role_user))
        self.assertIn("gams.appointment.view_internal", get_user_capabilities(membership_role_user))

        plain_roles = get_user_roles(plain_internal_user)
        self.assertIn("internal", plain_roles)
        self.assertNotIn("vetting_officer", plain_roles)
        self.assertNotIn("gams.appointment.stage", get_user_capabilities(plain_internal_user))

    def test_legacy_internal_or_admin_helper_requires_operational_authority(self):
        self.assertTrue(is_internal_or_admin_user(self.admin))
        self.assertTrue(is_internal_or_admin_user(self.registry_admin))
        self.assertFalse(is_internal_or_admin_user(self.hr))
        self.assertFalse(is_internal_or_admin_user(self.applicant))



