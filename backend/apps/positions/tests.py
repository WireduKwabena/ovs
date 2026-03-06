from rest_framework.test import APITestCase

from apps.authentication.models import User
from apps.positions.models import GovernmentPosition


class GovernmentPositionApiTests(APITestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(
            email="positions_admin@example.com",
            password="Pass1234!",
            first_name="Pos",
            last_name="Admin",
            user_type="admin",
        )
        GovernmentPosition.objects.create(
            title="Chief Justice",
            branch="judicial",
            institution="Judiciary",
            appointment_authority="President",
            is_public=True,
            is_vacant=True,
        )

    def test_public_positions_available_without_auth(self):
        response = self.client.get("/api/positions/public/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)
        item = response.json()[0]
        self.assertNotIn("rubric", item)
        self.assertNotIn("required_qualifications", item)
        self.assertNotIn("current_holder", item)

    def test_create_position_requires_hr_or_admin(self):
        response = self.client.post(
            "/api/positions/",
            {
                "title": "Attorney General",
                "branch": "executive",
                "institution": "Ministry of Justice",
                "appointment_authority": "President",
            },
            format="json",
        )
        self.assertIn(response.status_code, {401, 403})

        self.client.force_authenticate(self.admin_user)
        success = self.client.post(
            "/api/positions/",
            {
                "title": "Attorney General",
                "branch": "executive",
                "institution": "Ministry of Justice",
                "appointment_authority": "President",
            },
            format="json",
        )
        self.assertEqual(success.status_code, 201)
