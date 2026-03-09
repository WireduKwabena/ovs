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


def _committee_roles_from_memberships(user) -> set[str]:
    if not _is_authenticated(user):
        return set()
    try:
        from apps.governance.models import CommitteeMembership
    except Exception:  # pragma: no cover - governance app may be unavailable
        return set()

    membership_roles = set(
        CommitteeMembership.objects.filter(user=user, is_active=True).values_list("committee_role", flat=True)
    )
    if not membership_roles:
        return set()

    resolved_roles: set[str] = set()
    if membership_roles.intersection({"member", "chair", "secretary"}):
        resolved_roles.add(ROLE_COMMITTEE_MEMBER)
    if "chair" in membership_roles:
        resolved_roles.add(ROLE_COMMITTEE_CHAIR)
    return resolved_roles


def get_user_organization_ids(user) -> set[str]:
    if not _is_authenticated(user):
        return set()
    try:
        from apps.governance.models import OrganizationMembership
    except Exception:  # pragma: no cover - governance app may be unavailable
        return set()

    return {
        str(org_id)
        for org_id in OrganizationMembership.objects.filter(user=user, is_active=True).values_list(
            "organization_id", flat=True
        )
    }


def get_user_organization_names(user) -> set[str]:
    names = set()
    if not _is_authenticated(user):
        return names

    legacy_name = str(getattr(user, "organization", "") or "").strip()
    if legacy_name:
        names.add(legacy_name)

    try:
        from apps.governance.models import OrganizationMembership
    except Exception:  # pragma: no cover - governance app may be unavailable
        return names

    names.update(
        name
        for name in OrganizationMembership.objects.filter(user=user, is_active=True).values_list(
            "organization__name", flat=True
        )
        if name
    )
    return names


def get_user_organization_memberships(user) -> list[dict]:
    if not _is_authenticated(user):
        return []
    try:
        from apps.governance.models import OrganizationMembership
    except Exception:  # pragma: no cover - governance app may be unavailable
        return []

    memberships = (
        OrganizationMembership.objects.select_related("organization")
        .filter(user=user, is_active=True, organization__is_active=True)
        .order_by("-is_default", "organization__name", "created_at")
    )
    payload: list[dict] = []
    for membership in memberships:
        organization = membership.organization
        payload.append(
            {
                "id": str(membership.id),
                "organization_id": str(organization.id),
                "organization_code": str(organization.code),
                "organization_name": str(organization.name),
                "organization_type": str(organization.organization_type),
                "title": str(membership.title or ""),
                "membership_role": str(membership.membership_role or ""),
                "is_default": bool(membership.is_default),
                "is_active": bool(membership.is_active),
                "joined_at": membership.joined_at.isoformat() if membership.joined_at else None,
                "left_at": membership.left_at.isoformat() if membership.left_at else None,
            }
        )
    return payload


def get_user_default_organization(user) -> dict | None:
    memberships = get_user_organization_memberships(user)
    if not memberships:
        return None
    default_membership = next((item for item in memberships if item.get("is_default")), None)
    selected = default_membership or memberships[0]
    return {
        "id": selected["organization_id"],
        "code": selected["organization_code"],
        "name": selected["organization_name"],
        "organization_type": selected["organization_type"],
        "membership_id": selected["id"],
        "membership_role": selected["membership_role"],
        "is_default_membership": bool(selected.get("is_default")),
    }


def get_user_organization_by_id(user, organization_id) -> dict | None:
    normalized = str(organization_id or "").strip()
    if not normalized:
        return None
    for membership in get_user_organization_memberships(user):
        if str(membership.get("organization_id")) != normalized:
            continue
        return {
            "id": membership["organization_id"],
            "code": membership["organization_code"],
            "name": membership["organization_name"],
            "organization_type": membership["organization_type"],
            "membership_id": membership["id"],
            "membership_role": membership["membership_role"],
            "is_default_membership": bool(membership.get("is_default")),
        }
    return None


def get_user_committees(user, *, organization_id: str | None = None) -> list[dict]:
    if not _is_authenticated(user):
        return []
    try:
        from apps.governance.models import CommitteeMembership
    except Exception:  # pragma: no cover - governance app may be unavailable
        return []

    memberships = (
        CommitteeMembership.objects.select_related("committee", "committee__organization", "organization_membership")
        .filter(user=user, is_active=True, committee__is_active=True, committee__organization__is_active=True)
        .order_by("committee__organization__name", "committee__name", "created_at")
    )
    if organization_id:
        memberships = memberships.filter(committee__organization_id=organization_id)

    payload: list[dict] = []
    for membership in memberships:
        committee = membership.committee
        organization = committee.organization
        payload.append(
            {
                "id": str(membership.id),
                "committee_id": str(committee.id),
                "committee_code": str(committee.code),
                "committee_name": str(committee.name),
                "committee_type": str(committee.committee_type),
                "organization_id": str(organization.id),
                "organization_code": str(organization.code),
                "organization_name": str(organization.name),
                "committee_role": str(membership.committee_role),
                "can_vote": bool(membership.can_vote),
                "joined_at": membership.joined_at.isoformat() if membership.joined_at else None,
                "left_at": membership.left_at.isoformat() if membership.left_at else None,
            }
        )
    return payload


def get_user_committee_ids(
    user,
    *,
    organization_id: str | None = None,
    include_observer: bool = True,
) -> set[str]:
    if not _is_authenticated(user):
        return set()
    try:
        from apps.governance.models import CommitteeMembership
    except Exception:  # pragma: no cover - governance app may be unavailable
        return set()

    memberships = CommitteeMembership.objects.filter(
        user=user,
        is_active=True,
        committee__is_active=True,
        committee__organization__is_active=True,
    )
    if organization_id:
        memberships = memberships.filter(committee__organization_id=organization_id)
    if not include_observer:
        memberships = memberships.exclude(committee_role="observer")
    return {str(value) for value in memberships.values_list("committee_id", flat=True)}


def get_user_roles(user) -> set[str]:
    if not _is_authenticated(user):
        return set()

    roles = get_group_roles(user)
    roles.update(_committee_roles_from_memberships(user))

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
    "get_user_committees",
    "get_user_default_organization",
    "get_user_organization_by_id",
    "get_user_organization_ids",
    "get_user_organization_memberships",
    "get_user_organization_names",
    "get_user_capabilities",
    "get_user_committee_ids",
    "get_user_roles",
    "has_any_role",
    "has_capability",
    "has_role",
    "is_internal_operator",
    "requires_two_factor_for_user",
    "resolve_actor_role",
]
