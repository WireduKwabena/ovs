from __future__ import annotations

from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from django.test import TestCase
from django.test import override_settings
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.test import APITestCase

from apps.users.models import User
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
            user_type="internal",
            organization="Legacy Secretariat",
        )
        self.organization = Organization.objects.create(
            code="legacy-secretariat",
            name="Legacy Secretariat",
            organization_type="agency",
        )
        self.membership = OrganizationMembership.objects.create(
            user=self.user,
            membership_role="officer",
            is_default=True,
        )
        self.committee = Committee.objects.create(
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
                is_active=True,
                is_default=True,
            )

    def test_org_membership_unique_user_org_constraint_enforced(self):
        with self.assertRaises(IntegrityError):
            OrganizationMembership.objects.create(
                user=self.user,
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
            user_type="internal",
            organization="Legacy Secretariat",
        )
        second_membership = OrganizationMembership.objects.create(
            user=second_user,
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
            user_type="internal",
            organization="Legacy Secretariat",
        )
        next_org_membership = OrganizationMembership.objects.create(
            user=next_user,
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
            user_type="internal",
        )

        with self.assertRaises(DRFValidationError) as exc:
            OrganizationMembership.objects.create(
                user=second_user,
                membership_role="officer",
                is_active=True,
                is_default=False,
            )

        self.assertEqual(exc.exception.detail.get("code"), "ORG_SEAT_QUOTA_EXCEEDED")
        self.assertFalse(
            OrganizationMembership.objects.filter(
                user=second_user,
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
            user_type="internal",
        )
        inactive_membership = OrganizationMembership.objects.create(
            user=inactive_user,
            membership_role="officer",
            is_active=False,
            is_default=False,
        )

        inactive_membership.is_active = True
        with self.assertRaises(DRFValidationError) as exc:
            inactive_membership.save(update_fields=["is_active", "updated_at"])

        self.assertEqual(exc.exception.detail.get("code"), "ORG_SEAT_QUOTA_EXCEEDED")


class GovernanceApiTests(APITestCase):
    def setUp(self):
        self.org_a = Organization.objects.create(
            code="gov-api-org-a",
            name="Gov API Org A",
            organization_type="agency",
        )
        self.org_b = Organization.objects.create(
            code="gov-api-org-b",
            name="Gov API Org B",
            organization_type="ministry",
        )

        self.org_admin = User.objects.create_user(
            email="gov.api.admin@example.com",
            password="TestPass123!",
            first_name="Gov",
            last_name="OrgAdmin",
            user_type="internal",
        )
        self.platform_admin = User.objects.create_user(
            email="gov.api.platform@example.com",
            password="TestPass123!",
            first_name="Gov",
            last_name="PlatformAdmin",
            user_type="admin",
            is_staff=True,
            is_superuser=True,
        )
        self.org_b_operator = User.objects.create_user(
            email="gov.api.operator.b@example.com",
            password="TestPass123!",
            first_name="Gov",
            last_name="OperatorB",
            user_type="internal",
        )
        self.candidate_user = User.objects.create_user(
            email="gov.api.member@example.com",
            password="TestPass123!",
            first_name="Gov",
            last_name="Member",
            user_type="internal",
        )

        self.membership_a_admin = OrganizationMembership.objects.create(
            user=self.org_admin,
            membership_role="registry_admin",
            is_active=True,
            is_default=True,
        )
        self.membership_b_operator = OrganizationMembership.objects.create(
            user=self.org_b_operator,
            membership_role="registry_admin",
            is_active=True,
            is_default=True,
        )
        self.membership_a_candidate = OrganizationMembership.objects.create(
            user=self.candidate_user,
            membership_role="member",
            is_active=True,
            is_default=True,
        )

        self.committee_a = Committee.objects.create(
            code="api-org-a-main",
            name="API Org A Main Committee",
            committee_type="vetting",
            created_by=self.org_admin,
        )
        self.committee_b = Committee.objects.create(
            code="api-org-b-main",
            name="API Org B Main Committee",
            committee_type="approval",
            created_by=self.org_b_operator,
        )

        self.committee_membership_b = CommitteeMembership.objects.create(
            committee=self.committee_b,
            user=self.org_b_operator,
            organization_membership=self.membership_b_operator,
            committee_role="member",
            can_vote=True,
        )

    def _results(self, response):
        payload = response.json()
        if isinstance(payload, dict) and "results" in payload:
            return payload["results"]
        return payload

    def test_org_less_internal_user_can_bootstrap_organization(self):
        org_less_user = User.objects.create_user(
            email="gov.api.bootstrap@example.com",
            password="TestPass123!",
            first_name="Bootstrap",
            last_name="Operator",
            user_type="internal",
        )
        self.client.force_authenticate(org_less_user)

        response = self.client.post(
            "/api/governance/organization/bootstrap/",
            {
                "name": "Bootstrap Governance Office",
                "organization_type": "agency",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["membership"]["membership_role"], "registry_admin")
        self.assertTrue(payload["membership"]["is_default"])

        membership = OrganizationMembership.objects.get(
            user=org_less_user,
            organization_id=payload["organization"]["id"],
        )
        self.assertEqual(membership.membership_role, "registry_admin")
        self.assertTrue(membership.is_default)
        org_less_user.refresh_from_db()
        self.assertEqual(org_less_user.organization, payload["organization"]["name"])

    def test_org_bootstrap_rejected_when_active_membership_already_exists_for_non_platform_user(self):
        self.client.force_authenticate(self.org_admin)
        response = self.client.post(
            "/api/governance/organization/bootstrap/",
            {
                "name": "Should Not Provision",
                "organization_type": "agency",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json().get("code"), "ORGANIZATION_ALREADY_PROVISIONED")

    def test_applicant_cannot_bootstrap_organization(self):
        applicant = User.objects.create_user(
            email="gov.api.bootstrap.applicant@example.com",
            password="TestPass123!",
            first_name="Applicant",
            last_name="Denied",
            user_type="applicant",
        )
        self.client.force_authenticate(applicant)
        response = self.client.post(
            "/api/governance/organization/bootstrap/",
            {
                "name": "Applicant Should Not Bootstrap",
                "organization_type": "agency",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_org_summary_access_and_platform_override(self):
        self.client.force_authenticate(self.org_admin)
        response = self.client.get("/api/governance/organization/summary/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["organization"]["id"], str(self.org_a.id))

        self.client.force_authenticate(self.platform_admin)
        denied = self.client.get("/api/governance/organization/summary/")
        self.assertEqual(denied.status_code, 403)

    def test_committee_member_cannot_access_governance_management_endpoints(self):
        committee_group, _ = Group.objects.get_or_create(name="committee_member")
        self.candidate_user.groups.add(committee_group)
        self.client.force_authenticate(self.candidate_user)

        summary_response = self.client.get("/api/governance/organization/summary/")
        self.assertEqual(summary_response.status_code, 403)

        member_list_response = self.client.get("/api/governance/organization/members/")
        self.assertEqual(member_list_response.status_code, 403)

        committee_create_response = self.client.post(
            "/api/governance/organization/committees/",
            {
                "code": "candidate-denied-committee",
                "name": "Candidate Denied Committee",
                "committee_type": "vetting",
            },
            format="json",
        )
        self.assertEqual(committee_create_response.status_code, 403)

    def test_plain_internal_without_governance_role_cannot_access_governance_management_endpoints(self):
        self.client.force_authenticate(self.candidate_user)

        summary_response = self.client.get("/api/governance/organization/summary/")
        self.assertEqual(summary_response.status_code, 403)

        member_list_response = self.client.get("/api/governance/organization/members/")
        self.assertEqual(member_list_response.status_code, 403)

    def test_vetting_officer_cannot_access_governance_management_endpoints(self):
        vetting_officer = User.objects.create_user(
            email="gov.api.vetting.officer@example.com",
            password="TestPass123!",
            first_name="Gov",
            last_name="VettingOfficer",
            user_type="internal",
        )
        vetting_group, _ = Group.objects.get_or_create(name="vetting_officer")
        vetting_officer.groups.add(vetting_group)
        OrganizationMembership.objects.create(
            user=vetting_officer,
            membership_role="vetting_officer",
            is_active=True,
            is_default=True,
        )

        self.client.force_authenticate(vetting_officer)
        summary_response = self.client.get("/api/governance/organization/summary/")
        self.assertEqual(summary_response.status_code, 403)

        membership_update_response = self.client.patch(
            f"/api/governance/organization/members/{self.membership_a_candidate.id}/",
            {"title": "Should Not Update"},
            format="json",
        )
        self.assertEqual(membership_update_response.status_code, 403)

    def test_member_list_detail_update_scope(self):
        self.client.force_authenticate(self.org_admin)

        list_response = self.client.get("/api/governance/organization/members/")
        self.assertEqual(list_response.status_code, 200)
        ids = {item["id"] for item in self._results(list_response)}
        self.assertIn(str(self.membership_a_admin.id), ids)
        self.assertIn(str(self.membership_a_candidate.id), ids)
        self.assertNotIn(str(self.membership_b_operator.id), ids)

        denied_detail = self.client.get(
            f"/api/governance/organization/members/{self.membership_b_operator.id}/"
        )
        self.assertEqual(denied_detail.status_code, 404)

        update_response = self.client.patch(
            f"/api/governance/organization/members/{self.membership_a_candidate.id}/",
            {
                "title": "Senior Analyst",
                "membership_role": "committee_member",
            },
            format="json",
        )
        self.assertEqual(update_response.status_code, 200)
        self.membership_a_candidate.refresh_from_db()
        self.assertEqual(self.membership_a_candidate.title, "Senior Analyst")
        self.assertEqual(self.membership_a_candidate.membership_role, "committee_member")

        unsafe_role = self.client.patch(
            f"/api/governance/organization/members/{self.membership_a_candidate.id}/",
            {"membership_role": "member<script>"},
            format="json",
        )
        self.assertEqual(unsafe_role.status_code, 400)

    @override_settings(
        BILLING_ORG_MEMBER_QUOTA_ENFORCEMENT_ENABLED=True,
        BILLING_PLAN_STARTER_ORG_SEATS=3,
    )
    def test_member_reactivation_allowed_within_org_seat_limit(self):
        BillingSubscription.objects.create(
            provider="sandbox",
            status="complete",
            payment_status="paid",
            plan_id="starter",
            plan_name="Starter",
            billing_cycle="monthly",
            payment_method="card",
            amount_usd="149.00",
            reference="GOV-API-REACTIVATE-ALLOW",
        )
        inactive_user = User.objects.create_user(
            email="gov.api.inactive.allow@example.com",
            password="TestPass123!",
            first_name="Gov",
            last_name="InactiveAllow",
            user_type="internal",
        )
        inactive_membership = OrganizationMembership.objects.create(
            user=inactive_user,
            membership_role="member",
            is_active=False,
            is_default=False,
        )

        self.client.force_authenticate(self.org_admin)
        response = self.client.patch(
            f"/api/governance/organization/members/{inactive_membership.id}/",
            {"is_active": True},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        inactive_membership.refresh_from_db()
        self.assertTrue(inactive_membership.is_active)

    @override_settings(
        BILLING_ORG_MEMBER_QUOTA_ENFORCEMENT_ENABLED=True,
        BILLING_PLAN_STARTER_ORG_SEATS=2,
    )
    def test_member_reactivation_blocked_when_org_seat_limit_exceeded(self):
        BillingSubscription.objects.create(
            provider="sandbox",
            status="complete",
            payment_status="paid",
            plan_id="starter",
            plan_name="Starter",
            billing_cycle="monthly",
            payment_method="card",
            amount_usd="149.00",
            reference="GOV-API-REACTIVATE-DENY",
        )
        inactive_user = User.objects.create_user(
            email="gov.api.inactive.deny@example.com",
            password="TestPass123!",
            first_name="Gov",
            last_name="InactiveDeny",
            user_type="internal",
        )
        inactive_membership = OrganizationMembership.objects.create(
            user=inactive_user,
            membership_role="member",
            is_active=False,
            is_default=False,
        )

        self.client.force_authenticate(self.org_admin)
        response = self.client.patch(
            f"/api/governance/organization/members/{inactive_membership.id}/",
            {"is_active": True},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json().get("code"), "ORG_SEAT_QUOTA_EXCEEDED")
        inactive_membership.refresh_from_db()
        self.assertFalse(inactive_membership.is_active)

    @override_settings(
        BILLING_ORG_MEMBER_QUOTA_ENFORCEMENT_ENABLED=True,
        BILLING_PLAN_STARTER_ORG_SEATS=2,
    )
    def test_member_reactivation_is_idempotent_for_already_active_membership(self):
        BillingSubscription.objects.create(
            provider="sandbox",
            status="complete",
            payment_status="paid",
            plan_id="starter",
            plan_name="Starter",
            billing_cycle="monthly",
            payment_method="card",
            amount_usd="149.00",
            reference="GOV-API-REACTIVATE-IDEMPOTENT",
        )

        self.client.force_authenticate(self.org_admin)
        response = self.client.patch(
            f"/api/governance/organization/members/{self.membership_a_candidate.id}/",
            {"is_active": True},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.membership_a_candidate.refresh_from_db()
        self.assertTrue(self.membership_a_candidate.is_active)

    def test_member_reactivation_patch_is_denied_across_organizations(self):
        inactive_user = User.objects.create_user(
            email="gov.api.inactive.cross@example.com",
            password="TestPass123!",
            first_name="Gov",
            last_name="InactiveCross",
            user_type="internal",
        )
        cross_org_inactive_membership = OrganizationMembership.objects.create(
            user=inactive_user,
            membership_role="member",
            is_active=False,
            is_default=False,
        )

        self.client.force_authenticate(self.org_admin)
        response = self.client.patch(
            f"/api/governance/organization/members/{cross_org_inactive_membership.id}/",
            {"is_active": True},
            format="json",
        )
        self.assertEqual(response.status_code, 404)
        cross_org_inactive_membership.refresh_from_db()
        self.assertFalse(cross_org_inactive_membership.is_active)

    def test_committee_crud_scope_and_soft_delete(self):
        self.client.force_authenticate(self.org_admin)

        list_response = self.client.get("/api/governance/organization/committees/")
        self.assertEqual(list_response.status_code, 200)
        ids = {item["id"] for item in self._results(list_response)}
        self.assertIn(str(self.committee_a.id), ids)
        self.assertNotIn(str(self.committee_b.id), ids)

        create_response = self.client.post(
            "/api/governance/organization/committees/",
            {
                "code": "api-org-a-review",
                "name": "API Org A Review Committee",
                "committee_type": "approval",
                "description": "Review committee",
            },
            format="json",
        )
        self.assertEqual(create_response.status_code, 201)
        created_id = create_response.json()["id"]
        created = Committee.objects.get(id=created_id)
        self.assertTrue(created.is_active)

        denied_detail = self.client.get(f"/api/governance/organization/committees/{self.committee_b.id}/")
        self.assertEqual(denied_detail.status_code, 404)

        patch_response = self.client.patch(
            f"/api/governance/organization/committees/{created_id}/",
            {"name": "Renamed API Org A Review Committee"},
            format="json",
        )
        self.assertEqual(patch_response.status_code, 200)

        delete_response = self.client.delete(f"/api/governance/organization/committees/{created_id}/")
        self.assertEqual(delete_response.status_code, 204)
        created.refresh_from_db()
        self.assertFalse(created.is_active)

    def test_committee_membership_crud_scope_and_soft_delete(self):
        self.client.force_authenticate(self.org_admin)
        list_url = "/api/governance/organization/committee-memberships/"

        create_response = self.client.post(
            list_url,
            {
                "committee": str(self.committee_a.id),
                "user": str(self.candidate_user.id),
                "committee_role": "member",
                "can_vote": True,
            },
            format="json",
        )
        self.assertEqual(create_response.status_code, 201)
        membership_id = create_response.json()["id"]

        list_response = self.client.get(list_url)
        self.assertEqual(list_response.status_code, 200)
        ids = {item["id"] for item in self._results(list_response)}
        self.assertIn(str(membership_id), ids)
        self.assertNotIn(str(self.committee_membership_b.id), ids)

        denied_detail = self.client.get(
            f"/api/governance/organization/committee-memberships/{self.committee_membership_b.id}/"
        )
        self.assertEqual(denied_detail.status_code, 404)

        chair_create_denied = self.client.post(
            list_url,
            {
                "committee": str(self.committee_a.id),
                "user": str(self.org_admin.id),
                "committee_role": "chair",
                "can_vote": True,
            },
            format="json",
        )
        self.assertEqual(chair_create_denied.status_code, 400)

        update_response = self.client.patch(
            f"/api/governance/organization/committee-memberships/{membership_id}/",
            {
                "committee_role": "observer",
                "can_vote": False,
            },
            format="json",
        )
        self.assertEqual(update_response.status_code, 200)

        chair_patch_denied = self.client.patch(
            f"/api/governance/organization/committee-memberships/{membership_id}/",
            {"committee_role": "chair"},
            format="json",
        )
        self.assertEqual(chair_patch_denied.status_code, 400)

        delete_response = self.client.delete(
            f"/api/governance/organization/committee-memberships/{membership_id}/"
        )
        self.assertEqual(delete_response.status_code, 204)
        membership = CommitteeMembership.objects.get(id=membership_id)
        self.assertFalse(membership.is_active)
        self.assertIsNotNone(membership.left_at)

    def test_chair_reassignment_invariant(self):
        self.client.force_authenticate(self.org_admin)

        user_one = User.objects.create_user(
            email="gov.api.chair.one@example.com",
            password="TestPass123!",
            first_name="Chair",
            last_name="One",
            user_type="internal",
        )
        user_two = User.objects.create_user(
            email="gov.api.chair.two@example.com",
            password="TestPass123!",
            first_name="Chair",
            last_name="Two",
            user_type="internal",
        )
        org_membership_one = OrganizationMembership.objects.create(
            user=user_one,
            membership_role="member",
            is_active=True,
            is_default=True,
        )
        org_membership_two = OrganizationMembership.objects.create(
            user=user_two,
            membership_role="member",
            is_active=True,
            is_default=True,
        )
        committee_member_one = CommitteeMembership.objects.create(
            committee=self.committee_a,
            user=user_one,
            organization_membership=org_membership_one,
            committee_role="member",
            can_vote=True,
        )
        committee_member_two = CommitteeMembership.objects.create(
            committee=self.committee_a,
            user=user_two,
            organization_membership=org_membership_two,
            committee_role="member",
            can_vote=True,
        )

        endpoint = f"/api/governance/organization/committees/{self.committee_a.id}/reassign-chair/"
        first_reassignment = self.client.post(
            endpoint,
            {"target_committee_membership_id": str(committee_member_one.id)},
            format="json",
        )
        self.assertEqual(first_reassignment.status_code, 200)
        self.assertEqual(
            first_reassignment.json()["new_chair"]["user_id"],
            str(user_one.id),
        )

        second_reassignment = self.client.post(
            endpoint,
            {"target_committee_membership_id": str(committee_member_two.id)},
            format="json",
        )
        self.assertEqual(second_reassignment.status_code, 200)
        self.assertEqual(
            second_reassignment.json()["new_chair"]["user_id"],
            str(user_two.id),
        )

        active_chairs = CommitteeMembership.objects.filter(
            committee=self.committee_a,
            committee_role="chair",
            is_active=True,
        )
        self.assertEqual(active_chairs.count(), 1)
        self.assertEqual(active_chairs.first().user_id, user_two.id)
        committee_member_one.refresh_from_db()
        self.assertEqual(committee_member_one.committee_role, "member")

    def test_cross_org_denial_for_non_admin(self):
        self.client.force_authenticate(self.org_admin)
        response = self.client.post(
            "/api/governance/organization/committee-memberships/",
            {
                "committee": str(self.committee_b.id),
                "user": str(self.candidate_user.id),
                "committee_role": "member",
                "can_vote": True,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_platform_admin_is_blocked_from_org_governance_workflows(self):
        self.client.force_authenticate(self.platform_admin)

        global_members = self.client.get("/api/governance/organization/members/")
        self.assertEqual(global_members.status_code, 403)

        patch_response = self.client.patch(
            f"/api/governance/organization/members/{self.membership_b_operator.id}/",
            {"title": "Platform Updated"},
            format="json",
        )
        self.assertEqual(patch_response.status_code, 403)

        member_options = self.client.get(
            f"/api/governance/organization/lookups/member-options/?organization_id={self.org_a.id}"
        )
        self.assertEqual(member_options.status_code, 403)

        choices = self.client.get("/api/governance/organization/lookups/choices/")
        self.assertEqual(choices.status_code, 200)
        payload = choices.json()
        self.assertIn("committee_roles", payload)
        self.assertIn("committee_types", payload)
        self.assertIn("organization_types", payload)

    def test_platform_admin_can_list_organization_subscription_oversight(self):
        BillingSubscription.objects.create(
            provider="sandbox",
            status="complete",
            payment_status="paid",
            plan_id="growth",
            plan_name="Growth",
            billing_cycle="monthly",
            payment_method="card",
            amount_usd="399.00",
            reference="PLATFORM-GOV-ORG-ACTIVE",
        )
        BillingSubscription.objects.create(
            provider="paystack",
            status="failed",
            payment_status="unpaid",
            plan_id="starter",
            plan_name="Starter",
            billing_cycle="monthly",
            payment_method="mobile_money",
            amount_usd="149.00",
            reference="PLATFORM-GOV-ORG-FAILED",
        )

        self.client.force_authenticate(self.platform_admin)
        response = self.client.get("/api/governance/platform/organizations/")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertGreaterEqual(payload["count"], 2)
        org_rows = {row["code"]: row for row in payload["results"]}
        self.assertEqual(org_rows["gov-api-org-a"]["subscription"]["source"], "active")
        self.assertEqual(org_rows["gov-api-org-a"]["subscription"]["plan_name"], "Growth")
        self.assertEqual(org_rows["gov-api-org-b"]["subscription"]["status"], "failed")
        self.assertEqual(org_rows["gov-api-org-b"]["subscription"]["payment_status"], "unpaid")

    def test_platform_oversight_prefers_active_subscription_over_newer_failed_attempt(self):
        BillingSubscription.objects.create(
            provider="sandbox",
            status="complete",
            payment_status="paid",
            plan_id="growth",
            plan_name="Growth",
            billing_cycle="monthly",
            payment_method="card",
            amount_usd="399.00",
            reference="PLATFORM-GOV-ORG-ACTIVE-CURRENT",
        )
        BillingSubscription.objects.create(
            provider="paystack",
            status="failed",
            payment_status="unpaid",
            plan_id="starter",
            plan_name="Starter",
            billing_cycle="monthly",
            payment_method="mobile_money",
            amount_usd="149.00",
            reference="PLATFORM-GOV-ORG-ACTIVE-FAILED-LATEST",
        )

        self.client.force_authenticate(self.platform_admin)
        response = self.client.get("/api/governance/platform/organizations/")

        self.assertEqual(response.status_code, 200)
        org_row = next(
            row for row in response.json()["results"] if row["id"] == str(self.org_a.id)
        )
        self.assertEqual(org_row["subscription"]["source"], "active")
        self.assertEqual(org_row["subscription"]["plan_name"], "Growth")
        self.assertEqual(org_row["subscription"]["status"], "complete")

    def test_platform_admin_can_toggle_organization_active_status(self):
        self.client.force_authenticate(self.platform_admin)
        response = self.client.patch(
            f"/api/governance/platform/organizations/{self.org_b.id}/",
            {"is_active": False},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.org_b.refresh_from_db()
        self.assertFalse(self.org_b.is_active)
        self.assertEqual(response.json()["is_active"], False)

    def test_non_platform_actor_cannot_access_platform_organization_oversight(self):
        self.client.force_authenticate(self.org_admin)
        list_response = self.client.get("/api/governance/platform/organizations/")
        patch_response = self.client.patch(
            f"/api/governance/platform/organizations/{self.org_a.id}/",
            {"is_active": False},
            format="json",
        )

        self.assertEqual(list_response.status_code, 403)
        self.assertEqual(patch_response.status_code, 403)

