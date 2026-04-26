from datetime import timedelta
import threading
import time
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth.models import Group
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.hashers import check_password
from django.core.signing import Signer
from django.db import close_old_connections, connection
from django.test import override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase, APIClient, APITransactionTestCase
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from apps.users.models import User, UserProfile
from apps.billing.models import BillingSubscription
from apps.billing.services import create_organization_onboarding_token
from apps.governance.models import Committee, CommitteeMembership, OrganizationMembership
from apps.tenants.models import Organization


class EmailAuthEndpointTests(APITestCase):
    def setUp(self):
        self.password = "Pass1234!"
        self.user = User.objects.create_user(
            email="firm_admin@example.com",
            password=self.password,
            first_name="Firm",
            last_name="Admin",
            user_type="internal",
        )

    def _create_org_subscription_and_token(
        self,
        *,
        org_code: str,
        org_name: str,
        plan_id: str = "growth",
        plan_name: str = "Growth",
        max_uses: int = 2,
        allowed_email_domain: str = "example.com",
    ):
        organization = Organization.objects.create(
            code=org_code,
            name=org_name,
            organization_type="agency",
            is_active=True,
        )
        OrganizationMembership.objects.create(
            user=self.user,
            membership_role="registry_admin",
            is_active=True,
            is_default=True,
        )
        subscription = BillingSubscription.objects.create(
            provider="sandbox",
            status="complete",
            payment_status="paid",
            plan_id=plan_id,
            plan_name=plan_name,
            billing_cycle="monthly",
            payment_method="card",
            amount_usd="399.00",
            reference=f"OVS-{org_code.upper()}",
            ticket_confirmed_at=timezone.now(),
            ticket_expires_at=timezone.now() + timedelta(hours=12),
        )
        token_record, raw_token = create_organization_onboarding_token(
            subscription=subscription,
            created_by=self.user,
            max_uses=max_uses,
            expires_at=timezone.now() + timedelta(hours=8),
            allowed_email_domain=allowed_email_domain,
            rotate=True,
        )
        return organization, subscription, token_record, raw_token

    def test_org_admin_bootstrap_registration_creates_internal_user_and_org_membership(self):
        response = self.client.post(
            "/api/auth/register/organization-admin/",
            {
                "email": "bootstrap.admin@example.com",
                "password": self.password,
                "password_confirm": self.password,
                "first_name": "Bootstrap",
                "last_name": "Admin",
                "phone_number": "+12345678901",
                "department": "Registry",
                "organization_name": "Bootstrap Secretariat",
                "organization_code": "bootstrap-secretariat",
                "organization_type": "agency",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        payload = response.json()
        self.assertEqual(payload["user_type"], "internal")
        self.assertEqual(payload["organization"]["name"], "Bootstrap Secretariat")

        created_user = User.objects.get(email="bootstrap.admin@example.com")
        self.assertEqual(created_user.user_type, "internal")
        self.assertEqual(created_user.organization, "Bootstrap Secretariat")
        self.assertTrue(
            OrganizationMembership.objects.filter(
                user=created_user,
                organization__name="Bootstrap Secretariat",
                membership_role="registry_admin",
                is_active=True,
                is_default=True,
            ).exists()
        )

    def test_org_admin_bootstrap_registration_rejects_duplicate_email(self):
        response = self.client.post(
            "/api/auth/register/organization-admin/",
            {
                "email": self.user.email,
                "password": self.password,
                "password_confirm": self.password,
                "first_name": "Duplicate",
                "last_name": "Email",
                "phone_number": "+12345678901",
                "organization_name": "Duplicate Org",
                "organization_type": "agency",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)

    def test_org_admin_bootstrap_registration_rejects_existing_organization_name(self):
        Organization.objects.create(
            code="existing-org",
            name="Existing Org Name",
            organization_type="agency",
            is_active=True,
        )

        response = self.client.post(
            "/api/auth/register/organization-admin/",
            {
                "email": "new.bootstrap@example.com",
                "password": self.password,
                "password_confirm": self.password,
                "first_name": "New",
                "last_name": "Bootstrap",
                "phone_number": "+12345678901",
                "organization_name": "Existing Org Name",
                "organization_type": "agency",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("organization_name", response.data)

    @override_settings(AUTH_PUBLIC_REGISTRATION_ENABLED=True)
    def test_register_requires_onboarding_token_even_when_public_registration_flag_enabled(self):
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

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("onboarding_token", response.data)
        self.assertFalse(User.objects.filter(email="new_firm@example.com").exists())

    def test_register_requires_onboarding_token_by_default(self):
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

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("onboarding_token", response.data)

    def test_register_rejects_subscription_reference_without_onboarding_token(self):
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

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("onboarding_token", response.data)
        self.assertFalse(User.objects.filter(email="subscribed@example.com").exists())

    def test_register_with_valid_onboarding_token_when_public_disabled(self):
        organization, _subscription, token_record, raw_token = self._create_org_subscription_and_token(
            org_code="auth-onboarding-org",
            org_name="Auth Onboarding Org",
        )

        response = self.client.post(
            "/api/auth/register/",
            {
                "email": "orgmember@example.com",
                "password": self.password,
                "password_confirm": self.password,
                "first_name": "Org",
                "last_name": "Member",
                "phone_number": "+12345678901",
                "onboarding_token": raw_token,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created_user = User.objects.get(email="orgmember@example.com")
        self.assertEqual(created_user.organization, organization.name)
        self.assertTrue(
            OrganizationMembership.objects.filter(
                user=created_user,
                is_active=True,
            ).exists()
        )
        token_record.refresh_from_db()
        self.assertEqual(token_record.uses, 1)
        self.assertEqual(token_record.is_active, True)

    def test_register_rejects_invalid_onboarding_token(self):
        response = self.client.post(
            "/api/auth/register/",
            {
                "email": "invalid.token@example.com",
                "password": self.password,
                "password_confirm": self.password,
                "first_name": "Invalid",
                "last_name": "Token",
                "phone_number": "+12345678901",
                "onboarding_token": "org_onb_invalid_value",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data.get("code"), "ONBOARDING_TOKEN_INVALID")
        self.assertEqual(response.data.get("reason"), "not_found")
        self.assertFalse(User.objects.filter(email="invalid.token@example.com").exists())

    def test_register_rejects_expired_onboarding_token(self):
        _organization, _subscription, token_record, raw_token = self._create_org_subscription_and_token(
            org_code="auth-onboarding-expired",
            org_name="Auth Onboarding Expired",
        )
        token_record.expires_at = timezone.now() - timedelta(minutes=1)
        token_record.save(update_fields=["expires_at", "updated_at"])

        response = self.client.post(
            "/api/auth/register/",
            {
                "email": "expired.member@example.com",
                "password": self.password,
                "password_confirm": self.password,
                "first_name": "Expired",
                "last_name": "Member",
                "phone_number": "+12345678901",
                "onboarding_token": raw_token,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data.get("reason"), "expired")
        token_record.refresh_from_db()
        self.assertEqual(token_record.uses, 0)
        self.assertFalse(User.objects.filter(email="expired.member@example.com").exists())

    def test_register_rejects_onboarding_token_when_subscription_inactive(self):
        _organization, subscription, token_record, raw_token = self._create_org_subscription_and_token(
            org_code="auth-onboarding-inactive-sub",
            org_name="Auth Onboarding Inactive Sub",
        )
        subscription.status = "canceled"
        subscription.payment_status = "unpaid"
        subscription.save(update_fields=["status", "payment_status", "updated_at"])

        response = self.client.post(
            "/api/auth/register/",
            {
                "email": "inactive.sub@example.com",
                "password": self.password,
                "password_confirm": self.password,
                "first_name": "Inactive",
                "last_name": "Subscription",
                "phone_number": "+12345678901",
                "onboarding_token": raw_token,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data.get("reason"), "subscription_inactive")
        token_record.refresh_from_db()
        self.assertEqual(token_record.uses, 0)
        self.assertFalse(User.objects.filter(email="inactive.sub@example.com").exists())

    def test_register_rejects_onboarding_token_max_uses_reached(self):
        _organization, _subscription, token_record, raw_token = self._create_org_subscription_and_token(
            org_code="auth-onboarding-max",
            org_name="Auth Onboarding Max",
            max_uses=1,
        )

        first_response = self.client.post(
            "/api/auth/register/",
            {
                "email": "first.member@example.com",
                "password": self.password,
                "password_confirm": self.password,
                "first_name": "First",
                "last_name": "Member",
                "phone_number": "+12345678901",
                "onboarding_token": raw_token,
            },
            format="json",
        )
        self.assertEqual(first_response.status_code, status.HTTP_201_CREATED)

        second_response = self.client.post(
            "/api/auth/register/",
            {
                "email": "second.member@example.com",
                "password": self.password,
                "password_confirm": self.password,
                "first_name": "Second",
                "last_name": "Member",
                "phone_number": "+12345678901",
                "onboarding_token": raw_token,
            },
            format="json",
        )
        self.assertEqual(second_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(User.objects.filter(email="second.member@example.com").exists())
        token_record.refresh_from_db()
        self.assertEqual(token_record.uses, 1)
        self.assertFalse(token_record.is_active)

    @override_settings(
        BILLING_ORG_MEMBER_QUOTA_ENFORCEMENT_ENABLED=True,
        BILLING_PLAN_STARTER_ORG_SEATS=1,
    )
    def test_register_rejects_onboarding_token_when_seat_quota_exceeded(self):
        organization, _subscription, token_record, raw_token = self._create_org_subscription_and_token(
            org_code="auth-seat-cap-full",
            org_name="Auth Seat Cap Full",
            plan_id="starter",
            plan_name="Starter",
            max_uses=5,
        )

        # Existing default membership for self.user already consumes the single starter seat.
        response = self.client.post(
            "/api/auth/register/",
            {
                "email": "quota.blocked@example.com",
                "password": self.password,
                "password_confirm": self.password,
                "first_name": "Quota",
                "last_name": "Blocked",
                "phone_number": "+12345678901",
                "onboarding_token": raw_token,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(User.objects.filter(email="quota.blocked@example.com").exists())
        self.assertEqual(response.data.get("code"), "ORG_SEAT_QUOTA_EXCEEDED")
        self.assertEqual(response.data.get("organization_id"), str(organization.id))
        token_record.refresh_from_db()
        self.assertEqual(token_record.uses, 0)
        self.assertTrue(token_record.is_active)

    @override_settings(
        BILLING_ORG_MEMBER_QUOTA_ENFORCEMENT_ENABLED=True,
        BILLING_PLAN_STARTER_ORG_SEATS=2,
    )
    def test_register_allows_onboarding_token_within_seat_quota(self):
        organization, _subscription, token_record, raw_token = self._create_org_subscription_and_token(
            org_code="auth-seat-cap-okay",
            org_name="Auth Seat Cap Okay",
            plan_id="starter",
            plan_name="Starter",
            max_uses=5,
        )

        response = self.client.post(
            "/api/auth/register/",
            {
                "email": "quota.allowed@example.com",
                "password": self.password,
                "password_confirm": self.password,
                "first_name": "Quota",
                "last_name": "Allowed",
                "phone_number": "+12345678901",
                "onboarding_token": raw_token,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created_user = User.objects.get(email="quota.allowed@example.com")
        self.assertTrue(
            OrganizationMembership.objects.filter(
                user=created_user,
                is_active=True,
            ).exists()
        )
        token_record.refresh_from_db()
        self.assertEqual(token_record.uses, 1)

    def test_register_duplicate_email_does_not_consume_token_or_create_membership(self):
        organization, _subscription, token_record, raw_token = self._create_org_subscription_and_token(
            org_code="auth-duplicate-email",
            org_name="Auth Duplicate Email Org",
        )
        existing_user = User.objects.create_user(
            email="existing.member@example.com",
            password=self.password,
            first_name="Existing",
            last_name="Member",
            user_type="internal",
        )
        existing_membership_count = OrganizationMembership.objects.filter(
            user=existing_user,
        ).count()

        response = self.client.post(
            "/api/auth/register/",
            {
                "email": "existing.member@example.com",
                "password": self.password,
                "password_confirm": self.password,
                "first_name": "Existing",
                "last_name": "Member",
                "phone_number": "+12345678901",
                "onboarding_token": raw_token,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)
        token_record.refresh_from_db()
        self.assertEqual(token_record.uses, 0)
        self.assertEqual(
            OrganizationMembership.objects.filter(
                user=existing_user,
            ).count(),
            existing_membership_count,
        )

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
        self.assertEqual(payload["user_type"], "internal")
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
        access_token = AccessToken(payload["tokens"]["access"])
        refresh_token = RefreshToken(payload["tokens"]["refresh"])
        self.assertIsNotNone(access_token.get("recent_auth_at"))
        self.assertIsNotNone(refresh_token.get("recent_auth_at"))

    def test_login_requires_2fa_for_applicant_with_internal_role_group(self):
        applicant = User.objects.create_user(
            email="applicant.internal@example.com",
            password=self.password,
            first_name="Applicant",
            last_name="Internal",
            user_type="applicant",
        )
        group, _ = Group.objects.get_or_create(name="vetting_officer")
        applicant.groups.add(group)

        with patch(
            "apps.authentication.views.pyotp",
            SimpleNamespace(random_base32=lambda: "E" * 32),
        ):
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
        self.assertIn("token", payload)
        self.assertNotIn("tokens", payload)
        self.assertTrue(payload.get("setup_required"))

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
        self.assertEqual(payload["user_type"], "internal")
        access_token = AccessToken(payload["tokens"]["access"])
        refresh_token = RefreshToken(payload["tokens"]["refresh"])
        self.assertIsNotNone(access_token.get("recent_auth_at"))
        self.assertIsNotNone(refresh_token.get("recent_auth_at"))

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

    def test_admin_login_rejects_staff_user_without_admin_role(self):
        staff_operator = User.objects.create_user(
            email="staff-operator@example.com",
            password=self.password,
            first_name="Staff",
            last_name="Operator",
            user_type="internal",
            is_staff=True,
        )

        response = self.client.post(
            "/api/auth/admin/login/",
            {
                "email": staff_operator.email,
                "password": self.password,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("non_field_errors", response.data)

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
                "current_job_title": "Lead Internal Reviewer",
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

    def test_profile_update_rejects_duplicate_email(self):
        self.client.force_authenticate(user=self.user)
        existing_user = User.objects.create_user(
            email="duplicate@example.com",
            password="OtherPass123!",
            first_name="Duplicate",
            last_name="Owner",
            user_type="internal",
        )

        response = self.client.put(
            "/api/auth/profile/update/",
            {"email": existing_user.email},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)

    @patch("apps.authentication.views.send_mail")
    @patch("apps.authentication.views.User.all_objects.get")
    def test_password_reset_request_sends_email_for_known_user(self, mock_get_user, mock_send_mail):
        mock_get_user.return_value = self.user
        response = self.client.post(
            "/api/auth/password-reset/",
            {"email": self.user.email},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_get_user.assert_called_once_with(email__iexact=self.user.email)
        mock_send_mail.assert_called_once()

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

    def test_two_factor_setup_caches_secret_and_does_not_persist_to_db(self):
        """
        The setup endpoint must store the pending secret in the cache only.
        Persisting it to the DB before OTP verification would allow an attacker
        who intercepts the provisioning_uri to register their own authenticator
        on the same secret before the user confirms ownership.
        """
        from django.core.cache import cache as django_cache

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
        self.assertIn("provisioning_uri", response.data)

        # Secret must be held in cache, NOT persisted to the DB yet.
        cached_secret = django_cache.get(f"2fa:pending_secret:{admin.pk}")
        self.assertEqual(cached_secret, "A" * 32, "Pending secret not stored in cache")
        admin.refresh_from_db()
        self.assertNotEqual(admin.two_factor_secret, "A" * 32,
                            "Secret must not be saved to DB before OTP verification")

    def test_two_factor_setup_allows_internal(self):
        from django.core.cache import cache as django_cache

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
        # Secret is in cache, not in DB.
        self.assertEqual(django_cache.get(f"2fa:pending_secret:{self.user.pk}"), "C" * 32)

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

    def test_two_factor_status_for_internal(self):
        self.user.is_two_factor_enabled = True
        self.user.two_factor_secret = "A" * 32
        self.user.generate_backup_codes(count=2, length=8)
        self.client.force_authenticate(user=self.user)

        response = self.client.get("/api/auth/2fa/status/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["user_type"], "internal")
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

    def test_two_factor_status_for_applicant_with_internal_role_requires_2fa(self):
        applicant = User.objects.create_user(
            email="status-applicant-internal@example.com",
            password=self.password,
            first_name="Status",
            last_name="ApplicantInternal",
            user_type="applicant",
        )
        group, _ = Group.objects.get_or_create(name="auditor")
        applicant.groups.add(group)
        self.client.force_authenticate(user=applicant)

        response = self.client.get("/api/auth/2fa/status/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["user_type"], "applicant")
        self.assertTrue(response.data["two_factor_required"])
        self.assertFalse(response.data["applicant_exempt"])

    def test_profile_view_exposes_roles_and_capabilities(self):
        group, _ = Group.objects.get_or_create(name="vetting_officer")
        self.user.groups.add(group)
        self.client.force_authenticate(user=self.user)

        response = self.client.get("/api/auth/profile/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("roles", response.data)
        self.assertIn("capabilities", response.data)
        self.assertTrue(response.data["is_internal_operator"])
        self.assertIn("vetting_officer", response.data["roles"])
        self.assertIn("roles", response.data["user"])
        self.assertIn("capabilities", response.data["user"])

    def test_profile_roles_do_not_treat_staff_as_admin_by_default(self):
        staff_operator = User.objects.create_user(
            email="staff-profile@example.com",
            password=self.password,
            first_name="Staff",
            last_name="Profile",
            user_type="internal",
            is_staff=True,
        )
        self.client.force_authenticate(user=staff_operator)

        response = self.client.get("/api/auth/profile/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("internal", response.data["roles"])
        self.assertNotIn("admin", response.data["roles"])

    @override_settings(AUTHZ_STAFF_IMPLIES_ADMIN=True)
    def test_profile_roles_can_preserve_legacy_staff_admin_mapping(self):
        staff_operator = User.objects.create_user(
            email="staff-profile-compat@example.com",
            password=self.password,
            first_name="Staff",
            last_name="Compat",
            user_type="internal",
            is_staff=True,
        )
        self.client.force_authenticate(user=staff_operator)

        response = self.client.get("/api/auth/profile/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("admin", response.data["roles"])

    def test_profile_view_includes_governance_context_for_single_org_membership(self):
        organization = Organization.objects.create(
            code="appointments-secretariat",
            name="Appointments Secretariat",
            organization_type="agency",
        )
        membership = OrganizationMembership.objects.create(
            user=self.user,
            is_active=True,
            is_default=True,
            membership_role="vetting_officer",
        )
        self.client.force_authenticate(user=self.user)

        response = self.client.get("/api/auth/profile/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("organizations", response.data)
        self.assertIn("organization_memberships", response.data)
        self.assertIn("active_organization", response.data)
        self.assertEqual(len(response.data["organizations"]), 1)
        self.assertEqual(response.data["organizations"][0]["id"], str(organization.id))
        self.assertEqual(response.data["active_organization"]["id"], str(organization.id))
        self.assertEqual(response.data["active_organization_source"], "default")
        self.assertEqual(response.data["organization_memberships"][0]["id"], str(membership.id))
        self.assertEqual(response.data["committees"], [])

    def test_active_organization_switching_supports_multi_org_user(self):
        org_one = Organization.objects.create(code="org-one", name="Organization One", organization_type="agency")
        org_two = Organization.objects.create(code="org-two", name="Organization Two", organization_type="agency")
        self.client.force_authenticate(user=self.user)

        membership_one = {
            "id": str(uuid4()),
            "organization_id": str(org_one.id),
            "organization_code": org_one.code,
            "organization_name": org_one.name,
            "organization_type": org_one.organization_type,
            "tier": str(getattr(org_one, "tier", "") or ""),
            "title": "Operations",
            "membership_role": "member",
            "is_default": True,
            "is_active": True,
            "joined_at": None,
            "left_at": None,
        }
        membership_two = {
            "id": str(uuid4()),
            "organization_id": str(org_two.id),
            "organization_code": org_two.code,
            "organization_name": org_two.name,
            "organization_type": org_two.organization_type,
            "tier": str(getattr(org_two, "tier", "") or ""),
            "title": "Approvals",
            "membership_role": "member",
            "is_default": False,
            "is_active": True,
            "joined_at": None,
            "left_at": None,
        }
        committee_record = {
            "id": str(uuid4()),
            "committee_id": str(uuid4()),
            "committee_code": "org-two-committee",
            "committee_name": "Org Two Committee",
            "committee_type": "approval",
            "organization_id": str(org_two.id),
            "organization_code": org_two.code,
            "organization_name": org_two.name,
            "committee_role": "member",
            "can_vote": True,
            "joined_at": None,
            "left_at": None,
        }

        with patch(
            "apps.core.authz._load_active_organization_memberships_for_user",
            side_effect=lambda _user_id, organization: (
                [dict(membership_one)]
                if organization.id == org_one.id
                else [dict(membership_two)]
                if organization.id == org_two.id
                else []
            ),
        ), patch(
            "apps.core.authz._load_active_committee_memberships_for_user",
            side_effect=lambda _user_id, organization: (
                [dict(committee_record)] if organization.id == org_two.id else []
            ),
        ):
            initial_profile = self.client.get("/api/auth/profile/")
            self.assertEqual(initial_profile.status_code, status.HTTP_200_OK)
            self.assertEqual(len(initial_profile.data["organizations"]), 2)
            self.assertEqual(initial_profile.data["active_organization"]["id"], str(org_one.id))
            self.assertEqual(initial_profile.data["active_organization_source"], "default")

            switch_response = self.client.post(
                "/api/auth/profile/active-organization/",
                {"organization_id": str(org_two.id)},
                format="json",
            )
            self.assertEqual(switch_response.status_code, status.HTTP_200_OK)
            self.assertEqual(switch_response.data["active_organization"]["id"], str(org_two.id))

            switched_profile = self.client.get("/api/auth/profile/")
            self.assertEqual(switched_profile.status_code, status.HTTP_200_OK)
            self.assertEqual(switched_profile.data["active_organization"]["id"], str(org_two.id))
            self.assertEqual(switched_profile.data["active_organization_source"], "session")
            self.assertEqual(len(switched_profile.data["committees"]), 1)
            self.assertEqual(switched_profile.data["committees"][0]["committee_id"], committee_record["committee_id"])

    def test_profile_view_for_applicant_without_org_membership_has_empty_context(self):
        applicant = User.objects.create_user(
            email="nomembership@example.com",
            password=self.password,
            first_name="No",
            last_name="Membership",
            user_type="applicant",
        )
        self.client.force_authenticate(user=applicant)

        response = self.client.get("/api/auth/profile/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["organizations"], [])
        self.assertEqual(response.data["organization_memberships"], [])
        self.assertEqual(response.data["committees"], [])
        self.assertIsNone(response.data["active_organization"])
        self.assertEqual(response.data["active_organization_source"], "none")


class EmailAuthRegistrationConcurrencyTests(APITransactionTestCase):
    def setUp(self):
        self.password = "Pass1234!"
        self._run_suffix = uuid4().hex[:8]
        self.inviter = User.objects.create_user(
            email=f"concurrency.inviter.{self._run_suffix}@example.com",
            password=self.password,
            first_name="Concurrency",
            last_name="Inviter",
            user_type="internal",
        )

    def _create_org_subscription_and_token(
        self,
        *,
        org_code: str,
        org_name: str,
        plan_id: str,
        plan_name: str,
        max_uses: int,
        allowed_email_domain: str = "example.com",
    ):
        org_code_with_suffix = f"{org_code}-{self._run_suffix}"
        organization = Organization.objects.create(
            code=org_code_with_suffix,
            name=org_name,
            organization_type="agency",
            is_active=True,
        )
        OrganizationMembership.objects.create(
            user=self.inviter,
            membership_role="registry_admin",
            is_active=True,
            is_default=True,
        )
        subscription = BillingSubscription.objects.create(
            provider="sandbox",
            status="complete",
            payment_status="paid",
            plan_id=plan_id,
            plan_name=plan_name,
            billing_cycle="monthly",
            payment_method="card",
            amount_usd="399.00",
            reference=f"OVS-CONCURRENCY-{org_code_with_suffix.upper()}",
            ticket_confirmed_at=timezone.now(),
            ticket_expires_at=timezone.now() + timedelta(hours=12),
        )
        token_record, raw_token = create_organization_onboarding_token(
            subscription=subscription,
            created_by=self.inviter,
            max_uses=max_uses,
            expires_at=timezone.now() + timedelta(hours=8),
            allowed_email_domain=allowed_email_domain,
            rotate=True,
        )
        return organization, subscription, token_record, raw_token

    def _run_parallel_registrations(self, *, token: str, emails: list[str]) -> list[tuple[str, int, dict]]:
        barrier = threading.Barrier(len(emails) + 1)
        lock = threading.Lock()
        results: list[tuple[str, int, dict]] = []
        errors: list[Exception] = []

        def _worker(email: str):
            try:
                close_old_connections()
                client = APIClient()
                barrier.wait(timeout=15)
                response = client.post(
                    "/api/auth/register/",
                    {
                        "email": email,
                        "password": self.password,
                        "password_confirm": self.password,
                        "first_name": "Concurrent",
                        "last_name": "Member",
                        "phone_number": "+12345678901",
                        "onboarding_token": token,
                    },
                    format="json",
                )
                payload = dict(response.data) if isinstance(response.data, dict) else {}
                with lock:
                    results.append((email, response.status_code, payload))
            except Exception as exc:
                with lock:
                    errors.append(exc)
            finally:
                close_old_connections()

        threads = [threading.Thread(target=_worker, args=(email,)) for email in emails]
        for thread in threads:
            thread.start()

        barrier.wait(timeout=15)
        for thread in threads:
            thread.join(timeout=20)

        if errors:
            raise AssertionError(f"Concurrency workers failed: {errors}")
        return results

    @override_settings(
        BILLING_ORG_MEMBER_QUOTA_ENFORCEMENT_ENABLED=True,
        BILLING_PLAN_STARTER_ORG_SEATS=2,
    )
    def test_concurrent_registration_does_not_exceed_seat_limit(self):
        if connection.vendor != "postgresql":
            self.skipTest("Concurrent row-locking registration test requires PostgreSQL.")

        organization, _subscription, token_record, raw_token = self._create_org_subscription_and_token(
            org_code="concurrency-seat-limit",
            org_name="Concurrency Seat Limit Org",
            plan_id="starter",
            plan_name="Starter",
            max_uses=10,
        )

        results = self._run_parallel_registrations(
            token=raw_token,
            emails=[
                f"parallel.one.{self._run_suffix}@example.com",
                f"parallel.two.{self._run_suffix}@example.com",
            ],
        )
        status_codes = [entry[1] for entry in results]

        self.assertEqual(status_codes.count(status.HTTP_201_CREATED), 1)
        self.assertEqual(status_codes.count(status.HTTP_400_BAD_REQUEST), 1)
        self.assertEqual(
            OrganizationMembership.objects.filter(
                is_active=True,
            ).count(),
            2,  # inviter + one successful onboarded user
        )

        token_record.refresh_from_db()
        self.assertEqual(token_record.uses, 1)

    @override_settings(
        BILLING_ORG_MEMBER_QUOTA_ENFORCEMENT_ENABLED=True,
        BILLING_PLAN_STARTER_ORG_SEATS=10,
    )
    def test_concurrent_registration_respects_token_max_uses(self):
        if connection.vendor != "postgresql":
            self.skipTest("Concurrent token-usage locking test requires PostgreSQL.")

        organization, _subscription, token_record, raw_token = self._create_org_subscription_and_token(
            org_code="concurrency-token-max",
            org_name="Concurrency Token Max Org",
            plan_id="starter",
            plan_name="Starter",
            max_uses=1,
        )

        results = self._run_parallel_registrations(
            token=raw_token,
            emails=[
                f"token.one.{self._run_suffix}@example.com",
                f"token.two.{self._run_suffix}@example.com",
            ],
        )
        status_codes = [entry[1] for entry in results]
        failure_reasons = [entry[2].get("reason") for entry in results if entry[1] != status.HTTP_201_CREATED]

        self.assertEqual(status_codes.count(status.HTTP_201_CREATED), 1)
        self.assertEqual(status_codes.count(status.HTTP_403_FORBIDDEN), 1)
        self.assertTrue(set(failure_reasons).issubset({"inactive", "max_uses_reached"}))

        token_record.refresh_from_db()
        self.assertEqual(token_record.uses, 1)
        self.assertFalse(token_record.is_active)
        self.assertEqual(
            OrganizationMembership.objects.filter(
                is_active=True,
            ).count(),
            2,  # inviter + one successful onboarded user
        )


