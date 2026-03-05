"""Shared role-based permission helpers."""

from __future__ import annotations

from rest_framework.permissions import BasePermission


def is_hr_or_admin_user(user) -> bool:
    return bool(
        getattr(user, "is_authenticated", False)
        and (
            getattr(user, "is_staff", False)
            or getattr(user, "is_superuser", False)
            or getattr(user, "user_type", None) in {"admin", "hr_manager"}
        )
    )


def is_admin_user(user) -> bool:
    return bool(
        getattr(user, "is_authenticated", False)
        and (
            getattr(user, "is_staff", False)
            or getattr(user, "is_superuser", False)
            or getattr(user, "user_type", None) == "admin"
        )
    )


class IsHRManagerOrAdmin(BasePermission):
    message = "Only HR managers/admin users can access this resource."

    def has_permission(self, request, view):
        return is_hr_or_admin_user(getattr(request, "user", None))

