from rest_framework.permissions import BasePermission

from apps.core.permissions import is_admin_user


def _has_group(user, name: str) -> bool:
    return bool(getattr(user, "is_authenticated", False) and user.groups.filter(name=name).exists())


class IsStageActorOrAdmin(BasePermission):
    message = "Only stage actors (vetting/committee/authority/registry) or admins can perform this action."

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        if is_admin_user(user):
            return True
        return any(
            _has_group(user, group_name)
            for group_name in ("vetting_officer", "committee_member", "appointing_authority", "registry_admin")
        )


class IsCommitteeMemberOrAdmin(BasePermission):
    message = "Only committee members or admins can perform this action."

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        return bool(is_admin_user(user) or _has_group(user, "committee_member"))


class IsAppointingAuthorityOrAdmin(BasePermission):
    message = "Only appointing authority or admins can perform this action."

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        return bool(is_admin_user(user) or _has_group(user, "appointing_authority"))
