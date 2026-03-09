"""Shared role-based permission helpers."""

from __future__ import annotations

from django.db.models import Q
from rest_framework.permissions import BasePermission

from .authz import (
    get_user_organization_ids,
    CAPABILITY_APPOINTMENT_DECIDE,
    CAPABILITY_APPOINTMENT_PUBLISH,
    CAPABILITY_APPOINTMENT_STAGE,
    CAPABILITY_APPOINTMENT_VIEW_INTERNAL,
    CAPABILITY_AUDIT_VIEW,
    CAPABILITY_REGISTRY_MANAGE,
    ROLE_ADMIN,
    get_user_default_organization,
    get_user_organization_by_id,
    get_user_organization_memberships,
    get_user_organization_names,
    get_user_roles,
    has_capability,
    has_role,
    is_internal_operator,
)

ACTIVE_ORGANIZATION_SESSION_KEY = "auth_active_organization_id"
ACTIVE_ORGANIZATION_HEADER_KEY = "HTTP_X_ACTIVE_ORGANIZATION_ID"
ACTIVE_ORGANIZATION_QUERY_PARAM = "active_organization_id"


def is_hr_or_admin_user(user) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    if has_role(user, ROLE_ADMIN):
        return True
    return getattr(user, "user_type", None) == "hr_manager"


def is_admin_user(user) -> bool:
    return bool(getattr(user, "is_authenticated", False) and has_role(user, ROLE_ADMIN))


def is_platform_admin_user(user) -> bool:
    """
    Strict admin bypass used for organization scoping.

    Keeps recovery path for true platform operators regardless of org membership.
    """
    if not getattr(user, "is_authenticated", False):
        return False
    return bool(getattr(user, "is_superuser", False) or getattr(user, "user_type", None) == "admin")


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


def user_organization_scope(user) -> list[str]:
    """
    Governance-first org scope with legacy ``user.organization`` fallback.

    This helper is additive and intentionally not enforced globally in Phase 1.
    """
    return sorted(get_user_organization_names(user))


def resolve_active_organization_context(request) -> dict:
    """
    Resolve active organization for the current request without enforcing global data scoping.

    Selection priority:
    1. ``X-Active-Organization-ID`` header
    2. ``active_organization_id`` query parameter
    3. persisted session value
    4. user's default/first active membership
    """
    user = getattr(request, "user", None)
    memberships = get_user_organization_memberships(user)
    membership_organizations = []
    seen_org_ids: set[str] = set()
    for membership in memberships:
        org_id = str(membership.get("organization_id") or "")
        if not org_id or org_id in seen_org_ids:
            continue
        seen_org_ids.add(org_id)
        membership_organizations.append(
            {
                "id": org_id,
                "code": str(membership.get("organization_code") or ""),
                "name": str(membership.get("organization_name") or ""),
                "organization_type": str(membership.get("organization_type") or ""),
            }
        )

    requested_header_org_id = str(getattr(request, "META", {}).get(ACTIVE_ORGANIZATION_HEADER_KEY, "") or "").strip()
    requested_query_org_id = str(
        getattr(request, "query_params", {}).get(ACTIVE_ORGANIZATION_QUERY_PARAM, "") or ""
    ).strip()
    session = getattr(request, "session", None)
    requested_session_org_id = ""
    if session is not None:
        requested_session_org_id = str(session.get(ACTIVE_ORGANIZATION_SESSION_KEY, "") or "").strip()

    active_organization = None
    active_organization_source = "none"
    invalid_requested_org_id = ""

    for source, requested_org_id in (
        ("header", requested_header_org_id),
        ("query", requested_query_org_id),
        ("session", requested_session_org_id),
    ):
        if not requested_org_id:
            continue
        resolved = get_user_organization_by_id(user, requested_org_id)
        if resolved is not None:
            active_organization = resolved
            active_organization_source = source
            break
        if not invalid_requested_org_id and source in {"header", "query"}:
            invalid_requested_org_id = requested_org_id

    if active_organization is None:
        fallback = get_user_default_organization(user)
        if fallback is not None:
            active_organization = fallback
            active_organization_source = "default"

    return {
        "organizations": membership_organizations,
        "organization_memberships": memberships,
        "active_organization": active_organization,
        "active_organization_source": active_organization_source,
        "invalid_requested_organization_id": invalid_requested_org_id,
    }


def get_request_active_organization_id(request) -> str | None:
    active = resolve_active_organization_context(request).get("active_organization")
    if isinstance(active, dict):
        value = str(active.get("id", "") or "").strip()
        if value:
            return value
    return None


def get_user_allowed_organization_ids(user) -> set[str]:
    return set(get_user_organization_ids(user))


def can_access_organization_id(user, organization_id) -> bool:
    if is_platform_admin_user(user):
        return True

    normalized_org_id = str(organization_id or "").strip()
    if not normalized_org_id:
        # Legacy null-scoped records remain accessible during transition.
        return True

    allowed_org_ids = get_user_allowed_organization_ids(user)
    if not allowed_org_ids:
        # Legacy users without memberships remain backward-compatible.
        return True

    return normalized_org_id in allowed_org_ids


def scope_queryset_to_user_organizations(
    queryset,
    *,
    request,
    organization_field: str = "organization_id",
    include_null_legacy: bool = True,
):
    """
    Scope queryset by active org (preferred) or membership org set, with null legacy fallback.
    """
    user = getattr(request, "user", None)
    if user is None or not getattr(user, "is_authenticated", False):
        return queryset
    if is_platform_admin_user(user):
        return queryset

    allowed_org_ids = get_user_allowed_organization_ids(user)
    if not allowed_org_ids:
        return queryset

    active_org_id = get_request_active_organization_id(request)
    if active_org_id and active_org_id in allowed_org_ids:
        if include_null_legacy:
            return queryset.filter(
                Q(**{organization_field: active_org_id}) | Q(**{f"{organization_field}__isnull": True})
            )
        return queryset.filter(**{organization_field: active_org_id})

    if include_null_legacy:
        return queryset.filter(
            Q(**{f"{organization_field}__in": list(allowed_org_ids)})
            | Q(**{f"{organization_field}__isnull": True})
        )
    return queryset.filter(**{f"{organization_field}__in": list(allowed_org_ids)})
