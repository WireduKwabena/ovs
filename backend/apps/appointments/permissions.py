from rest_framework.permissions import BasePermission

from apps.core.authz import (
    ROLE_APPOINTING_AUTHORITY,
    ROLE_COMMITTEE_CHAIR,
    ROLE_COMMITTEE_MEMBER,
    ROLE_PUBLICATION_OFFICER,
    ROLE_REGISTRY_ADMIN,
    ROLE_VETTING_OFFICER,
    has_any_role,
)
from apps.core.permissions import is_admin_user


class IsStageActorOrAdmin(BasePermission):
    message = "Only authorized stage actors or admins can perform this action."

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        return bool(
            is_admin_user(user)
            or has_any_role(
                user,
                (
                    ROLE_VETTING_OFFICER,
                    ROLE_COMMITTEE_MEMBER,
                    ROLE_COMMITTEE_CHAIR,
                    ROLE_APPOINTING_AUTHORITY,
                    ROLE_REGISTRY_ADMIN,
                ),
            )
        )


class IsCommitteeMemberOrAdmin(BasePermission):
    message = "Only committee actors or admins can perform this action."

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        return bool(
            is_admin_user(user)
            or has_any_role(user, (ROLE_COMMITTEE_MEMBER, ROLE_COMMITTEE_CHAIR))
        )


class IsAppointingAuthorityOrAdmin(BasePermission):
    message = "Only appointing authority or admins can perform this action."

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        return bool(is_admin_user(user) or has_any_role(user, (ROLE_APPOINTING_AUTHORITY,)))


class IsPublicationOfficerOrAuthorityOrAdmin(BasePermission):
    message = "Only publication officers, appointing authority, or admins can perform this action."

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        return bool(
            is_admin_user(user)
            or has_any_role(user, (ROLE_PUBLICATION_OFFICER, ROLE_APPOINTING_AUTHORITY))
        )
