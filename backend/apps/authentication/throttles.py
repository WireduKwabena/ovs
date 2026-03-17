"""Rate-limiting throttle classes for authentication endpoints."""

from rest_framework.throttling import AnonRateThrottle


class LoginRateThrottle(AnonRateThrottle):
    """10 login attempts per minute per IP."""
    scope = 'login'


class TwoFactorRateThrottle(AnonRateThrottle):
    """10 2FA verification attempts per minute per IP."""
    scope = 'two_factor'


class PasswordResetRateThrottle(AnonRateThrottle):
    """5 password reset requests per minute per IP."""
    scope = 'password_reset'


class RegistrationRateThrottle(AnonRateThrottle):
    """10 registration attempts per minute per IP."""
    scope = 'registration'
