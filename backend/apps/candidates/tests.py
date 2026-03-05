from rest_framework.test import APITestCase
from django.test import override_settings

from apps.authentication.models import User
from apps.billing.models import BillingSubscription
from apps.campaigns.models import VettingCampaign
from apps.candidates.models import Candidate, CandidateEnrollment, CandidateSocialProfile


class CandidateEnrollmentAuthorizationTests(APITestCase):
    def setUp(self):
        self.hr_one = User.objects.create_user(
            email="hr_candidates_one@example.com",
            password="Pass1234!",
            first_name="HR",
            last_name="One",
            user_type="hr_manager",
        )
        self.hr_two = User.objects.create_user(
            email="hr_candidates_two@example.com",
            password="Pass1234!",
            first_name="HR",
            last_name="Two",
            user_type="hr_manager",
        )
        self.admin = User.objects.create_user(
            email="admin_candidates@example.com",
            password="Pass1234!",
            first_name="Admin",
            last_name="Candidates",
            user_type="admin",
            is_staff=True,
        )

        self.campaign_one = VettingCampaign.objects.create(name="HR1 Campaign", initiated_by=self.hr_one)
        self.campaign_two = VettingCampaign.objects.create(name="HR2 Campaign", initiated_by=self.hr_two)
        self.candidate = Candidate.objects.create(
            first_name="Jane",
            last_name="Candidate",
            email="candidate_scope@example.com",
        )
        self.enrollment_one = CandidateEnrollment.objects.create(
            campaign=self.campaign_one,
            candidate=self.candidate,
            status="invited",
        )
        self.enrollment_two = CandidateEnrollment.objects.create(
            campaign=self.campaign_two,
            candidate=Candidate.objects.create(
                first_name="John",
                last_name="Other",
                email="other_scope@example.com",
            ),
            status="invited",
        )
        self.profile_one = CandidateSocialProfile.objects.create(
            candidate=self.candidate,
            platform="linkedin",
            url="https://linkedin.com/in/candidate-scope",
            username="candidate-scope",
            is_primary=True,
        )
        self.profile_two = CandidateSocialProfile.objects.create(
            candidate=self.enrollment_two.candidate,
            platform="github",
            url="https://github.com/other-scope",
            username="other-scope",
            is_primary=True,
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

    def test_hr_manager_lists_only_own_enrollments(self):
        self.client.force_authenticate(self.hr_one)
        response = self.client.get("/api/enrollments/")
        self.assertEqual(response.status_code, 200)
        ids = {item["id"] for item in self._items(response.json())}
        self.assertIn(str(self.enrollment_one.id), ids)
        self.assertNotIn(str(self.enrollment_two.id), ids)

    def test_hr_manager_cannot_create_enrollment_for_other_campaign(self):
        self.client.force_authenticate(self.hr_one)
        response = self.client.post(
            "/api/enrollments/",
            {
                "campaign": self.campaign_two.id,
                "candidate": self.candidate.id,
                "status": "invited",
                "metadata": {},
            },
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_admin_can_list_all_enrollments(self):
        self.client.force_authenticate(self.admin)
        response = self.client.get("/api/enrollments/")
        self.assertEqual(response.status_code, 200)
        ids = {item["id"] for item in self._items(response.json())}
        self.assertIn(str(self.enrollment_one.id), ids)
        self.assertIn(str(self.enrollment_two.id), ids)

    def test_hr_manager_lists_only_own_social_profiles(self):
        self.client.force_authenticate(self.hr_one)
        response = self.client.get("/api/social-profiles/")

        self.assertEqual(response.status_code, 200)
        ids = {item["id"] for item in self._items(response.json())}
        self.assertIn(str(self.profile_one.id), ids)
        self.assertNotIn(str(self.profile_two.id), ids)

    def test_hr_manager_cannot_create_social_profile_for_other_campaign_candidate(self):
        self.client.force_authenticate(self.hr_one)
        response = self.client.post(
            "/api/social-profiles/",
            {
                "candidate": self.enrollment_two.candidate.id,
                "platform": "linkedin",
                "url": "https://linkedin.com/in/not-allowed",
                "username": "not-allowed",
                "is_primary": False,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_admin_can_create_social_profile_for_any_candidate(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(
            "/api/social-profiles/",
            {
                "candidate": self.enrollment_two.candidate.id,
                "platform": "linkedin",
                "url": "https://linkedin.com/in/admin-created",
                "username": "admin-created",
                "is_primary": False,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["candidate"], str(self.enrollment_two.candidate.id))

    @override_settings(
        BILLING_QUOTA_ENFORCEMENT_ENABLED=True,
        BILLING_PLAN_STARTER_CANDIDATES_PER_MONTH=2,
    )
    def test_hr_manager_enrollment_requires_active_subscription(self):
        candidate = Candidate.objects.create(
            first_name="No",
            last_name="Subscription",
            email="no_subscription@example.com",
        )

        self.client.force_authenticate(self.hr_one)
        response = self.client.post(
            "/api/enrollments/",
            {
                "campaign": self.campaign_one.id,
                "candidate": candidate.id,
                "status": "invited",
                "metadata": {},
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertEqual(payload.get("code"), "subscription_required")
        self.assertIn("quota", payload)
        self.assertIn("period_start", payload["quota"])
        self.assertIn("period_end", payload["quota"])
        self.assertTrue(str(payload["quota"].get("period_start")))
        self.assertTrue(str(payload["quota"].get("period_end")))

    @override_settings(
        BILLING_QUOTA_ENFORCEMENT_ENABLED=True,
        BILLING_PLAN_STARTER_CANDIDATES_PER_MONTH=2,
    )
    def test_hr_manager_quota_blocks_new_enrollment_after_plan_limit(self):
        self._seed_subscription(self.hr_one, plan_id="starter", plan_name="Starter")

        for idx in range(2):
            limited_candidate = Candidate.objects.create(
                first_name=f"Limited{idx}",
                last_name="Candidate",
                email=f"limited_{idx}@example.com",
            )
            CandidateEnrollment.objects.create(
                campaign=self.campaign_one,
                candidate=limited_candidate,
                status="invited",
            )

        extra_candidate = Candidate.objects.create(
            first_name="Overflow",
            last_name="Candidate",
            email="overflow_candidate@example.com",
        )

        self.client.force_authenticate(self.hr_one)
        response = self.client.post(
            "/api/enrollments/",
            {
                "campaign": self.campaign_one.id,
                "candidate": extra_candidate.id,
                "status": "invited",
                "metadata": {},
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertEqual(payload.get("code"), "quota_exceeded")
        self.assertIn("quota", payload)
        self.assertIn("period_start", payload["quota"])
        self.assertIn("period_end", payload["quota"])
        self.assertTrue(str(payload["quota"].get("period_start")))
        self.assertTrue(str(payload["quota"].get("period_end")))
