"""Audit authorization policy helpers."""

from __future__ import annotations

from apps.core.authz import CAPABILITY_AUDIT_VIEW, ROLE_ADMIN, has_capability, has_role


def can_view_audit(user) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    return bool(has_role(user, ROLE_ADMIN) or has_capability(user, CAPABILITY_AUDIT_VIEW))

