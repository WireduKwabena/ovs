from rest_framework.test import APITestCase

from apps.authentication.models import User
from apps.candidates.models import Candidate
from apps.personnel.models import PersonnelRecord


class PersonnelApiTests(APITestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(
            email="personnel_admin@example.com",
            password="Pass1234!",
            first_name="Personnel",
            last_name="Admin",
            user_type="admin",
        )
        self.candidate = Candidate.objects.create(
            first_name="Jane",
            last_name="Nominee",
            email="jane.nominee@example.com",
        )
        self.record = PersonnelRecord.objects.create(
            full_name="Jane Nominee",
            is_public=True,
            is_active_officeholder=True,
        )

    def test_officeholders_is_public(self):
        response = self.client.get("/api/personnel/officeholders/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)
        item = response.json()[0]
        self.assertNotIn("contact_email", item)
        self.assertNotIn("contact_phone", item)
        self.assertNotIn("national_id_hash", item)
        self.assertNotIn("national_id_encrypted", item)

    def test_link_candidate_requires_hr_or_admin(self):
        response = self.client.post(
            f"/api/personnel/{self.record.id}/link-candidate/",
            {"candidate_id": str(self.candidate.id)},
            format="json",
        )
        self.assertIn(response.status_code, {401, 403})

        self.client.force_authenticate(self.admin_user)
        success = self.client.post(
            f"/api/personnel/{self.record.id}/link-candidate/",
            {"candidate_id": str(self.candidate.id)},
            format="json",
        )
        self.assertEqual(success.status_code, 200)
        self.record.refresh_from_db()
        self.assertEqual(self.record.linked_candidate_id, self.candidate.id)
