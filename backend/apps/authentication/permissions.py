from rest_framework.permissions import BasePermission
from rest_framework.exceptions import PermissionDenied
from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.core.permissions import is_admin_user

RECENT_AUTH_TOKEN_CLAIM = "recent_auth_at"
RECENT_AUTH_SESSION_KEY = "auth_last_verified_at"
RECENT_AUTH_REQUIRED_CODE = "RECENT_AUTH_REQUIRED"


def _to_epoch(value) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        normalized = value.strip()
        if not normalized:
            return None
        if normalized.isdigit():
            return int(normalized)
        parsed = parse_datetime(normalized)
        if parsed is None:
            return None
        if timezone.is_naive(parsed):
            parsed = timezone.make_aware(parsed, timezone=timezone.get_current_timezone())
        return int(parsed.timestamp())
    return None


def get_recent_auth_epoch(request) -> int | None:
    auth = getattr(request, "auth", None)
    if auth is not None and hasattr(auth, "get"):
        token_value = auth.get(RECENT_AUTH_TOKEN_CLAIM)
        token_epoch = _to_epoch(token_value)
        if token_epoch is not None:
            return token_epoch

    session = getattr(request, "session", None)
    if session is not None:
        session_epoch = _to_epoch(session.get(RECENT_AUTH_SESSION_KEY))
        if session_epoch is not None:
            return session_epoch

    return None


class RequiresRecentAuth(BasePermission):
    message = "Recent authentication is required for this action."

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return False

        max_age_seconds = int(getattr(settings, "AUTH_RECENT_AUTH_MAX_AGE_SECONDS", 900))
        max_age_seconds = max(60, max_age_seconds)
        recent_auth_epoch = get_recent_auth_epoch(request)
        now_epoch = int(timezone.now().timestamp())

        if recent_auth_epoch is None or (now_epoch - recent_auth_epoch) > max_age_seconds:
            raise PermissionDenied(
                detail={
                    "code": RECENT_AUTH_REQUIRED_CODE,
                    "error": "Recent authentication is required for this action.",
                },
                code=RECENT_AUTH_REQUIRED_CODE,
            )

        return True


class IsAdminUser(BasePermission):
    """
    Allows access only to system-admin users.
    """

    def has_permission(self, request, view):
        return is_admin_user(getattr(request, "user", None))


class IsSuperAdminUser(BasePermission):
    """
    Allows access only to super admin users.
    """
    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        return bool(user and user.is_authenticated and getattr(user, "is_superuser", False))
