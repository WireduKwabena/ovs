"""Permission classes for rubric APIs."""

from rest_framework.permissions import BasePermission

from apps.core.authz import (
    CAPABILITY_APPOINTMENT_DECIDE,
    CAPABILITY_APPOINTMENT_STAGE,
    CAPABILITY_REGISTRY_MANAGE,
    ROLE_APPOINTING_AUTHORITY,
    ROLE_COMMITTEE_CHAIR,
    ROLE_COMMITTEE_MEMBER,
    ROLE_REGISTRY_ADMIN,
    ROLE_VETTING_OFFICER,
    has_any_role,
    has_capability,
)
from apps.core.permissions import get_request_active_organization_id, is_platform_admin_user
from apps.core.policies.registry_policy import can_manage_registry_governance


class IsInternalRubricOperator(BasePermission):
    """
    Allow rubric operations for explicit governance actors only.

    Legacy ``user_type=internal`` alone is intentionally insufficient.
    """

    message = "Only authorized internal governance actors can access rubric operations."

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        if not bool(getattr(user, "is_authenticated", False)):
            return False
        if is_platform_admin_user(user):
            return True

        active_org_id = get_request_active_organization_id(request)
        if can_manage_registry_governance(
            user,
            organization_id=active_org_id,
            allow_membershipless_fallback=False,
        ):
            return True

        if any(
            has_capability(user, capability)
            for capability in (
                CAPABILITY_REGISTRY_MANAGE,
                CAPABILITY_APPOINTMENT_STAGE,
                CAPABILITY_APPOINTMENT_DECIDE,
            )
        ):
            return True

        return has_any_role(
            user,
            (
                ROLE_REGISTRY_ADMIN,
                ROLE_VETTING_OFFICER,
                ROLE_COMMITTEE_MEMBER,
                ROLE_COMMITTEE_CHAIR,
                ROLE_APPOINTING_AUTHORITY,
            ),
        )


class CanOverrideScores(BasePermission):
    """Allow only authorized rubric actors to override rubric scores."""

    message = "Only authorized internal governance actors can override rubric scores."

    def has_permission(self, request, view):
        return IsInternalRubricOperator().has_permission(request, view)

