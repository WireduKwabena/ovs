from rest_framework.test import APITestCase

from apps.authentication.models import User
from apps.campaigns.models import VettingCampaign


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
        self.campaign_one = VettingCampaign.objects.create(name="Campaign One", initiated_by=self.hr_one)
        self.campaign_two = VettingCampaign.objects.create(name="Campaign Two", initiated_by=self.hr_two)

    def _items(self, payload):
        if isinstance(payload, list):
            return payload
        return payload.get("results", [])

    def test_hr_manager_sees_only_own_campaigns(self):
        self.client.force_authenticate(self.hr_one)
        response = self.client.get("/api/campaigns/")
        self.assertEqual(response.status_code, 200)
        ids = {item["id"] for item in self._items(response.json())}
        self.assertIn(str(self.campaign_one.id), ids)
        self.assertNotIn(str(self.campaign_two.id), ids)

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
