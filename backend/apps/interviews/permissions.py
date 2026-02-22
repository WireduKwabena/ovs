from __future__ import annotations

from rest_framework.permissions import BasePermission

from apps.core.security import has_valid_service_token


def is_hr_admin_user(user) -> bool:
    return bool(
        getattr(user, "is_authenticated", False)
        and (
            getattr(user, "is_staff", False)
            or getattr(user, "is_superuser", False)
            or getattr(user, "user_type", None) in {"admin", "hr_manager"}
        )
    )


class IsHrAdminOrServiceAuthenticated(BasePermission):
    message = "Only HR/admin or service-authenticated requests can access this endpoint."

    def has_permission(self, request, view):
        if has_valid_service_token(request):
            request.service_authenticated = True
            return True
        return is_hr_admin_user(getattr(request, "user", None))
