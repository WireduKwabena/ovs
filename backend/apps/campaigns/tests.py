from rest_framework.test import APITestCase
from django.test import override_settings

from apps.authentication.models import User
from apps.billing.models import BillingSubscription
from apps.candidates.models import Candidate, CandidateEnrollment
from apps.campaigns.models import CampaignRubricVersion, VettingCampaign


class CampaignAuthorizationTests(APITestCase):
    def setUp(self):
        self.hr_one = User.objects.create_user(
            email="hr_campaign_one@example.com",
            password="Pass1234!",
            first_name="HR",
            last_name="One",
            user_type="hr_manager",
        )
        self.hr_two = User.objects.create_user(
            email="hr_campaign_two@example.com",
            password="Pass1234!",
            first_name="HR",
            last_name="Two",
            user_type="hr_manager",
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
        self.campaign_one = VettingCampaign.objects.create(name="Campaign One", initiated_by=self.hr_one)
        self.campaign_two = VettingCampaign.objects.create(name="Campaign Two", initiated_by=self.hr_two)
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
            created_by=self.hr_one,
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
            created_by=self.hr_one,
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

    def test_hr_manager_sees_only_own_campaigns(self):
        self.client.force_authenticate(self.hr_one)
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

    def test_hr_manager_cannot_access_other_campaign_detail(self):
        self.client.force_authenticate(self.hr_one)
        response = self.client.get(f"/api/campaigns/{self.campaign_two.id}/")
        self.assertEqual(response.status_code, 404)

    def test_admin_sees_all_campaigns(self):
        self.client.force_authenticate(self.admin)
        response = self.client.get("/api/campaigns/")
        self.assertEqual(response.status_code, 200)
        ids = {item["id"] for item in self._items(response.json())}
        self.assertIn(str(self.campaign_one.id), ids)
        self.assertIn(str(self.campaign_two.id), ids)

    def test_hr_manager_can_define_required_document_types(self):
        self.client.force_authenticate(self.hr_one)
        payload = {
            "name": "Required Docs Campaign",
            "status": "draft",
            "required_document_types": ["id_card", "passport", "id_card"],
        }

        response = self.client.post("/api/campaigns/", payload, format="json")
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["required_document_types"], ["id_card", "passport"])

        campaign = VettingCampaign.objects.get(id=data["id"])
        settings_json = campaign.settings_json if isinstance(campaign.settings_json, dict) else {}
        self.assertEqual(settings_json.get("required_document_types"), ["id_card", "passport"])

    def test_hr_manager_can_list_own_campaign_rubric_versions(self):
        self.client.force_authenticate(self.hr_one)
        response = self.client.get(f"/api/campaigns/{self.campaign_one.id}/rubrics/versions/")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(isinstance(payload, list))
        ids = {item["id"] for item in payload}
        self.assertEqual(ids, {str(self.version_one.id), str(self.version_two.id)})
        self.assertEqual(payload[0]["version"], 2)

    def test_hr_manager_cannot_list_other_campaign_rubric_versions(self):
        self.client.force_authenticate(self.hr_one)
        response = self.client.get(f"/api/campaigns/{self.campaign_two.id}/rubrics/versions/")
        self.assertEqual(response.status_code, 404)

    def test_hr_manager_can_add_campaign_rubric_version(self):
        self.client.force_authenticate(self.hr_one)
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

    def test_hr_manager_can_activate_campaign_rubric_version(self):
        self.client.force_authenticate(self.hr_one)
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

    def test_hr_manager_cannot_activate_other_campaign_rubric_version(self):
        self.client.force_authenticate(self.hr_one)
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
            created_by=self.hr_two,
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
    def test_hr_manager_import_candidates_respects_plan_quota(self):
        self._seed_subscription(self.hr_one, plan_id="starter", plan_name="Starter")
        self.client.force_authenticate(self.hr_one)

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
    def test_hr_manager_import_candidates_requires_active_subscription(self):
        self.client.force_authenticate(self.hr_one)

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
