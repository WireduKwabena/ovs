"""Tests for authentication rate-limiting throttles."""

from unittest.mock import MagicMock

from django.test import SimpleTestCase, override_settings
from rest_framework.test import APITestCase, APIClient
from rest_framework.throttling import AnonRateThrottle

from apps.authentication.throttles import (
    LoginRateThrottle,
    PasswordResetRateThrottle,
    RegistrationRateThrottle,
    TwoFactorRateThrottle,
)


class ThrottleClassScopeTests(SimpleTestCase):
    """Verify each throttle class declares the correct scope."""

    def test_login_throttle_scope(self):
        self.assertEqual(LoginRateThrottle.scope, "login")

    def test_two_factor_throttle_scope(self):
        self.assertEqual(TwoFactorRateThrottle.scope, "two_factor")

    def test_password_reset_throttle_scope(self):
        self.assertEqual(PasswordResetRateThrottle.scope, "password_reset")

    def test_registration_throttle_scope(self):
        self.assertEqual(RegistrationRateThrottle.scope, "registration")

    def test_all_throttles_subclass_anon_rate_throttle(self):
        for cls in (LoginRateThrottle, TwoFactorRateThrottle, PasswordResetRateThrottle, RegistrationRateThrottle):
            self.assertTrue(
                issubclass(cls, AnonRateThrottle),
                f"{cls.__name__} must subclass AnonRateThrottle",
            )


class ViewThrottleClassAssignmentTests(SimpleTestCase):
    """Verify the correct throttle classes are wired to each view."""

    def _get_view_throttle_classes(self, view_func):
        """Extract throttle_classes from a DRF function-based view's WrappedAPIView."""
        cls = getattr(view_func, "cls", None)
        if cls is not None:
            return getattr(cls, "throttle_classes", [])
        return getattr(view_func, "throttle_classes", [])

    def test_login_view_has_login_throttle(self):
        from apps.authentication.views import login_view
        throttles = self._get_view_throttle_classes(login_view)
        self.assertIn(LoginRateThrottle, throttles)

    def test_admin_login_view_has_login_throttle(self):
        from apps.authentication.views import admin_login_view
        throttles = self._get_view_throttle_classes(admin_login_view)
        self.assertIn(LoginRateThrottle, throttles)

    def test_two_factor_view_has_2fa_throttle(self):
        from apps.authentication.views import two_factor_verification_view
        throttles = self._get_view_throttle_classes(two_factor_verification_view)
        self.assertIn(TwoFactorRateThrottle, throttles)

    def test_password_reset_view_has_password_reset_throttle(self):
        from apps.authentication.views import password_reset_request_view
        throttles = self._get_view_throttle_classes(password_reset_request_view)
        self.assertIn(PasswordResetRateThrottle, throttles)

    def test_register_view_has_registration_throttle(self):
        from apps.authentication.views import RegisterView
        self.assertIn(RegistrationRateThrottle, RegisterView.throttle_classes)

    def test_org_admin_register_view_has_registration_throttle(self):
        from apps.authentication.views import OrganizationAdminRegisterView
        self.assertIn(RegistrationRateThrottle, OrganizationAdminRegisterView.throttle_classes)


class ThrottleAllowRequestUnitTests(SimpleTestCase):
    """
    Direct unit tests for throttle allow/deny logic.

    Uses DRF's cache-backed sliding window by wiring up a fresh locmem cache
    and a mock request, bypassing the full HTTP stack which has DRF settings
    caching issues in test environments.
    """

    def _make_request(self, ip="1.2.3.4"):
        request = MagicMock()
        request.user = MagicMock()
        request.user.is_authenticated = False
        request.META = {"REMOTE_ADDR": ip}
        request.auth = None
        return request

    def _make_view(self):
        return MagicMock()

    def _make_throttle(self, throttle_cls, rate):
        """Create a throttle instance with the rate set directly to bypass class-level caching."""
        t = throttle_cls()
        # Override rate and derived values so the instance uses the test rate,
        # not whatever default is configured in settings.
        t.rate = rate
        t.num_requests, t.duration = t.parse_rate(rate)
        return t

    @override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "login-allow"}})
    def test_login_throttle_allows_within_rate(self):
        from django.core.cache import cache
        cache.clear()
        request = self._make_request()
        view = self._make_view()
        # 3 requests within the "3/minute" rate should all be allowed
        for _ in range(3):
            throttle = self._make_throttle(LoginRateThrottle, "3/minute")
            self.assertTrue(throttle.allow_request(request, view))

    @override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "login-deny"}})
    def test_login_throttle_denies_after_rate_exceeded(self):
        from django.core.cache import cache
        cache.clear()
        request = self._make_request()
        view = self._make_view()
        for _ in range(3):
            self._make_throttle(LoginRateThrottle, "3/minute").allow_request(request, view)
        # 4th call exceeds the limit
        self.assertFalse(self._make_throttle(LoginRateThrottle, "3/minute").allow_request(request, view))

    @override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "2fa-deny"}})
    def test_two_factor_throttle_denies_after_rate_exceeded(self):
        from django.core.cache import cache
        cache.clear()
        request = self._make_request()
        view = self._make_view()
        for _ in range(2):
            self._make_throttle(TwoFactorRateThrottle, "2/minute").allow_request(request, view)
        self.assertFalse(self._make_throttle(TwoFactorRateThrottle, "2/minute").allow_request(request, view))

    @override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "per-ip"}})
    def test_throttle_tracks_per_ip(self):
        from django.core.cache import cache
        cache.clear()
        view = self._make_view()
        # Exhaust limit for ip1
        req_ip1 = self._make_request(ip="10.0.0.1")
        for _ in range(5):
            self._make_throttle(LoginRateThrottle, "5/minute").allow_request(req_ip1, view)
        # ip2 should still be allowed
        req_ip2 = self._make_request(ip="10.0.0.2")
        self.assertTrue(self._make_throttle(LoginRateThrottle, "5/minute").allow_request(req_ip2, view))

    def test_parse_rate_returns_correct_values(self):
        """Verify rate strings parse to expected (num_requests, seconds) tuples."""
        throttle = LoginRateThrottle()
        num, duration = throttle.parse_rate("10/minute")
        self.assertEqual(num, 10)
        self.assertEqual(duration, 60)

        num, duration = throttle.parse_rate("5/hour")
        self.assertEqual(num, 5)
        self.assertEqual(duration, 3600)
