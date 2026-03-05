from datetime import timedelta
import time
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.hashers import check_password
from django.core.signing import Signer
from django.test import override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.authentication.models import User, UserProfile
from apps.billing.models import BillingSubscription


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

    @override_settings(AUTH_PUBLIC_REGISTRATION_ENABLED=True)
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
        self.assertNotIn("tokens", payload)
        self.assertEqual(payload["message"], "Registration successful. Please sign in to continue.")
        self.assertEqual(payload["user_type"], "hr_manager")
        self.assertEqual(
            User.objects.get(email="new_firm@example.com").user_type,
            "hr_manager",
        )

    def test_register_is_disabled_by_default(self):
        response = self.client.post(
            "/api/auth/register/",
            {
                "email": "blocked@example.com",
                "password": self.password,
                "password_confirm": self.password,
                "first_name": "Blocked",
                "last_name": "User",
                "phone_number": "+12345678901",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("error", response.data)

    def test_register_with_valid_subscription_reference_when_public_disabled(self):
        subscription = BillingSubscription.objects.create(
            provider="sandbox",
            status="complete",
            payment_status="paid",
            plan_id="growth",
            plan_name="Growth",
            billing_cycle="monthly",
            payment_method="card",
            amount_usd="399.00",
            reference="OVS-VALIDREF",
            ticket_confirmed_at=timezone.now(),
            ticket_expires_at=timezone.now() + timedelta(hours=12),
        )

        response = self.client.post(
            "/api/auth/register/",
            {
                "email": "subscribed@example.com",
                "password": self.password,
                "password_confirm": self.password,
                "first_name": "Subscribed",
                "last_name": "Firm",
                "phone_number": "+12345678901",
                "subscription_reference": "OVS-VALIDREF",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.filter(email="subscribed@example.com").exists())

        subscription.refresh_from_db()
        self.assertIsNotNone(subscription.registration_consumed_at)
        self.assertEqual(subscription.registration_consumed_by_email, "subscribed@example.com")

    def test_register_rejects_reused_subscription_reference(self):
        BillingSubscription.objects.create(
            provider="sandbox",
            status="complete",
            payment_status="paid",
            plan_id="growth",
            plan_name="Growth",
            billing_cycle="monthly",
            payment_method="card",
            amount_usd="399.00",
            reference="OVS-USEDREF",
            ticket_confirmed_at=timezone.now(),
            ticket_expires_at=timezone.now() + timedelta(hours=12),
            registration_consumed_at=timezone.now(),
            registration_consumed_by_email="existing@example.com",
        )

        response = self.client.post(
            "/api/auth/register/",
            {
                "email": "second@example.com",
                "password": self.password,
                "password_confirm": self.password,
                "first_name": "Second",
                "last_name": "Firm",
                "phone_number": "+12345678901",
                "subscription_reference": "OVS-USEDREF",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(User.objects.filter(email="second@example.com").exists())

    def test_login_requires_2fa_for_non_applicant_accounts(self):
        with patch(
            "apps.authentication.views.pyotp",
            SimpleNamespace(random_base32=lambda: "A" * 32),
        ):
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
        self.assertNotIn("tokens", payload)
        self.assertEqual(payload["user_type"], "hr_manager")
        self.assertTrue(payload.get("setup_required"))
        self.assertIn("token", payload)
        self.assertIn("expires_in_seconds", payload)

        self.user.refresh_from_db()
        self.assertEqual(self.user.two_factor_secret, "A" * 32)

    def test_login_is_case_insensitive_for_email(self):
        with patch(
            "apps.authentication.views.pyotp",
            SimpleNamespace(random_base32=lambda: "A" * 32),
        ):
            response = self.client.post(
                "/api/auth/login/",
                {
                    "email": "FIRM_ADMIN@EXAMPLE.COM",
                    "password": self.password,
                },
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("token", response.data)

    def test_login_issues_tokens_for_applicant(self):
        applicant = User.objects.create_user(
            email="applicant@example.com",
            password=self.password,
            first_name="Applicant",
            last_name="User",
            user_type="applicant",
        )

        response = self.client.post(
            "/api/auth/login/",
            {
                "email": applicant.email,
                "password": self.password,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = response.json()
        self.assertIn("tokens", payload)
        self.assertIn("access", payload["tokens"])
        self.assertIn("refresh", payload["tokens"])
        self.assertEqual(payload["user_type"], "applicant")

    def test_login_verify_enables_2fa_and_returns_tokens(self):
        with patch(
            "apps.authentication.views.pyotp",
            SimpleNamespace(random_base32=lambda: "A" * 32),
        ):
            challenge = self.client.post(
                "/api/auth/login/",
                {
                    "email": self.user.email,
                    "password": self.password,
                },
                format="json",
            )

        self.assertEqual(challenge.status_code, status.HTTP_200_OK)
        token = challenge.data["token"]

        with patch.object(User, "verify_totp", return_value=True):
            verify_response = self.client.post(
                "/api/auth/login/verify/",
                {
                    "token": token,
                    "otp": "123456",
                },
                format="json",
            )

        self.assertEqual(verify_response.status_code, status.HTTP_200_OK)
        payload = verify_response.json()
        self.assertIn("tokens", payload)
        self.assertEqual(payload["user_type"], "hr_manager")

        self.user.refresh_from_db()
        self.assertTrue(self.user.is_two_factor_enabled)

    def test_login_verify_rejects_reused_challenge_token(self):
        with patch(
            "apps.authentication.views.pyotp",
            SimpleNamespace(random_base32=lambda: "A" * 32),
        ):
            challenge = self.client.post(
                "/api/auth/login/",
                {
                    "email": self.user.email,
                    "password": self.password,
                },
                format="json",
            )

        self.assertEqual(challenge.status_code, status.HTTP_200_OK)
        token = challenge.data["token"]

        with patch.object(User, "verify_totp", return_value=True):
            first_verify = self.client.post(
                "/api/auth/login/verify/",
                {
                    "token": token,
                    "otp": "123456",
                },
                format="json",
            )
            second_verify = self.client.post(
                "/api/auth/login/verify/",
                {
                    "token": token,
                    "otp": "123456",
                },
                format="json",
            )

        self.assertEqual(first_verify.status_code, status.HTTP_200_OK)
        self.assertEqual(second_verify.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", second_verify.data)
        self.assertIn("already used", second_verify.data["error"].lower())

    @override_settings(AUTH_TWO_FACTOR_CHALLENGE_TTL_SECONDS=1)
    def test_login_verify_rejects_expired_challenge_token(self):
        with patch(
            "apps.authentication.views.pyotp",
            SimpleNamespace(random_base32=lambda: "A" * 32),
        ):
            challenge = self.client.post(
                "/api/auth/login/",
                {
                    "email": self.user.email,
                    "password": self.password,
                },
                format="json",
            )

        self.assertEqual(challenge.status_code, status.HTTP_200_OK)
        token = challenge.data["token"]

        time.sleep(2)

        with patch.object(User, "verify_totp", return_value=True):
            verify_response = self.client.post(
                "/api/auth/login/verify/",
                {
                    "token": token,
                    "otp": "123456",
                },
                format="json",
            )

        self.assertEqual(verify_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", verify_response.data)
        self.assertIn("expired", verify_response.data["error"].lower())

    def test_login_verify_accepts_backup_code_and_consumes_it(self):
        self.user.is_two_factor_enabled = True
        self.user.two_factor_secret = "A" * 32
        self.user.save(update_fields=["is_two_factor_enabled", "two_factor_secret", "updated_at"])
        backup_codes = self.user.generate_backup_codes(count=1, length=8)

        with patch(
            "apps.authentication.views.pyotp",
            SimpleNamespace(random_base32=lambda: "A" * 32),
        ):
            challenge = self.client.post(
                "/api/auth/login/",
                {
                    "email": self.user.email,
                    "password": self.password,
                },
                format="json",
            )

        self.assertEqual(challenge.status_code, status.HTTP_200_OK)
        token = challenge.data["token"]

        verify_response = self.client.post(
            "/api/auth/login/verify/",
            {
                "token": token,
                "backup_code": backup_codes[0],
            },
            format="json",
        )

        self.assertEqual(verify_response.status_code, status.HTTP_200_OK)
        self.assertIn("tokens", verify_response.data)

        self.user.refresh_from_db()
        self.assertEqual(self.user.two_factor_backup_codes, [])

    @override_settings(AUTH_TWO_FACTOR_BACKUP_CODE_COUNT=3, AUTH_TWO_FACTOR_BACKUP_CODE_LENGTH=8)
    def test_login_verify_first_success_returns_initial_backup_codes(self):
        with patch(
            "apps.authentication.views.pyotp",
            SimpleNamespace(random_base32=lambda: "A" * 32),
        ):
            challenge = self.client.post(
                "/api/auth/login/",
                {
                    "email": self.user.email,
                    "password": self.password,
                },
                format="json",
            )

        self.assertEqual(challenge.status_code, status.HTTP_200_OK)
        token = challenge.data["token"]

        with patch.object(User, "verify_totp", return_value=True):
            verify_response = self.client.post(
                "/api/auth/login/verify/",
                {
                    "token": token,
                    "otp": "123456",
                },
                format="json",
            )

        self.assertEqual(verify_response.status_code, status.HTTP_200_OK)
        self.assertIn("backup_codes", verify_response.data)
        self.assertEqual(len(verify_response.data["backup_codes"]), 3)

        self.user.refresh_from_db()
        self.assertEqual(len(self.user.two_factor_backup_codes), 3)
        self.assertTrue(
            check_password(
                User._normalize_backup_code(verify_response.data["backup_codes"][0]),
                self.user.two_factor_backup_codes[0],
            )
        )

    def test_login_verify_requires_exactly_one_2fa_factor(self):
        with patch(
            "apps.authentication.views.pyotp",
            SimpleNamespace(random_base32=lambda: "A" * 32),
        ):
            challenge = self.client.post(
                "/api/auth/login/",
                {
                    "email": self.user.email,
                    "password": self.password,
                },
                format="json",
            )

        self.assertEqual(challenge.status_code, status.HTTP_200_OK)
        token = challenge.data["token"]

        response = self.client.post(
            "/api/auth/login/verify/",
            {
                "token": token,
                "otp": "123456",
                "backup_code": "ABCD-EFGH",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_admin_login_returns_2fa_challenge(self):
        admin = User.objects.create_user(
            email="admin@example.com",
            password=self.password,
            first_name="System",
            last_name="Admin",
            user_type="admin",
            is_staff=True,
        )

        with patch(
            "apps.authentication.views.pyotp",
            SimpleNamespace(random_base32=lambda: "B" * 32),
        ):
            response = self.client.post(
                "/api/auth/admin/login/",
                {
                    "email": admin.email,
                    "password": self.password,
                },
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("token", response.data)
        self.assertNotIn("tokens", response.data)

    def test_admin_login_is_case_insensitive_for_email(self):
        admin = User.objects.create_user(
            email="admin-ci@example.com",
            password=self.password,
            first_name="System",
            last_name="Admin",
            user_type="admin",
            is_staff=True,
        )

        with patch(
            "apps.authentication.views.pyotp",
            SimpleNamespace(random_base32=lambda: "D" * 32),
        ):
            response = self.client.post(
                "/api/auth/admin/login/",
                {
                    "email": admin.email.upper(),
                    "password": self.password,
                },
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("token", response.data)

    def test_social_login_endpoints_are_disabled(self):
        google = self.client.post("/api/auth/google/login/", {"code": "mock"}, format="json")
        github = self.client.post("/api/auth/github/login/", {"code": "mock"}, format="json")

        self.assertEqual(google.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(github.status_code, status.HTTP_404_NOT_FOUND)

    def test_profile_view_includes_extended_profile(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.get("/api/auth/profile/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("profile", response.data["user"])
        self.assertIsNotNone(response.data["user"]["profile"])
        self.assertEqual(
            response.data["user"]["profile"]["profile_completion_percentage"],
            0,
        )

    def test_profile_update_updates_user_and_extended_profile_fields(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.put(
            "/api/auth/profile/update/",
            {
                "first_name": "Updated",
                "last_name": "Manager",
                "organization": "OVS Labs",
                "department": "Vetting",
                "phone_number": "+12345678911",
                "date_of_birth": "1990-03-10",
                "nationality": "Ghanaian",
                "city": "Accra",
                "country": "Ghana",
                "postal_code": "GA-001",
                "current_job_title": "Lead HR",
                "years_of_experience": 8,
                "linkedin_url": "https://www.linkedin.com/in/example",
                "bio": "Profile update integration test",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        profile = UserProfile.objects.get(user=self.user)

        self.assertEqual(self.user.first_name, "Updated")
        self.assertEqual(self.user.department, "Vetting")
        self.assertEqual(profile.city, "Accra")
        self.assertEqual(profile.years_of_experience, 8)
        self.assertGreater(profile.profile_completion_percentage, 0)
        self.assertEqual(response.data["profile"]["city"], "Accra")

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

    def test_two_factor_setup_allows_hr_manager(self):
        self.client.force_authenticate(user=self.user)

        with patch(
            "apps.authentication.views.pyotp",
            SimpleNamespace(random_base32=lambda: "C" * 32),
        ), patch.object(
            User,
            "get_totp_uri",
            return_value="otpauth://totp/OVS-Redo:firm_admin@example.com",
        ):
            response = self.client.get("/api/auth/admin/2fa/setup/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.two_factor_secret, "C" * 32)

    @override_settings(AUTH_TWO_FACTOR_BACKUP_CODE_COUNT=2, AUTH_TWO_FACTOR_BACKUP_CODE_LENGTH=8)
    def test_backup_codes_regenerate_with_otp(self):
        self.user.is_two_factor_enabled = True
        self.user.two_factor_secret = "A" * 32
        self.user.save(update_fields=["is_two_factor_enabled", "two_factor_secret", "updated_at"])
        self.client.force_authenticate(user=self.user)

        with patch.object(User, "verify_totp", return_value=True):
            response = self.client.post(
                "/api/auth/2fa/backup-codes/regenerate/",
                {"otp": "123456"},
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["backup_codes"]), 2)
        self.user.refresh_from_db()
        self.assertEqual(len(self.user.two_factor_backup_codes), 2)

    def test_backup_codes_regenerate_rejects_applicant(self):
        applicant = User.objects.create_user(
            email="backup-applicant@example.com",
            password=self.password,
            first_name="Backup",
            last_name="Applicant",
            user_type="applicant",
        )
        self.client.force_authenticate(user=applicant)

        response = self.client.post(
            "/api/auth/2fa/backup-codes/regenerate/",
            {"otp": "123456"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_two_factor_status_for_hr_manager(self):
        self.user.is_two_factor_enabled = True
        self.user.two_factor_secret = "A" * 32
        self.user.generate_backup_codes(count=2, length=8)
        self.client.force_authenticate(user=self.user)

        response = self.client.get("/api/auth/2fa/status/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["user_type"], "hr_manager")
        self.assertTrue(response.data["two_factor_required"])
        self.assertFalse(response.data["applicant_exempt"])
        self.assertTrue(response.data["is_two_factor_enabled"])
        self.assertTrue(response.data["has_totp_secret"])
        self.assertEqual(response.data["backup_codes_remaining"], 2)

    def test_two_factor_status_for_applicant(self):
        applicant = User.objects.create_user(
            email="status-applicant@example.com",
            password=self.password,
            first_name="Status",
            last_name="Applicant",
            user_type="applicant",
        )
        self.client.force_authenticate(user=applicant)

        response = self.client.get("/api/auth/2fa/status/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["user_type"], "applicant")
        self.assertFalse(response.data["two_factor_required"])
        self.assertTrue(response.data["applicant_exempt"])
