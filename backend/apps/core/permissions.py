"""Shared role-based permission helpers."""

from __future__ import annotations

from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny, BasePermission

from .authz import (
    get_user_organization_ids,
    CAPABILITY_APPOINTMENT_DECIDE,
    CAPABILITY_APPOINTMENT_PUBLISH,
    CAPABILITY_APPOINTMENT_STAGE,
    CAPABILITY_APPOINTMENT_VIEW_INTERNAL,
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
from .policies.appointment_policy import can_view_internal_record
from .policies.audit_policy import can_view_audit
from .policies.registry_policy import can_manage_registry_governance

ACTIVE_ORGANIZATION_SESSION_KEY = "auth_active_organization_id"
ACTIVE_ORGANIZATION_HEADER_KEY = "HTTP_X_ACTIVE_ORGANIZATION_ID"
ACTIVE_ORGANIZATION_QUERY_PARAM = "active_organization_id"
ACTIVE_ORGANIZATION_CONTEXT_CACHE_ATTR = "_active_organization_context"
TENANT_CONTEXT_CACHE_ATTR = "_tenant_context"


def is_internal_or_admin_user(user) -> bool:
    """
    Legacy compatibility helper.

    Do not use this helper for governance-sensitive GAMS authorization.
    """
    # Keep helper narrow; operational authority remains role/capability/policy based.
    return is_government_workflow_operator(user)


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


class BlockPlatformAdminOrgWorkflowMixin:
    """
    Deny platform-admin access to organization-owned workflow endpoints.

    Platform administrators are limited to organization subscription oversight
    and organization active/inactive status management. Operational GAMS/OVS
    workflows remain organization-admin responsibilities.
    """

    platform_admin_forbidden_message = (
        "Platform admins can only manage organization subscriptions and organization active status."
    )

    def initial(self, request, *args, **kwargs):
        if is_platform_admin_user(getattr(request, "user", None)):
            # Allow public endpoints (e.g., transparency feeds) to remain accessible even
            # when a platform admin is authenticated and the client attaches auth headers.
            try:
                if any(isinstance(permission, AllowAny) for permission in self.get_permissions()):  # type: ignore[attr-defined]
                    return super().initial(request, *args, **kwargs)
            except Exception:
                # Fail closed for non-public endpoints if permission introspection breaks.
                pass
            raise PermissionDenied(self.platform_admin_forbidden_message)
        return super().initial(request, *args, **kwargs)


class IsInternalOperatorOrAdmin(BasePermission):
    message = "Only authorized internal operators/admin users can access this resource."

    def has_permission(self, request, view):
        return is_internal_or_admin_user(getattr(request, "user", None))


def is_government_workflow_operator(user, *, organization_id=None) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    if is_platform_admin_user(user):
        return True
    if not is_internal_operator(user):
        return False
    # Organization governance administrators remain valid operators even when
    # role/capability payloads are stale, but no coarse user_type fallback.
    if can_manage_registry_governance(
        user,
        organization_id=organization_id,
        allow_membershipless_fallback=False,
    ):
        return True
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
        return is_government_workflow_operator(
            getattr(request, "user", None),
            organization_id=get_request_active_organization_id(request),
        )


class IsRegistryOperatorOrAdmin(BasePermission):
    message = "Only registry operators or admins can access this resource."

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        if is_platform_admin_user(user):
            return True
        if has_capability(user, CAPABILITY_REGISTRY_MANAGE):
            return True
        return can_manage_registry_governance(
            user,
            organization_id=get_request_active_organization_id(request),
            allow_membershipless_fallback=False,
        )


def is_registry_governance_admin(user, *, organization_id=None) -> bool:
    return can_manage_registry_governance(
        user,
        organization_id=organization_id,
        allow_membershipless_fallback=False,
    )


class IsRegistryGovernanceAdmin(BasePermission):
    message = "Only organization registry administrators or platform administrators can access this resource."

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        organization_id = get_request_active_organization_id(request)
        return is_registry_governance_admin(
            user,
            organization_id=organization_id,
        )


class IsAuditReaderOrAdmin(BasePermission):
    message = "Only auditors or admins can access this resource."

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        return can_view_audit(user)


class CanViewInternalAppointmentData(BasePermission):
    message = "Only internal operators can view internal appointment details."

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        return can_view_internal_record(user)


def user_roles(user) -> list[str]:
    """Expose sorted role keys for serializers/debug views."""
    return sorted(get_user_roles(user))


def user_organization_scope(user) -> list[str]:
    """
    Governance-first org scope with legacy ``user.organization`` fallback.

    This helper is additive and intentionally not enforced globally in Phase 1.
    """
    return sorted(get_user_organization_names(user))


def _build_active_organization_context(request) -> dict:
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


def resolve_active_organization_context(request) -> dict:
    cached = getattr(request, ACTIVE_ORGANIZATION_CONTEXT_CACHE_ATTR, None)
    if isinstance(cached, dict):
        return cached
    context = _build_active_organization_context(request)
    setattr(request, ACTIVE_ORGANIZATION_CONTEXT_CACHE_ATTR, context)
    return context


def clear_request_tenant_context_cache(request) -> None:
    for attr_name in (ACTIVE_ORGANIZATION_CONTEXT_CACHE_ATTR, TENANT_CONTEXT_CACHE_ATTR):
        if hasattr(request, attr_name):
            delattr(request, attr_name)


def get_request_active_organization_id(request) -> str | None:
    active = resolve_active_organization_context(request).get("active_organization")
    if isinstance(active, dict):
        value = str(active.get("id", "") or "").strip()
        if value:
            return value
    return None


def get_request_tenant_context(request) -> dict:
    cached = getattr(request, TENANT_CONTEXT_CACHE_ATTR, None)
    if isinstance(cached, dict):
        return cached

    organization_context = resolve_active_organization_context(request)
    user = getattr(request, "user", None)
    allowed_org_ids = get_user_allowed_organization_ids(user)
    active_org = organization_context.get("active_organization")
    active_org_id = ""
    if isinstance(active_org, dict):
        active_org_id = str(active_org.get("id", "") or "").strip()
    context = {
        **organization_context,
        "active_organization_id": active_org_id or None,
        "allowed_organization_ids": allowed_org_ids,
        "has_memberships": bool(allowed_org_ids),
        "is_platform_admin": bool(is_platform_admin_user(user)),
    }
    setattr(request, TENANT_CONTEXT_CACHE_ATTR, context)
    return context


def get_user_allowed_organization_ids(user) -> set[str]:
    return set(get_user_organization_ids(user))


def can_access_organization_id(
    user,
    organization_id,
    *,
    allow_membershipless_fallback: bool = False,
) -> bool:
    if is_platform_admin_user(user):
        return True

    normalized_org_id = str(organization_id or "").strip()
    if not normalized_org_id:
        if allow_membershipless_fallback:
            # Compatibility mode can keep null-scoped records writable.
            return True
        allowed_org_ids = get_user_allowed_organization_ids(user)
        # In strict mode, null-scoped records are writable only for legacy users
        # who have not yet been migrated to org memberships.
        return not bool(allowed_org_ids)

    allowed_org_ids = get_user_allowed_organization_ids(user)
    if not allowed_org_ids:
        # Compatibility mode for legacy users without governance memberships.
        return bool(allow_membershipless_fallback)

    return normalized_org_id in allowed_org_ids


def can_access_organization_id_strict(user, organization_id) -> bool:
    return can_access_organization_id(
        user,
        organization_id,
        allow_membershipless_fallback=False,
    )


def scope_queryset_to_user_organizations(
    queryset,
    *,
    request,
    organization_field: str = "organization_id",
    include_null_legacy: bool = True,
    allow_membershipless_fallback: bool = False,
):
    """
    Scope queryset to the current tenant.

    In django-tenants, schema isolation already guarantees that all queryset rows
    belong to the current tenant — no organization_id filter is required.  The
    parameters are retained for call-site compatibility but are intentionally
    unused; the function simply returns the queryset as-is after an authentication
    guard.
    """
    user = getattr(request, "user", None)
    if user is None or not getattr(user, "is_authenticated", False):
        return queryset.none()
    return queryset


def scope_internal_queryset_to_tenant(
    queryset,
    *,
    request,
    organization_field: str = "organization_id",
    include_null_legacy: bool = True,
):
    """
    Strict tenant scoping for internal workflows.

    In django-tenants, schema isolation already scopes data to the current tenant.
    Authentication is enforced; membership checks are handled by permission classes
    (IsGovernmentWorkflowOperator etc.) before the queryset is built.
    """
    user = getattr(request, "user", None)
    if user is None or not getattr(user, "is_authenticated", False):
        return queryset.none()
    return queryset

