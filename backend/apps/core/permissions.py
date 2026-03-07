"""Shared role-based permission helpers."""

from __future__ import annotations

from rest_framework.permissions import BasePermission

from .authz import (
    CAPABILITY_APPOINTMENT_DECIDE,
    CAPABILITY_APPOINTMENT_PUBLISH,
    CAPABILITY_APPOINTMENT_STAGE,
    CAPABILITY_APPOINTMENT_VIEW_INTERNAL,
    CAPABILITY_AUDIT_VIEW,
    CAPABILITY_REGISTRY_MANAGE,
    ROLE_ADMIN,
    get_user_roles,
    has_capability,
    has_role,
    is_internal_operator,
)


def is_hr_or_admin_user(user) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    if has_role(user, ROLE_ADMIN):
        return True
    return getattr(user, "user_type", None) == "hr_manager"


def is_admin_user(user) -> bool:
    return bool(getattr(user, "is_authenticated", False) and has_role(user, ROLE_ADMIN))


class IsHRManagerOrAdmin(BasePermission):
    message = "Only HR managers/admin users can access this resource."

    def has_permission(self, request, view):
        return is_hr_or_admin_user(getattr(request, "user", None))


def is_government_workflow_operator(user) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    if is_hr_or_admin_user(user):
        return True
    if not is_internal_operator(user):
        return False
    return any(
        has_capability(user, capability)
        for capability in (
            CAPABILITY_REGISTRY_MANAGE,
            CAPABILITY_APPOINTMENT_STAGE,
            CAPABILITY_APPOINTMENT_DECIDE,
            CAPABILITY_APPOINTMENT_PUBLISH,
            CAPABILITY_APPOINTMENT_VIEW_INTERNAL,
        )
    )


class IsGovernmentWorkflowOperator(BasePermission):
    message = "Only internal government workflow actors can access this resource."

    def has_permission(self, request, view):
        return is_government_workflow_operator(getattr(request, "user", None))


class IsRegistryOperatorOrAdmin(BasePermission):
    message = "Only registry operators or admins can access this resource."

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        return bool(is_hr_or_admin_user(user) or has_capability(user, CAPABILITY_REGISTRY_MANAGE))


class IsAuditReaderOrAdmin(BasePermission):
    message = "Only auditors or admins can access this resource."

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        return bool(is_admin_user(user) or has_capability(user, CAPABILITY_AUDIT_VIEW))


class CanViewInternalAppointmentData(BasePermission):
    message = "Only internal operators can view internal appointment details."

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        return bool(is_admin_user(user) or has_capability(user, CAPABILITY_APPOINTMENT_VIEW_INTERNAL))


def user_roles(user) -> list[str]:
    """Expose sorted role keys for serializers/debug views."""
    return sorted(get_user_roles(user))
