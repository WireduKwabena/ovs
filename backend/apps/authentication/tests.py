from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.tokens import default_token_generator
from django.core.signing import Signer
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

    def test_password_reset_confirm_with_signed_token_changes_password(self):
        raw_token = default_token_generator.make_token(self.user)
        signed_token = Signer().sign(f"{self.user.pk}:{raw_token}")
        new_password = "NewPass1234!"

        response = self.client.post(
            "/api/auth/password-reset-confirm/",
            {
                "token": signed_token,
                "new_password": new_password,
                "new_password_confirm": new_password,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(new_password))

    def test_password_reset_confirm_rejects_invalid_token(self):
        response = self.client.post(
            "/api/auth/password-reset-confirm/",
            {
                "token": "invalid-token",
                "new_password": "NewPass1234!",
                "new_password_confirm": "NewPass1234!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)

    def test_two_factor_setup_stores_plain_totp_secret(self):
        admin = User.objects.create_user(
            email="admin2fa@example.com",
            password=self.password,
            first_name="Admin",
            last_name="2FA",
            user_type="admin",
            is_staff=True,
        )
        self.client.force_authenticate(user=admin)

        with patch(
            "apps.authentication.views.pyotp",
            SimpleNamespace(random_base32=lambda: "A" * 32),
        ), patch.object(
            User,
            "get_totp_uri",
            return_value="otpauth://totp/OVS-Redo:admin2fa@example.com",
        ):
            response = self.client.get("/api/auth/admin/2fa/setup/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        admin.refresh_from_db()
        self.assertEqual(admin.two_factor_secret, "A" * 32)
        self.assertIn("provisioning_uri", response.data)
