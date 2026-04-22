from rest_framework.test import APITestCase
from django.test import override_settings
from django.contrib.auth.models import Group

from apps.users.models import User
from apps.billing.models import BillingSubscription
from apps.candidates.models import Candidate, CandidateEnrollment
from apps.campaigns.models import CampaignRubricVersion, VettingCampaign
from apps.tenants.models import Organization
from apps.governance.models import OrganizationMembership


class CampaignAuthorizationTests(APITestCase):
    def setUp(self):
        self.internal_one = User.objects.create_user(
            email="internal_campaign_one@example.com",
            password="Pass1234!",
            first_name="Internal",
            last_name="One",
            user_type="internal",
        )
        self.internal_two = User.objects.create_user(
            email="internal_campaign_two@example.com",
            password="Pass1234!",
            first_name="Internal",
            last_name="Two",
            user_type="internal",
        )
        self.admin = User.objects.create_user(
            email="admin_campaign@example.com",
            password="Pass1234!",
            first_name="Admin",
            last_name="User",
            user_type="admin",
            is_staff=True,
        )
        self.applicant = User.objects.create_user(
            email="applicant_campaign@example.com",
            password="Pass1234!",
            first_name="Applicant",
            last_name="User",
            user_type="applicant",
        )
        registry_admin_group, _ = Group.objects.get_or_create(name="registry_admin")
        self.internal_one.groups.add(registry_admin_group)
        self.internal_two.groups.add(registry_admin_group)
        self.campaign_one = VettingCampaign.objects.create(name="Campaign One", initiated_by=self.internal_one)
        self.campaign_two = VettingCampaign.objects.create(name="Campaign Two", initiated_by=self.internal_two)
        self.version_one = CampaignRubricVersion.objects.create(
            campaign=self.campaign_one,
            version=1,
            name="Default rubric version",
            description="Baseline",
            weight_document=60,
            weight_interview=40,
            passing_score=70,
            auto_approve_threshold=90,
            auto_reject_threshold=40,
            rubric_payload={"source": "unit-test"},
            is_active=True,
            created_by=self.internal_one,
        )
        self.version_two = CampaignRubricVersion.objects.create(
            campaign=self.campaign_one,
            version=2,
            name="Secondary rubric version",
            description="Secondary",
            weight_document=55,
            weight_interview=45,
            passing_score=72,
            auto_approve_threshold=92,
            auto_reject_threshold=42,
            rubric_payload={"source": "unit-test-two"},
            is_active=False,
            created_by=self.internal_one,
        )

    def _items(self, payload):
        if isinstance(payload, list):
            return payload
        return payload.get("results", [])

    def _seed_subscription(self, user, *, plan_id="starter", plan_name="Starter"):
        BillingSubscription.objects.create(
            provider="sandbox",
            status="complete",
            payment_status="paid",
            plan_id=plan_id,
            plan_name=plan_name,
            billing_cycle="monthly",
            payment_method="card",
            amount_usd="149.00",
            reference=f"OVS-{plan_id.upper()}-{user.id.hex[:6]}",
            registration_consumed_by_email=user.email,
        )

    def test_internal_sees_only_own_campaigns(self):
        self.client.force_authenticate(self.internal_one)
        response = self.client.get("/api/campaigns/")
        self.assertEqual(response.status_code, 200)
        ids = {item["id"] for item in self._items(response.json())}
        self.assertIn(str(self.campaign_one.id), ids)
        self.assertNotIn(str(self.campaign_two.id), ids)

    def test_applicant_cannot_list_campaigns(self):
        self.client.force_authenticate(self.applicant)
        response = self.client.get("/api/campaigns/")
        self.assertEqual(response.status_code, 403)

    def test_applicant_cannot_create_campaign(self):
        self.client.force_authenticate(self.applicant)
        response = self.client.post("/api/campaigns/", {"name": "Applicant Campaign"}, format="json")
        self.assertEqual(response.status_code, 403)

    def test_internal_can_transition_campaign_status_draft_to_active(self):
        self.client.force_authenticate(self.internal_one)
        response = self.client.patch(
            f"/api/campaigns/{self.campaign_one.id}/",
            {"status": "active"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.campaign_one.refresh_from_db()
        self.assertEqual(self.campaign_one.status, "active")

    def test_internal_cannot_transition_campaign_status_draft_to_closed(self):
        self.client.force_authenticate(self.internal_one)
        response = self.client.patch(
            f"/api/campaigns/{self.campaign_one.id}/",
            {"status": "closed"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertIn("status", payload)

    def test_internal_can_reopen_closed_campaign_to_active(self):
        self.campaign_one.status = "closed"
        self.campaign_one.save(update_fields=["status"])

        self.client.force_authenticate(self.internal_one)
        response = self.client.patch(
            f"/api/campaigns/{self.campaign_one.id}/",
            {"status": "active"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.campaign_one.refresh_from_db()
        self.assertEqual(self.campaign_one.status, "active")

    def test_internal_can_reopen_archived_campaign(self):
        self.campaign_one.status = "archived"
        self.campaign_one.save(update_fields=["status"])

        self.client.force_authenticate(self.internal_one)
        response = self.client.patch(
            f"/api/campaigns/{self.campaign_one.id}/",
            {"status": "active"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.campaign_one.refresh_from_db()
        self.assertEqual(self.campaign_one.status, "active")

    def test_plain_internal_without_operational_role_cannot_list_campaigns(self):
        plain_internal = User.objects.create_user(
            email="plain_internal_campaign@example.com",
            password="Pass1234!",
            first_name="Plain",
            last_name="Reviewer",
            user_type="internal",
        )
        self.client.force_authenticate(plain_internal)
        response = self.client.get("/api/campaigns/")
        self.assertEqual(response.status_code, 403)

    def test_internal_cannot_access_other_campaign_detail(self):
        self.client.force_authenticate(self.internal_one)
        response = self.client.get(f"/api/campaigns/{self.campaign_two.id}/")
        self.assertEqual(response.status_code, 404)

    def test_admin_sees_all_campaigns(self):
        self.client.force_authenticate(self.admin)
        response = self.client.get("/api/campaigns/")
        self.assertEqual(response.status_code, 200)
        ids = {item["id"] for item in self._items(response.json())}
        self.assertIn(str(self.campaign_one.id), ids)
        self.assertIn(str(self.campaign_two.id), ids)

    def test_internal_can_define_required_document_types(self):
        organization = Organization.objects.create(
            code="campaign-required-docs-org",
            name="Campaign Required Docs Org",
            organization_type="agency",
            is_active=True,
        )
        OrganizationMembership.objects.create(
            user=self.internal_one,
            membership_role="registry_admin",
            is_active=True,
            is_default=True,
        )
        self.client.force_authenticate(self.internal_one)
        payload = {
            "name": "Required Docs Campaign",
            "status": "draft",
            "required_document_types": ["id_card", "passport", "id_card"],
        }

        response = self.client.post(
            "/api/campaigns/",
            payload,
            format="json",
            HTTP_X_ACTIVE_ORGANIZATION_ID=str(organization.id),
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["required_document_types"], ["id_card", "passport"])

        campaign = VettingCampaign.objects.get(id=data["id"])
        settings_json = campaign.settings_json if isinstance(campaign.settings_json, dict) else {}
        self.assertEqual(settings_json.get("required_document_types"), ["id_card", "passport"])

    def test_internal_can_list_own_campaign_rubric_versions(self):
        self.client.force_authenticate(self.internal_one)
        response = self.client.get(f"/api/campaigns/{self.campaign_one.id}/rubrics/versions/")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(isinstance(payload, list))
        ids = {item["id"] for item in payload}
        self.assertEqual(ids, {str(self.version_one.id), str(self.version_two.id)})
        self.assertEqual(payload[0]["version"], 2)

    def test_internal_cannot_list_other_campaign_rubric_versions(self):
        self.client.force_authenticate(self.internal_one)
        response = self.client.get(f"/api/campaigns/{self.campaign_two.id}/rubrics/versions/")
        self.assertEqual(response.status_code, 404)

    def test_internal_can_add_campaign_rubric_version(self):
        self.client.force_authenticate(self.internal_one)
        payload = {
            "name": "New version",
            "description": "Updated thresholds",
            "weight_document": 55,
            "weight_interview": 45,
            "passing_score": 72,
            "auto_approve_threshold": 92,
            "auto_reject_threshold": 42,
            "rubric_payload": {"source_rubric_id": "demo-rubric-id"},
            "is_active": True,
        }

        response = self.client.post(f"/api/campaigns/{self.campaign_one.id}/rubrics/versions/", payload, format="json")
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["version"], 3)
        self.assertEqual(data["name"], "New version")
        self.assertEqual(data["campaign"], str(self.campaign_one.id))

    def test_internal_can_activate_campaign_rubric_version(self):
        self.client.force_authenticate(self.internal_one)
        payload = {"version_id": str(self.version_two.id)}
        response = self.client.post(
            f"/api/campaigns/{self.campaign_one.id}/rubrics/versions/activate/",
            payload,
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.version_one.refresh_from_db()
        self.version_two.refresh_from_db()
        self.assertFalse(self.version_one.is_active)
        self.assertTrue(self.version_two.is_active)

    def test_internal_cannot_activate_other_campaign_rubric_version(self):
        self.client.force_authenticate(self.internal_one)
        outsider_version = CampaignRubricVersion.objects.create(
            campaign=self.campaign_two,
            version=1,
            name="Other campaign version",
            description="Other",
            weight_document=50,
            weight_interview=50,
            passing_score=70,
            auto_approve_threshold=90,
            auto_reject_threshold=40,
            rubric_payload={"source": "other"},
            is_active=True,
            created_by=self.internal_two,
        )
        payload = {"version_id": str(outsider_version.id)}
        response = self.client.post(
            f"/api/campaigns/{self.campaign_one.id}/rubrics/versions/activate/",
            payload,
            format="json",
        )
        self.assertEqual(response.status_code, 404)

    @override_settings(
        BILLING_QUOTA_ENFORCEMENT_ENABLED=True,
        BILLING_PLAN_STARTER_CANDIDATES_PER_MONTH=2,
    )
    def test_internal_import_candidates_respects_plan_quota(self):
        self._seed_subscription(self.internal_one, plan_id="starter", plan_name="Starter")
        self.client.force_authenticate(self.internal_one)

        payload = {
            "send_invites": False,
            "candidates": [
                {
                    "email": "quota_a@example.com",
                    "first_name": "Quota",
                    "last_name": "A",
                    "preferred_channel": "email",
                },
                {
                    "email": "quota_b@example.com",
                    "first_name": "Quota",
                    "last_name": "B",
                    "preferred_channel": "email",
                },
                {
                    "email": "quota_c@example.com",
                    "first_name": "Quota",
                    "last_name": "C",
                    "preferred_channel": "email",
                },
            ],
        }

        response = self.client.post(
            f"/api/campaigns/{self.campaign_one.id}/candidates/import/",
            payload,
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        body = response.json()
        self.assertEqual(body.get("code"), "quota_exceeded")
        self.assertIn("quota", body)
        self.assertIn("detail", body)
        self.assertIn("Monthly limit 2", body.get("detail", ""))
        self.assertEqual(int(body["quota"].get("projected_total")), 3)
        self.assertEqual(int(body["quota"].get("requested_additional")), 3)
        self.assertEqual(int(body["quota"].get("limit")), 2)
        self.assertEqual(int(body["quota"].get("used")), 0)
        self.assertIn("period_start", body["quota"])
        self.assertIn("period_end", body["quota"])
        self.assertEqual(Candidate.objects.count(), 0)
        self.assertEqual(CandidateEnrollment.objects.count(), 0)

    @override_settings(
        BILLING_QUOTA_ENFORCEMENT_ENABLED=True,
    )
    def test_internal_import_candidates_requires_active_subscription(self):
        self.client.force_authenticate(self.internal_one)

        payload = {
            "send_invites": False,
            "candidates": [
                {
                    "email": "need_sub@example.com",
                    "first_name": "Need",
                    "last_name": "Subscription",
                    "preferred_channel": "email",
                },
            ],
        }

        response = self.client.post(
            f"/api/campaigns/{self.campaign_one.id}/candidates/import/",
            payload,
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        body = response.json()
        self.assertEqual(body.get("code"), "subscription_required")
        self.assertIn("quota", body)
        self.assertIn("detail", body)
        self.assertIn("No active paid subscription found", body.get("detail", ""))
        self.assertEqual(int(body["quota"].get("limit")), 0)
        self.assertEqual(int(body["quota"].get("used")), 0)
        self.assertEqual(int(body["quota"].get("remaining")), 0)
        self.assertIn("period_start", body["quota"])
        self.assertIn("period_end", body["quota"])
        self.assertTrue(str(body["quota"].get("period_start")))
        self.assertTrue(str(body["quota"].get("period_end")))
        self.assertEqual(Candidate.objects.count(), 0)
        self.assertEqual(CandidateEnrollment.objects.count(), 0)


class CampaignOrganizationScopeTests(APITestCase):
    def setUp(self):
        self.org_a = Organization.objects.create(code="camp-org-a", name="Campaign Org A")
        self.org_b = Organization.objects.create(code="camp-org-b", name="Campaign Org B")

        self.internal_a = User.objects.create_user(
            email="campaign_scope_a@example.com",
            password="Pass1234!",
            first_name="Scope",
            last_name="A",
            user_type="internal",
        )
        self.internal_b = User.objects.create_user(
            email="campaign_scope_b@example.com",
            password="Pass1234!",
            first_name="Scope",
            last_name="B",
            user_type="internal",
        )
        vetting_officer_group, _ = Group.objects.get_or_create(name="vetting_officer")
        self.internal_a.groups.add(vetting_officer_group)
        self.internal_b.groups.add(vetting_officer_group)
        OrganizationMembership.objects.create(
            user=self.internal_a,
            is_active=True,
            is_default=True,
        )
        OrganizationMembership.objects.create(
            user=self.internal_b,
            is_active=True,
            is_default=True,
        )

        self.same_org_foreign_owner_campaign = VettingCampaign.objects.create(
            name="Org A Campaign (Owned by B)",
            initiated_by=self.internal_b,
        )
        self.other_org_campaign = VettingCampaign.objects.create(
            name="Org B Campaign",
            initiated_by=self.internal_b,
        )

    def _items(self, payload):
        if isinstance(payload, list):
            return payload
        return payload.get("results", [])

    def test_internal_with_org_membership_can_view_same_org_campaigns(self):
        self.client.force_authenticate(self.internal_a)
        response = self.client.get("/api/campaigns/")
        self.assertEqual(response.status_code, 200)
        ids = {item["id"] for item in self._items(response.json())}
        self.assertIn(str(self.same_org_foreign_owner_campaign.id), ids)
        self.assertNotIn(str(self.other_org_campaign.id), ids)

    def test_internal_cannot_create_campaign_for_other_org(self):
        self.client.force_authenticate(self.internal_a)
        response = self.client.post(
            "/api/campaigns/",
            {
                "name": "Cross Org Campaign",
                "organization": str(self.org_b.id),
            },
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_membershipless_internal_cannot_create_campaign_without_org_context(self):
        membershipless_internal = User.objects.create_user(
            email="campaign_scope_create_denied@example.com",
            password="Pass1234!",
            first_name="Campaign",
            last_name="CreateDenied",
            user_type="internal",
        )
        self.client.force_authenticate(membershipless_internal)
        response = self.client.post(
            "/api/campaigns/",
            {"name": "Membershipless Create Campaign"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_non_registry_member_cannot_create_campaign_within_active_org(self):
        self.client.force_authenticate(self.internal_a)
        response = self.client.post(
            "/api/campaigns/",
            {"name": "Insufficient Role Campaign"},
            format="json",
            HTTP_X_ACTIVE_ORGANIZATION_ID=str(self.org_a.id),
        )
        self.assertEqual(response.status_code, 403)

    def test_non_registry_member_cannot_update_same_org_campaign(self):
        self.client.force_authenticate(self.internal_a)
        response = self.client.patch(
            f"/api/campaigns/{self.same_org_foreign_owner_campaign.id}/",
            {"description": "Updated by non-registry actor"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_non_registry_member_cannot_delete_same_org_campaign(self):
        self.client.force_authenticate(self.internal_a)
        response = self.client.delete(f"/api/campaigns/{self.same_org_foreign_owner_campaign.id}/")
        self.assertEqual(response.status_code, 403)


class CampaignAliasContractTests(APITestCase):
    def setUp(self):
        self.internal_user = User.objects.create_user(
            email="campaign_alias_internal@example.com",
            password="Pass1234!",
            first_name="Campaign",
            last_name="Alias",
            user_type="internal",
        )
        registry_admin_group, _ = Group.objects.get_or_create(name="registry_admin")
        self.internal_user.groups.add(registry_admin_group)
        self.campaign = VettingCampaign.objects.create(
            name="Cabinet Office Exercise",
            status="active",
            initiated_by=self.internal_user,
        )
        self.client.force_authenticate(self.internal_user)

    def _items(self, payload):
        if isinstance(payload, list):
            return payload
        return payload.get("results", [])

    def test_government_exercises_alias_endpoint_exposes_additive_fields(self):
        response = self.client.get("/api/government/exercises/")
        self.assertEqual(response.status_code, 200)
        items = self._items(response.json())
        target = next((item for item in items if item["id"] == str(self.campaign.id)), None)
        self.assertIsNotNone(target)
        self.assertEqual(target["appointment_exercise_name"], self.campaign.name)
        self.assertEqual(target["appointment_exercise_status"], self.campaign.status)
        self.assertIn("office_ids", target)
        self.assertIn("appointment_route_template_id", target)


