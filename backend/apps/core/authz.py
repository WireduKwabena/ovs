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
ROLE_INTERNAL = "internal"
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
    # Legacy ``user_type=internal`` no longer implies governance authority.
    # Sensitive GAMS actions must be granted through explicit group roles or
    # organization membership policy checks.
    ROLE_INTERNAL: set(),
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
    ROLE_INTERNAL,
    ROLE_NOMINEE,
)

DEFAULT_ORG_ADMIN_MEMBERSHIP_ROLES = frozenset(
    {
        "registry_admin",
        "org_admin",
        "organization_admin",
        "system_admin",
    }
)

# Membership-role -> authz-role mapping.
# This keeps ``user_type`` backward-compatible while deriving real operational
# authority from organization context.
ORGANIZATION_MEMBERSHIP_ROLE_TO_AUTHZ_ROLES: dict[str, set[str]] = {
    "registry_admin": {ROLE_REGISTRY_ADMIN},
    "org_admin": {ROLE_REGISTRY_ADMIN},
    "organization_admin": {ROLE_REGISTRY_ADMIN},
    "system_admin": {ROLE_REGISTRY_ADMIN},
    "vetting_officer": {ROLE_VETTING_OFFICER},
    "appointing_authority": {ROLE_APPOINTING_AUTHORITY},
    "publication_officer": {ROLE_PUBLICATION_OFFICER},
    "auditor": {ROLE_AUDITOR},
    "nominee": {ROLE_NOMINEE},
}


def _is_authenticated(user) -> bool:
    return bool(getattr(user, "is_authenticated", False))


def _group_names(user) -> set[str]:
    if not _is_authenticated(user):
        return set()
    groups = getattr(user, "groups", None)
    if groups is None:
        return set()
    return set(groups.values_list("name", flat=True))


_AUTHZ_ORG_MEMBERSHIPS_CACHE_ATTR = "_authz_organization_memberships_cache"
_AUTHZ_COMMITTEES_CACHE_ATTR = "_authz_committees_cache"


def _schema_exists(schema_name: str) -> bool:
    """Return True if *schema_name* exists in the PostgreSQL catalog."""
    try:
        from django.db import connection
        with connection.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM pg_catalog.pg_namespace WHERE nspname = %s",
                [schema_name],
            )
            return cur.fetchone() is not None
    except Exception:
        return False


def _list_active_tenant_organizations():
    try:
        from django.db import connection
        from django_tenants.utils import get_public_schema_name, schema_context
        from apps.tenants.models import Organization
    except Exception:  # pragma: no cover - tenancy app may be unavailable
        return []

    public_schema = get_public_schema_name()

    def _query():
        return list(
            Organization.objects.filter(is_active=True)
            .exclude(schema_name=public_schema)
            .order_by("name")
        )

    current_schema = str(getattr(connection, "schema_name", public_schema) or public_schema)
    if current_schema == public_schema:
        try:
            return _query()
        except Exception:
            return []

    try:
        with schema_context(public_schema):
            return _query()
    except Exception:
        try:
            return _query()
        except Exception:
            return []


def _load_active_organization_memberships_for_user(user_id, organization) -> list[dict]:
    from django_tenants.utils import schema_context
    from apps.governance.models import OrganizationMembership

    with schema_context(organization.schema_name):
        memberships = (
            OrganizationMembership.objects.filter(user_id=user_id, is_active=True)
            .order_by("-is_default", "created_at")
        )
        return [
            {
                "id": str(membership.id),
                "organization_id": str(organization.id),
                "organization_code": str(organization.code or ""),
                "organization_name": str(organization.name or ""),
                "organization_type": str(getattr(organization, "organization_type", "") or ""),
                "tier": str(getattr(organization, "tier", "") or ""),
                "title": str(membership.title or ""),
                "membership_role": str(membership.membership_role or ""),
                "is_default": bool(membership.is_default),
                "is_active": bool(membership.is_active),
                "joined_at": membership.joined_at.isoformat() if membership.joined_at else None,
                "left_at": membership.left_at.isoformat() if membership.left_at else None,
            }
            for membership in memberships
        ]


def _load_active_committee_memberships_for_user(user_id, organization) -> list[dict]:
    from django_tenants.utils import schema_context
    from apps.governance.models import CommitteeMembership

    with schema_context(organization.schema_name):
        memberships = (
            CommitteeMembership.objects.select_related("committee")
            .filter(user_id=user_id, is_active=True, committee__is_active=True)
            .order_by("committee__name", "created_at")
        )
        return [
            {
                "id": str(membership.id),
                "committee_id": str(membership.committee_id),
                "committee_code": str(membership.committee.code),
                "committee_name": str(membership.committee.name),
                "committee_type": str(membership.committee.committee_type),
                "organization_id": str(organization.id),
                "organization_code": str(organization.code or ""),
                "organization_name": str(organization.name or ""),
                "committee_role": str(membership.committee_role),
                "can_vote": bool(membership.can_vote),
                "joined_at": membership.joined_at.isoformat() if membership.joined_at else None,
                "left_at": membership.left_at.isoformat() if membership.left_at else None,
            }
            for membership in memberships
        ]


def _load_current_schema_organization_memberships(user) -> list[dict]:
    try:
        from django.db import connection
        from apps.governance.models import OrganizationMembership
    except Exception:  # pragma: no cover - governance app may be unavailable
        return []

    if getattr(connection, "schema_name", "public") == "public":
        return []

    memberships = (
        OrganizationMembership.objects.filter(user=user, is_active=True)
        .order_by("-is_default", "created_at")
    )

    try:
        tenant = connection.tenant
        tenant_id = str(tenant.id)
        tenant_code = str(tenant.code or "")
        tenant_name = str(tenant.name or "")
        tenant_org_type = str(getattr(tenant, "organization_type", "") or "")
        tenant_tier = str(getattr(tenant, "tier", "") or "")
    except Exception:
        tenant_id = ""
        tenant_code = ""
        tenant_name = ""
        tenant_org_type = ""
        tenant_tier = ""

    return [
        {
            "id": str(membership.id),
            "organization_id": tenant_id,
            "organization_code": tenant_code,
            "organization_name": tenant_name,
            "organization_type": tenant_org_type,
            "tier": tenant_tier,
            "title": str(membership.title or ""),
            "membership_role": str(membership.membership_role or ""),
            "is_default": bool(membership.is_default),
            "is_active": bool(membership.is_active),
            "joined_at": membership.joined_at.isoformat() if membership.joined_at else None,
            "left_at": membership.left_at.isoformat() if membership.left_at else None,
        }
        for membership in memberships
    ]


def _load_current_schema_committee_memberships(user) -> list[dict]:
    try:
        from django.db import connection
        from apps.governance.models import CommitteeMembership
    except Exception:  # pragma: no cover - governance app may be unavailable
        return []

    if getattr(connection, "schema_name", "public") == "public":
        return []

    memberships = (
        CommitteeMembership.objects.select_related("committee")
        .filter(user=user, is_active=True, committee__is_active=True)
        .order_by("committee__name", "created_at")
    )

    try:
        tenant = connection.tenant
        tenant_org_id = str(tenant.id)
        tenant_code = str(tenant.code or "")
        tenant_name = str(tenant.name or "")
    except Exception:
        tenant_org_id = ""
        tenant_code = ""
        tenant_name = ""

    return [
        {
            "id": str(membership.id),
            "committee_id": str(membership.committee_id),
            "committee_code": str(membership.committee.code),
            "committee_name": str(membership.committee.name),
            "committee_type": str(membership.committee.committee_type),
            "organization_id": tenant_org_id,
            "organization_code": tenant_code,
            "organization_name": tenant_name,
            "committee_role": str(membership.committee_role),
            "can_vote": bool(membership.can_vote),
            "joined_at": membership.joined_at.isoformat() if membership.joined_at else None,
            "left_at": membership.left_at.isoformat() if membership.left_at else None,
        }
        for membership in memberships
    ]


def _get_cached_user_authz_payload(user, attr_name: str, loader):
    cached = getattr(user, attr_name, None)
    if isinstance(cached, list):
        return cached
    payload = loader()
    setattr(user, attr_name, payload)
    return payload


def _get_user_organization_membership_records(user) -> list[dict]:
    if not _is_authenticated(user):
        return []

    def _load():
        records: list[dict] = []
        seen: set[tuple[str, str]] = set()
        for organization in _list_active_tenant_organizations():
            if not _schema_exists(organization.schema_name):
                continue
            try:
                organization_records = _load_active_organization_memberships_for_user(
                    user.id,
                    organization,
                )
            except Exception:
                continue
            for record in organization_records:
                cache_key = (
                    str(record.get("organization_id") or ""),
                    str(record.get("id") or ""),
                )
                if cache_key in seen:
                    continue
                seen.add(cache_key)
                records.append(record)
        if not records:
            records = _load_current_schema_organization_memberships(user)
        records.sort(
            key=lambda item: (
                not bool(item.get("is_default")),
                str(item.get("organization_name") or "").lower(),
                str(item.get("title") or "").lower(),
                str(item.get("id") or ""),
            )
        )
        return records

    return _get_cached_user_authz_payload(user, _AUTHZ_ORG_MEMBERSHIPS_CACHE_ATTR, _load)


def _get_user_committee_records(user) -> list[dict]:
    if not _is_authenticated(user):
        return []

    def _load():
        records: list[dict] = []
        seen: set[tuple[str, str]] = set()
        for organization in _list_active_tenant_organizations():
            if not _schema_exists(organization.schema_name):
                continue
            try:
                organization_records = _load_active_committee_memberships_for_user(
                    user.id,
                    organization,
                )
            except Exception:
                continue
            for record in organization_records:
                cache_key = (
                    str(record.get("organization_id") or ""),
                    str(record.get("id") or ""),
                )
                if cache_key in seen:
                    continue
                seen.add(cache_key)
                records.append(record)
        if not records:
            records = _load_current_schema_committee_memberships(user)
        records.sort(
            key=lambda item: (
                str(item.get("organization_name") or "").lower(),
                str(item.get("committee_name") or "").lower(),
                str(item.get("id") or ""),
            )
        )
        return records

    return _get_cached_user_authz_payload(user, _AUTHZ_COMMITTEES_CACHE_ATTR, _load)


def get_group_roles(user) -> set[str]:
    return _group_names(user).intersection(GOVERNMENT_ROLE_GROUPS)


def _committee_roles_from_memberships(user) -> set[str]:
    if not _is_authenticated(user):
        return set()
    membership_roles = {
        str(record.get("committee_role") or "").strip().lower()
        for record in _get_user_committee_records(user)
        if str(record.get("committee_role") or "").strip()
    }
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
    return {
        str(record.get("organization_id") or "").strip()
        for record in _get_user_organization_membership_records(user)
        if str(record.get("organization_id") or "").strip()
    }


def get_user_organization_names(user) -> set[str]:
    names = set()
    if not _is_authenticated(user):
        return names

    legacy_name = str(getattr(user, "organization", "") or "").strip()
    if legacy_name:
        names.add(legacy_name)
    for membership in _get_user_organization_membership_records(user):
        organization_name = str(membership.get("organization_name") or "").strip()
        if organization_name:
            names.add(organization_name)
    return names


def get_user_organization_memberships(user) -> list[dict]:
    return [dict(record) for record in _get_user_organization_membership_records(user)]


def get_user_default_organization(user) -> dict | None:
    memberships = _get_user_organization_membership_records(user)
    if not memberships:
        return None
    legacy_name = str(getattr(user, "organization", "") or "").strip().lower()
    default_memberships = [item for item in memberships if item.get("is_default")]
    selected = None
    if legacy_name:
        selected = next(
            (
                item
                for item in default_memberships
                if str(item.get("organization_name") or "").strip().lower() == legacy_name
            ),
            None,
        )
        if selected is None:
            selected = next(
                (
                    item
                    for item in memberships
                    if str(item.get("organization_name") or "").strip().lower() == legacy_name
                ),
                None,
            )
    if selected is None:
        selected = default_memberships[0] if default_memberships else memberships[0]
    return {
        "id": selected["organization_id"],
        "code": selected["organization_code"],
        "name": selected["organization_name"],
        "organization_type": selected["organization_type"],
        "tier": selected.get("tier", ""),
        "membership_id": selected["id"],
        "membership_role": selected["membership_role"],
        "is_default_membership": bool(selected.get("is_default")),
    }


def get_user_organization_by_id(user, organization_id) -> dict | None:
    normalized = str(organization_id or "").strip()
    if not normalized:
        return None
    for membership in _get_user_organization_membership_records(user):
        if str(membership.get("organization_id")) != normalized:
            continue
        return {
            "id": membership["organization_id"],
            "code": membership["organization_code"],
            "name": membership["organization_name"],
            "organization_type": membership["organization_type"],
            "tier": membership.get("tier", ""),
            "membership_id": membership["id"],
            "membership_role": membership["membership_role"],
            "is_default_membership": bool(membership.get("is_default")),
        }
    return None


def normalize_membership_role_key(value) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


def has_organization_membership_role(
    user,
    *,
    organization_id=None,
    allowed_roles=None,
) -> bool:
    if not _is_authenticated(user):
        return False

    normalized_allowed_roles = {
        normalize_membership_role_key(role_value)
        for role_value in (allowed_roles or DEFAULT_ORG_ADMIN_MEMBERSHIP_ROLES)
        if normalize_membership_role_key(role_value)
    }
    if not normalized_allowed_roles:
        return False

    normalized_org_id = str(organization_id or "").strip()
    for membership in get_user_organization_memberships(user):
        membership_org_id = str(membership.get("organization_id") or "").strip()
        if normalized_org_id and membership_org_id != normalized_org_id:
            continue
        membership_role = normalize_membership_role_key(membership.get("membership_role"))
        if membership_role in normalized_allowed_roles:
            return True
    return False


def _organization_roles_from_memberships(user) -> set[str]:
    if not _is_authenticated(user):
        return set()

    resolved_roles: set[str] = set()
    for membership in get_user_organization_memberships(user):
        role_key = normalize_membership_role_key(membership.get("membership_role"))
        if not role_key:
            continue
        resolved_roles.update(ORGANIZATION_MEMBERSHIP_ROLE_TO_AUTHZ_ROLES.get(role_key, set()))
    return resolved_roles


def get_user_committees(user, *, organization_id: str | None = None) -> list[dict]:
    normalized_org_id = str(organization_id or "").strip()
    committees = _get_user_committee_records(user)
    if normalized_org_id:
        committees = [
            record
            for record in committees
            if str(record.get("organization_id") or "").strip() == normalized_org_id
        ]
    return [dict(record) for record in committees]


def get_user_committee_ids(
    user,
    *,
    organization_id: str | None = None,
    include_observer: bool = True,
) -> set[str]:
    committees = get_user_committees(user, organization_id=organization_id)
    if not include_observer:
        committees = [
            record
            for record in committees
            if str(record.get("committee_role") or "").strip().lower() != "observer"
        ]
    return {
        str(record.get("committee_id") or "").strip()
        for record in committees
        if str(record.get("committee_id") or "").strip()
    }


def get_user_roles(user) -> set[str]:
    if not _is_authenticated(user):
        return set()

    roles = get_group_roles(user)
    roles.update(_committee_roles_from_memberships(user))
    roles.update(_organization_roles_from_memberships(user))

    user_type = str(getattr(user, "user_type", "") or "").strip().lower()
    staff_implies_admin = bool(getattr(settings, "AUTHZ_STAFF_IMPLIES_ADMIN", False))
    if (
        getattr(user, "is_superuser", False)
        or user_type == ROLE_ADMIN
        or (staff_implies_admin and getattr(user, "is_staff", False))
    ):
        roles.add(ROLE_ADMIN)
    elif user_type == ROLE_INTERNAL:
        roles.add(ROLE_INTERNAL)
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
    "ROLE_INTERNAL",
    "ROLE_NOMINEE",
    "ROLE_PUBLICATION_OFFICER",
    "ROLE_REGISTRY_ADMIN",
    "ROLE_VETTING_OFFICER",
    "DEFAULT_ORG_ADMIN_MEMBERSHIP_ROLES",
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
    "has_organization_membership_role",
    "has_role",
    "is_internal_operator",
    "normalize_membership_role_key",
    "requires_two_factor_for_user",
    "resolve_actor_role",
]
