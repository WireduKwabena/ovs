"""Centralized authorization role and capability helpers."""

from __future__ import annotations

from collections.abc import Sequence

from django.conf import settings


ROLE_REGISTRY_ADMIN = "registry_admin"
ROLE_VETTING_OFFICER = "vetting_officer"
ROLE_COMMITTEE_MEMBER = "committee_member"
ROLE_COMMITTEE_CHAIR = "committee_chair"
ROLE_APPOINTING_AUTHORITY = "appointing_authority"
ROLE_PUBLICATION_OFFICER = "publication_officer"
ROLE_AUDITOR = "auditor"
ROLE_NOMINEE = "nominee"

ROLE_ADMIN = "admin"
ROLE_HR_MANAGER = "hr_manager"
ROLE_APPLICANT = "applicant"

GOVERNMENT_ROLE_GROUPS = frozenset(
    {
        ROLE_REGISTRY_ADMIN,
        ROLE_VETTING_OFFICER,
        ROLE_COMMITTEE_MEMBER,
        ROLE_COMMITTEE_CHAIR,
        ROLE_APPOINTING_AUTHORITY,
        ROLE_PUBLICATION_OFFICER,
        ROLE_AUDITOR,
    }
)

CAPABILITY_REGISTRY_MANAGE = "gams.registry.manage"
CAPABILITY_APPOINTMENT_STAGE = "gams.appointment.stage"
CAPABILITY_APPOINTMENT_DECIDE = "gams.appointment.decide"
CAPABILITY_APPOINTMENT_PUBLISH = "gams.appointment.publish"
CAPABILITY_APPOINTMENT_VIEW_INTERNAL = "gams.appointment.view_internal"
CAPABILITY_AUDIT_VIEW = "gams.audit.view"

ROLE_CAPABILITIES: dict[str, set[str]] = {
    ROLE_ADMIN: {
        CAPABILITY_REGISTRY_MANAGE,
        CAPABILITY_APPOINTMENT_STAGE,
        CAPABILITY_APPOINTMENT_DECIDE,
        CAPABILITY_APPOINTMENT_PUBLISH,
        CAPABILITY_APPOINTMENT_VIEW_INTERNAL,
        CAPABILITY_AUDIT_VIEW,
    },
    ROLE_HR_MANAGER: {
        CAPABILITY_REGISTRY_MANAGE,
        CAPABILITY_APPOINTMENT_STAGE,
        CAPABILITY_APPOINTMENT_DECIDE,
        CAPABILITY_APPOINTMENT_PUBLISH,
        CAPABILITY_APPOINTMENT_VIEW_INTERNAL,
    },
    ROLE_REGISTRY_ADMIN: {
        CAPABILITY_REGISTRY_MANAGE,
        CAPABILITY_APPOINTMENT_STAGE,
        CAPABILITY_APPOINTMENT_VIEW_INTERNAL,
    },
    ROLE_VETTING_OFFICER: {
        CAPABILITY_APPOINTMENT_STAGE,
        CAPABILITY_APPOINTMENT_VIEW_INTERNAL,
    },
    ROLE_COMMITTEE_MEMBER: {
        CAPABILITY_APPOINTMENT_STAGE,
        CAPABILITY_APPOINTMENT_VIEW_INTERNAL,
    },
    ROLE_COMMITTEE_CHAIR: {
        CAPABILITY_APPOINTMENT_STAGE,
        CAPABILITY_APPOINTMENT_VIEW_INTERNAL,
    },
    ROLE_APPOINTING_AUTHORITY: {
        CAPABILITY_APPOINTMENT_STAGE,
        CAPABILITY_APPOINTMENT_DECIDE,
        CAPABILITY_APPOINTMENT_PUBLISH,
        CAPABILITY_APPOINTMENT_VIEW_INTERNAL,
    },
    ROLE_PUBLICATION_OFFICER: {
        CAPABILITY_APPOINTMENT_PUBLISH,
        CAPABILITY_APPOINTMENT_VIEW_INTERNAL,
    },
    ROLE_AUDITOR: {
        CAPABILITY_AUDIT_VIEW,
        CAPABILITY_APPOINTMENT_VIEW_INTERNAL,
    },
    ROLE_NOMINEE: set(),
}

ALL_CAPABILITIES = frozenset(capability for values in ROLE_CAPABILITIES.values() for capability in values)

ROLE_PRECEDENCE: tuple[str, ...] = (
    ROLE_ADMIN,
    ROLE_REGISTRY_ADMIN,
    ROLE_APPOINTING_AUTHORITY,
    ROLE_COMMITTEE_CHAIR,
    ROLE_COMMITTEE_MEMBER,
    ROLE_VETTING_OFFICER,
    ROLE_PUBLICATION_OFFICER,
    ROLE_AUDITOR,
    ROLE_HR_MANAGER,
    ROLE_NOMINEE,
)


def _is_authenticated(user) -> bool:
    return bool(getattr(user, "is_authenticated", False))


def _group_names(user) -> set[str]:
    if not _is_authenticated(user):
        return set()
    groups = getattr(user, "groups", None)
    if groups is None:
        return set()
    return set(groups.values_list("name", flat=True))


def get_group_roles(user) -> set[str]:
    return _group_names(user).intersection(GOVERNMENT_ROLE_GROUPS)


def get_user_roles(user) -> set[str]:
    if not _is_authenticated(user):
        return set()

    roles = get_group_roles(user)

    user_type = str(getattr(user, "user_type", "") or "").strip().lower()
    staff_implies_admin = bool(getattr(settings, "AUTHZ_STAFF_IMPLIES_ADMIN", False))
    if (
        getattr(user, "is_superuser", False)
        or user_type == ROLE_ADMIN
        or (staff_implies_admin and getattr(user, "is_staff", False))
    ):
        roles.add(ROLE_ADMIN)
    elif user_type == ROLE_HR_MANAGER:
        roles.add(ROLE_HR_MANAGER)
    elif user_type == ROLE_APPLICANT:
        roles.add(ROLE_NOMINEE)

    return roles


def has_role(user, role: str) -> bool:
    return role in get_user_roles(user)


def has_any_role(user, roles: Sequence[str]) -> bool:
    user_roles = get_user_roles(user)
    return any(role in user_roles for role in roles)


def get_user_capabilities(user) -> set[str]:
    roles = get_user_roles(user)
    if ROLE_ADMIN in roles:
        return set(ALL_CAPABILITIES)

    capabilities: set[str] = set()
    for role in roles:
        capabilities.update(ROLE_CAPABILITIES.get(role, set()))
    return capabilities


def has_capability(user, capability: str) -> bool:
    return capability in get_user_capabilities(user)


def is_internal_operator(user) -> bool:
    roles = get_user_roles(user)
    return any(role != ROLE_NOMINEE for role in roles)


def requires_two_factor_for_user(user) -> bool:
    return is_internal_operator(user)


def resolve_actor_role(user, *, preferred_roles: Sequence[str] | None = None) -> str:
    user_roles = get_user_roles(user)

    if preferred_roles:
        for role in preferred_roles:
            if role in user_roles:
                return role

    for role in ROLE_PRECEDENCE:
        if role in user_roles:
            return role
    return "user"


__all__ = [
    "ALL_CAPABILITIES",
    "CAPABILITY_APPOINTMENT_DECIDE",
    "CAPABILITY_APPOINTMENT_PUBLISH",
    "CAPABILITY_APPOINTMENT_STAGE",
    "CAPABILITY_APPOINTMENT_VIEW_INTERNAL",
    "CAPABILITY_AUDIT_VIEW",
    "CAPABILITY_REGISTRY_MANAGE",
    "GOVERNMENT_ROLE_GROUPS",
    "ROLE_ADMIN",
    "ROLE_APPLICANT",
    "ROLE_APPOINTING_AUTHORITY",
    "ROLE_AUDITOR",
    "ROLE_COMMITTEE_CHAIR",
    "ROLE_COMMITTEE_MEMBER",
    "ROLE_HR_MANAGER",
    "ROLE_NOMINEE",
    "ROLE_PUBLICATION_OFFICER",
    "ROLE_REGISTRY_ADMIN",
    "ROLE_VETTING_OFFICER",
    "get_group_roles",
    "get_user_capabilities",
    "get_user_roles",
    "has_any_role",
    "has_capability",
    "has_role",
    "is_internal_operator",
    "requires_two_factor_for_user",
    "resolve_actor_role",
]
