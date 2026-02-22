from rest_framework.test import APITestCase

from apps.authentication.models import User
from apps.campaigns.models import VettingCampaign
from apps.candidates.models import Candidate, CandidateEnrollment


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

    def _items(self, payload):
        if isinstance(payload, list):
            return payload
        return payload.get("results", [])

    def test_hr_manager_lists_only_own_enrollments(self):
        self.client.force_authenticate(self.hr_one)
        response = self.client.get("/api/enrollments/")
        self.assertEqual(response.status_code, 200)
        ids = {item["id"] for item in self._items(response.json())}
        self.assertIn(self.enrollment_one.id, ids)
        self.assertNotIn(self.enrollment_two.id, ids)

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
        self.assertIn(self.enrollment_one.id, ids)
        self.assertIn(self.enrollment_two.id, ids)
