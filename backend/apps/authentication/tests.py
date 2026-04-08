"""
End-to-end authentication flow tests.

All tests run inside the `test_tenant` schema provisioned by AllSchemasTestRunner.
Tenant-scoped requests pass `X-Organization-Slug: test-tenant` so TenantMiddleware
routes the connection to the right schema — mirroring real frontend behaviour.

Flows covered
─────────────
1.  Applicant login   → direct JWT tokens (no 2FA gate)
2.  Internal login    → 2FA challenge required
3.  Internal 2FA      → backup-code completion → JWT tokens
4.  Admin login       → always 2FA challenge (public-schema endpoint)
5.  Admin 2FA         → backup-code completion → JWT tokens
6.  Logout            → refresh token blacklisted
7.  Token refresh     → new access token issued
8.  Invalid credentials → 400 with error
9.  Org-admin bootstrap → creates org + admin user (public endpoint)
"""

from contextlib import contextmanager
from unittest.mock import patch

from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

try:
    import pyotp
    _PYOTP_AVAILABLE = True
except ImportError:  # pragma: no cover
    _PYOTP_AVAILABLE = False

from apps.users.models import User


# ---------------------------------------------------------------------------
# Mixins
# ---------------------------------------------------------------------------

class NoThrottleMixin:
    """
    Disable DRF rate throttles for the duration of each test.

    Strategy: clear the entire throttle cache in setUp so accumulated counts
    from other tests (or leftover Redis keys from --keepdb runs) don't cause
    spurious 429 responses.  The auth views use explicit @throttle_classes
    decorators so overriding DEFAULT_THROTTLE_CLASSES alone won't help.
    """

    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        super().setUp()


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_TENANT_SLUG = "test-tenant"
_TENANT_HEADER = {"HTTP_X_ORGANIZATION_SLUG": _TENANT_SLUG}


def _make_applicant(**kwargs) -> User:
    defaults = dict(
        email="applicant@test.local",
        password="TestPass123!",
        first_name="Test",
        last_name="Applicant",
        user_type="applicant",
        email_verified=True,
    )
    defaults.update(kwargs)
    password = defaults.pop("password")
    user = User(**defaults)
    user.set_password(password)
    user.save()
    return user


def _make_internal(**kwargs) -> User:
    defaults = dict(
        email="officer@test.local",
        password="TestPass123!",
        first_name="Internal",
        last_name="Officer",
        user_type="internal",
        email_verified=True,
    )
    defaults.update(kwargs)
    password = defaults.pop("password")
    user = User(**defaults)
    user.set_password(password)
    user.save()
    return user


def _make_admin(**kwargs) -> User:
    defaults = dict(
        email="platform.admin@test.local",
        password="TestAdmin123!",
        first_name="Platform",
        last_name="Admin",
        user_type="admin",
        is_staff=True,
        is_superuser=True,
        email_verified=True,
    )
    defaults.update(kwargs)
    password = defaults.pop("password")
    user = User(**defaults)
    user.set_password(password)
    user.save()
    return user


def _arm_user_with_backup_codes(user: User) -> list[str]:
    """Set a TOTP secret and generate backup codes. Returns the plaintext codes."""
    if _PYOTP_AVAILABLE:
        user.two_factor_secret = pyotp.random_base32()
        user.save(update_fields=["two_factor_secret", "updated_at"])
    return user.generate_backup_codes()


# ---------------------------------------------------------------------------
# 1. Applicant login — tenant-scoped, direct tokens
# ---------------------------------------------------------------------------

class ApplicantLoginTests(NoThrottleMixin, APITestCase):
    """
    user_type='applicant' maps to ROLE_NOMINEE.
    is_internal_operator() returns False → no 2FA → direct JWT tokens.
    """

    def setUp(self):
        super().setUp()
        self.user = _make_applicant()
        self.url = "/api/v1/auth/login/"

    def test_valid_credentials_return_jwt_tokens(self):
        resp = self.client.post(
            self.url,
            {"email": self.user.email, "password": "TestPass123!"},
            format="json",
            **_TENANT_HEADER,
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertIn("tokens", resp.data)
        self.assertIn("access", resp.data["tokens"])
        self.assertIn("refresh", resp.data["tokens"])
        self.assertEqual(resp.data["user_type"], "applicant")

    def test_response_contains_user_object(self):
        resp = self.client.post(
            self.url,
            {"email": self.user.email, "password": "TestPass123!"},
            format="json",
            **_TENANT_HEADER,
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("user", resp.data)
        self.assertEqual(resp.data["user"]["email"], self.user.email)

    def test_wrong_password_rejected(self):
        resp = self.client.post(
            self.url,
            {"email": self.user.email, "password": "WrongPass999!"},
            format="json",
            **_TENANT_HEADER,
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unknown_email_rejected(self):
        resp = self.client.post(
            self.url,
            {"email": "nobody@test.local", "password": "TestPass123!"},
            format="json",
            **_TENANT_HEADER,
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_missing_fields_rejected(self):
        resp = self.client.post(
            self.url,
            {"email": self.user.email},
            format="json",
            **_TENANT_HEADER,
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


# ---------------------------------------------------------------------------
# 2 & 3. Internal operator login — 2FA challenge → backup-code verify
# ---------------------------------------------------------------------------

class InternalLoginTwoFactorTests(NoThrottleMixin, APITestCase):
    """
    user_type='internal' is an operator — always gets a 2FA challenge.
    Test the full flow: login → challenge → verify with backup code → tokens.
    """

    def setUp(self):
        super().setUp()
        self.user = _make_internal()
        self.backup_codes = _arm_user_with_backup_codes(self.user)
        self.login_url = "/api/v1/auth/login/"
        self.verify_url = "/api/v1/auth/login/verify/"

    def _login(self):
        return self.client.post(
            self.login_url,
            {"email": self.user.email, "password": "TestPass123!"},
            format="json",
            **_TENANT_HEADER,
        )

    def test_login_returns_2fa_challenge(self):
        resp = self._login()
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertIn("token", resp.data)
        self.assertIn("message", resp.data)
        # No JWT tokens yet
        self.assertNotIn("access", resp.data)
        self.assertNotIn("tokens", resp.data)

    def test_challenge_contains_setup_required_flag(self):
        # After arming with a secret the flag should be False.
        resp = self._login()
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("setup_required", resp.data)

    def test_full_flow_backup_code_yields_tokens(self):
        challenge_resp = self._login()
        self.assertEqual(challenge_resp.status_code, status.HTTP_200_OK)
        challenge_token = challenge_resp.data["token"]

        verify_resp = self.client.post(
            self.verify_url,
            {"token": challenge_token, "backup_code": self.backup_codes[0]},
            format="json",
            **_TENANT_HEADER,
        )
        self.assertEqual(verify_resp.status_code, status.HTTP_200_OK, verify_resp.data)
        self.assertIn("tokens", verify_resp.data)
        self.assertIn("access", verify_resp.data["tokens"])
        self.assertIn("refresh", verify_resp.data["tokens"])

    def test_invalid_backup_code_rejected(self):
        challenge_resp = self._login()
        challenge_token = challenge_resp.data["token"]

        verify_resp = self.client.post(
            self.verify_url,
            {"token": challenge_token, "backup_code": "INVALID-CODE"},
            format="json",
            **_TENANT_HEADER,
        )
        self.assertEqual(verify_resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", verify_resp.data)

    def test_challenge_token_cannot_be_replayed(self):
        """Using the same challenge token twice must fail on the second attempt."""
        challenge_resp = self._login()
        challenge_token = challenge_resp.data["token"]
        code = self.backup_codes[0]

        first = self.client.post(
            self.verify_url,
            {"token": challenge_token, "backup_code": code},
            format="json",
            **_TENANT_HEADER,
        )
        self.assertEqual(first.status_code, status.HTTP_200_OK)

        # Re-arm so the backup code is available again for the replay attempt.
        self.user.refresh_from_db()
        fresh_codes = _arm_user_with_backup_codes(self.user)

        second = self.client.post(
            self.verify_url,
            {"token": challenge_token, "backup_code": fresh_codes[0]},
            format="json",
            **_TENANT_HEADER,
        )
        self.assertEqual(second.status_code, status.HTTP_400_BAD_REQUEST)

    def test_malformed_challenge_token_rejected(self):
        verify_resp = self.client.post(
            self.verify_url,
            {"token": "not.a.real.token", "backup_code": self.backup_codes[0]},
            format="json",
            **_TENANT_HEADER,
        )
        self.assertEqual(verify_resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_verify_requires_exactly_one_factor(self):
        """Passing both otp and backup_code at once must be rejected."""
        challenge_resp = self._login()
        challenge_token = challenge_resp.data["token"]

        resp = self.client.post(
            self.verify_url,
            {
                "token": challenge_token,
                "otp": "123456",
                "backup_code": self.backup_codes[0],
            },
            format="json",
            **_TENANT_HEADER,
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


# ---------------------------------------------------------------------------
# 4 & 5. Admin login — public endpoint, always 2FA
# ---------------------------------------------------------------------------

class AdminLoginTwoFactorTests(NoThrottleMixin, APITestCase):
    """
    Platform admin (user_type='admin') always authenticates through the
    public-schema endpoint. Login always returns a 2FA challenge.
    """

    def setUp(self):
        super().setUp()
        self.user = _make_admin()
        self.backup_codes = _arm_user_with_backup_codes(self.user)
        self.login_url = "/api/v1/auth/admin/login/"
        self.verify_url = "/api/v1/auth/admin/login/verify/"

    def _login(self):
        # Admin endpoint lives in public_urls — no tenant slug needed.
        return self.client.post(
            self.login_url,
            {"email": self.user.email, "password": "TestAdmin123!"},
            format="json",
        )

    def test_admin_login_always_returns_challenge(self):
        resp = self._login()
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertIn("token", resp.data)
        self.assertNotIn("tokens", resp.data)

    def test_admin_non_admin_user_rejected(self):
        """Regular internal user cannot use the admin login endpoint."""
        internal = _make_internal(email="other.internal@test.local")
        resp = self.client.post(
            self.login_url,
            {"email": internal.email, "password": "TestPass123!"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_admin_full_flow_backup_code(self):
        challenge_resp = self._login()
        self.assertEqual(challenge_resp.status_code, status.HTTP_200_OK)
        challenge_token = challenge_resp.data["token"]

        verify_resp = self.client.post(
            self.verify_url,
            {"token": challenge_token, "backup_code": self.backup_codes[0]},
            format="json",
        )
        self.assertEqual(verify_resp.status_code, status.HTTP_200_OK, verify_resp.data)
        self.assertIn("tokens", verify_resp.data)
        self.assertIn("access", verify_resp.data["tokens"])

    def test_admin_wrong_password_rejected(self):
        resp = self.client.post(
            self.login_url,
            {"email": self.user.email, "password": "BadPassword!"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


# ---------------------------------------------------------------------------
# 6. Logout
# ---------------------------------------------------------------------------

class LogoutTests(NoThrottleMixin, APITestCase):

    def setUp(self):
        super().setUp()
        self.user = _make_applicant(email="logout.user@test.local")
        self.login_url = "/api/v1/auth/login/"
        self.logout_url = "/api/v1/auth/logout/"

    def _login_and_get_tokens(self):
        resp = self.client.post(
            self.login_url,
            {"email": self.user.email, "password": "TestPass123!"},
            format="json",
            **_TENANT_HEADER,
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        return resp.data["tokens"]

    def test_logout_blacklists_refresh_token(self):
        tokens = self._login_and_get_tokens()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

        resp = self.client.post(
            self.logout_url,
            {"refresh": tokens["refresh"]},
            format="json",
            **_TENANT_HEADER,
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("message", resp.data)

    def test_logout_requires_authentication(self):
        resp = self.client.post(
            self.logout_url,
            {"refresh": "some.token.here"},
            format="json",
            **_TENANT_HEADER,
        )
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_with_invalid_token_returns_400(self):
        tokens = self._login_and_get_tokens()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

        resp = self.client.post(
            self.logout_url,
            {"refresh": "not.a.valid.jwt"},
            format="json",
            **_TENANT_HEADER,
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


# ---------------------------------------------------------------------------
# 7. Token refresh
# ---------------------------------------------------------------------------

class TokenRefreshTests(NoThrottleMixin, APITestCase):

    def setUp(self):
        super().setUp()
        self.user = _make_applicant(email="refresh.user@test.local")
        self.login_url = "/api/v1/auth/login/"
        self.refresh_url = "/api/v1/auth/token/refresh/"

    def test_valid_refresh_token_issues_new_access_token(self):
        login_resp = self.client.post(
            self.login_url,
            {"email": self.user.email, "password": "TestPass123!"},
            format="json",
            **_TENANT_HEADER,
        )
        self.assertEqual(login_resp.status_code, status.HTTP_200_OK)
        refresh_token = login_resp.data["tokens"]["refresh"]

        refresh_resp = self.client.post(
            self.refresh_url,
            {"refresh": refresh_token},
            format="json",
            **_TENANT_HEADER,
        )
        self.assertEqual(refresh_resp.status_code, status.HTTP_200_OK, refresh_resp.data)
        self.assertIn("access", refresh_resp.data)

    def test_invalid_refresh_token_rejected(self):
        resp = self.client.post(
            self.refresh_url,
            {"refresh": "garbage.token.value"},
            format="json",
            **_TENANT_HEADER,
        )
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


# ---------------------------------------------------------------------------
# 8. Organisation-admin bootstrap (public endpoint)
# ---------------------------------------------------------------------------

class OrgAdminRegistrationTests(NoThrottleMixin, APITestCase):
    """
    POST /api/v1/auth/register/organization-admin/ creates a new tenant
    organisation + initial admin user. In tests we redirect the schema_context
    call to `test_tenant` because the runner provisions a single shared schema
    (no per-organisation schemas are created during test runs).
    """

    url = "/api/v1/auth/register/organization-admin/"

    def setUp(self):
        super().setUp()
        # Route all schema_context(any_schema) calls to the already-migrated
        # test_tenant schema so TENANT_APP tables exist.
        from django_tenants.utils import schema_context as _real_sc

        @contextmanager
        def _test_sc(schema):
            with _real_sc("test_tenant"):
                yield

        self._sc_patcher = patch("apps.authentication.views.schema_context", _test_sc)
        self._sc_patcher.start()

    def tearDown(self):
        self._sc_patcher.stop()
        super().tearDown()

    def _payload(self, **overrides):
        base = {
            "email": "neworg.admin@example.local",
            "password": "NewOrgPass123!",
            "password_confirm": "NewOrgPass123!",
            "first_name": "New",
            "last_name": "OrgAdmin",
            "organization_name": "Test Ministry of Finance",
            "organization_code": "test-ministry-finance",
            "organization_type": "ministry",
        }
        base.update(overrides)
        return base

    def test_creates_org_and_user(self):
        resp = self.client.post(self.url, self._payload(), format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertIn("organization", resp.data)
        self.assertIn("user", resp.data)
        self.assertEqual(resp.data["organization"]["name"], "Test Ministry of Finance")

    def test_duplicate_org_name_rejected(self):
        self.client.post(self.url, self._payload(), format="json")
        # Second attempt with same org name
        resp = self.client.post(
            self.url,
            self._payload(email="another.admin@example.local"),
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_password_mismatch_rejected(self):
        resp = self.client.post(
            self.url,
            self._payload(password_confirm="DifferentPass123!"),
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_weak_password_rejected(self):
        resp = self.client.post(
            self.url,
            self._payload(password="short", password_confirm="short"),
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


# ---------------------------------------------------------------------------
# 9. Tenant-resolution endpoint
# ---------------------------------------------------------------------------

class ResolveTenantTests(NoThrottleMixin, APITestCase):
    """
    POST /api/v1/auth/resolve-tenant/ — discovers which login flow to use.

    This is a PUBLIC endpoint: called before the frontend knows which tenant
    to route to. It lives only in public_urls.py and must be reached via a
    hostname that doesn't match any tenant domain (so TenantMiddleware falls
    back to the public schema).  We use SERVER_NAME=public.testserver — that
    host has no entry in the domain table, triggering the public-schema fallback.
    """

    url = "/api/v1/auth/resolve-tenant/"
    # Hostname unknown to TenantMiddleware → routes to PUBLIC_SCHEMA_URLCONF
    _public_host = {"SERVER_NAME": "public.testserver"}

    def test_admin_user_resolves_to_public(self):
        admin = _make_admin(email="resolve.admin@test.local")
        resp = self.client.post(
            self.url, {"email": admin.email}, format="json", **self._public_host
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertEqual(resp.data["login_type"], "admin")
        self.assertEqual(resp.data["schema"], "public")

    def test_unknown_email_returns_404(self):
        resp = self.client.post(
            self.url, {"email": "nobody@nowhere.local"}, format="json", **self._public_host
        )
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_missing_email_returns_400(self):
        resp = self.client.post(self.url, {}, format="json", **self._public_host)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
