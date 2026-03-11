from __future__ import annotations

from rest_framework.permissions import BasePermission

from apps.core.permissions import get_request_active_organization_id, is_government_workflow_operator
from apps.core.security import has_valid_service_token


def is_hr_admin_user(user) -> bool:
    """
    Backward-compatible helper name retained for interview view imports.

    Legacy ``user_type=internal`` alone no longer grants interview admin access.
    """
    return is_government_workflow_operator(user)


class IsHrAdminOrServiceAuthenticated(BasePermission):
    message = "Only authorized internal workflow actors or service-authenticated requests can access this endpoint."

    def has_permission(self, request, view):
        if has_valid_service_token(request):
            request.service_authenticated = True
            return True
        return is_government_workflow_operator(
            getattr(request, "user", None),
            organization_id=get_request_active_organization_id(request),
        )

