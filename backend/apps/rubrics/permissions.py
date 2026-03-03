"""Permission classes for rubric APIs."""

from rest_framework.permissions import BasePermission


def is_hr_or_admin_user(user) -> bool:
    if not user or not getattr(user, "is_authenticated", False):
        return False
    return bool(
        getattr(user, "is_staff", False)
        or getattr(user, "is_superuser", False)
        or getattr(user, "user_type", None) in {"hr_manager", "admin"}
    )


class IsHRManager(BasePermission):
    """Allow only HR managers/admin users."""

    def has_permission(self, request, view):
        return is_hr_or_admin_user(getattr(request, "user", None))


class CanOverrideScores(BasePermission):
    """Allow only HR managers/admin users to override rubric scores."""

    def has_permission(self, request, view):
        return is_hr_or_admin_user(getattr(request, "user", None))
