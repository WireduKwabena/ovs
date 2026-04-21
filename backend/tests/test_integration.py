# backend/tests/test_integration.py
"""
Cross-app smoke tests that verify shared infrastructure works end-to-end.
These run against the test database and do not require external services.
"""
from django.test import TestCase
from apps.users.models import User


class AuthSmokeTest(TestCase):
    """Verify the login → token flow returns the expected shape."""

    def setUp(self):
        self.user = User.objects.create_user(
            email="smoke@example.com",
            password="SmokePass1!",
            full_name="Smoke User",
            date_of_birth="1990-01-01",
        )

    def test_login_returns_access_token(self):
        response = self.client.post(
            "/api/auth/login/",
            {"email": "smoke@example.com", "password": "SmokePass1!"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("tokens", data)
        self.assertIn("access", data["tokens"])

    def test_protected_endpoint_rejects_unauthenticated_request(self):
        response = self.client.get("/api/v1/campaigns/")
        self.assertIn(response.status_code, (401, 403))
