from rest_framework.throttling import AnonRateThrottle


class TwoFactorRateThrottle(AnonRateThrottle):
    """10 2FA verification attempts per minute per IP."""
    scope = 'two_factor'
