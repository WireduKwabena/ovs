from rest_framework import status
from rest_framework.test import APITestCase

from apps.authentication.models import User


class EmailAuthEndpointTests(APITestCase):
    def setUp(self):
        self.password = "Pass1234!"
        self.user = User.objects.create_user(
            email="firm_admin@example.com",
            password=self.password,
            first_name="Firm",
            last_name="Admin",
            user_type="hr_manager",
        )

    def test_register_with_email_password(self):
        response = self.client.post(
            "/api/auth/register/",
            {
                "email": "new_firm@example.com",
                "password": self.password,
                "password_confirm": self.password,
                "first_name": "New",
                "last_name": "Firm",
                "phone_number": "+12345678901",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        payload = response.json()
        self.assertEqual(payload["user"]["email"], "new_firm@example.com")
        self.assertIn("access", payload["tokens"])
        self.assertIn("refresh", payload["tokens"])
        self.assertEqual(
            User.objects.get(email="new_firm@example.com").user_type,
            "hr_manager",
        )

    def test_login_with_email_password(self):
        response = self.client.post(
            "/api/auth/login/",
            {
                "email": self.user.email,
                "password": self.password,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = response.json()
        self.assertEqual(payload["user"]["email"], self.user.email)
        self.assertIn("access", payload["tokens"])
        self.assertIn("refresh", payload["tokens"])

    def test_social_login_endpoints_are_disabled(self):
        google = self.client.post("/api/auth/google/login/", {"code": "mock"}, format="json")
        github = self.client.post("/api/auth/github/login/", {"code": "mock"}, format="json")

        self.assertEqual(google.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(github.status_code, status.HTTP_404_NOT_FOUND)
