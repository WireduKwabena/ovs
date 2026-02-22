"""Compatibility layer for legacy auth_actions imports.

Legacy modules still import ``apps.auth_actions`` for user models and admin
permissions. This module maps those references to the current authentication app.
"""

from rest_framework.permissions import BasePermission

from apps.authentication.models import User


class IsAdminUser(BasePermission):
    """Allow access to authenticated admin/staff users."""

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        if not user or not getattr(user, "is_authenticated", False):
            return False
        return bool(
            getattr(user, "is_staff", False)
            or getattr(user, "is_superuser", False)
            or getattr(user, "user_type", None) in {"admin", "hr_manager"}
        )


# Backward-compatible alias. Current project uses a unified User model.
AdminUser = User

__all__ = ["User", "AdminUser", "IsAdminUser"]
