"""Permission classes for rubric APIs."""

from rest_framework.permissions import BasePermission

from apps.core.permissions import is_hr_or_admin_user


class IsHRManager(BasePermission):
    """Allow only HR managers/admin users."""

    def has_permission(self, request, view):
        return is_hr_or_admin_user(getattr(request, "user", None))


class CanOverrideScores(BasePermission):
    """Allow only HR managers/admin users to override rubric scores."""

    def has_permission(self, request, view):
        return is_hr_or_admin_user(getattr(request, "user", None))
