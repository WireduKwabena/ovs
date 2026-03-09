"""Registry and tenant-scope authorization policy helpers."""

from __future__ import annotations

from apps.core.authz import (
    CAPABILITY_REGISTRY_MANAGE,
    ROLE_ADMIN,
    get_user_organization_ids,
    has_capability,
    has_role,
)


def _is_authenticated(user) -> bool:
    return bool(getattr(user, "is_authenticated", False))


def is_platform_admin_actor(user) -> bool:
    """
    Strict platform-admin bypass used for tenant recovery operations.

    Mirrors legacy behavior where superusers and ``user_type=admin`` bypass org scope.
    """
    if not _is_authenticated(user):
        return False
    return bool(getattr(user, "is_superuser", False) or getattr(user, "user_type", None) == "admin")


def has_organization_access(
    user,
    organization_id,
    *,
    allow_membershipless_fallback: bool = False,
) -> bool:
    """
    Evaluate whether actor can operate within an organization scope.

    Compatibility behavior:
    - null organization can be writable when ``allow_membershipless_fallback`` is enabled
    - membership-less users can still operate on legacy null-scoped rows only in compatibility mode
    """
    if is_platform_admin_actor(user):
        return True

    normalized_org_id = str(organization_id or "").strip()
    allowed_org_ids = {str(value) for value in get_user_organization_ids(user)}

    if not normalized_org_id:
        if allow_membershipless_fallback:
            return True
        return not bool(allowed_org_ids)

    if not allowed_org_ids:
        return bool(allow_membershipless_fallback)

    return normalized_org_id in allowed_org_ids


def can_manage_registry(
    user,
    *,
    organization_id=None,
    allow_membershipless_fallback: bool = False,
) -> bool:
    if not _is_authenticated(user):
        return False

    if not (has_role(user, ROLE_ADMIN) or has_capability(user, CAPABILITY_REGISTRY_MANAGE)):
        return False

    if organization_id is None:
        return True

    return has_organization_access(
        user,
        organization_id,
        allow_membershipless_fallback=allow_membershipless_fallback,
    )


def can_manage_registry_record(
    user,
    record,
    *,
    organization_attr: str = "organization_id",
    allow_membershipless_fallback: bool = False,
) -> bool:
    if record is None:
        return can_manage_registry(
            user,
            organization_id=None,
            allow_membershipless_fallback=allow_membershipless_fallback,
        )
    organization_id = getattr(record, organization_attr, None)
    return can_manage_registry(
        user,
        organization_id=organization_id,
        allow_membershipless_fallback=allow_membershipless_fallback,
    )

