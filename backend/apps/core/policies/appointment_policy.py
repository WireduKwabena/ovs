"""Appointment and governance action authorization policy helpers."""

from __future__ import annotations

from apps.core.authz import (
    CAPABILITY_APPOINTMENT_VIEW_INTERNAL,
    ROLE_ADMIN,
    ROLE_APPOINTING_AUTHORITY,
    ROLE_COMMITTEE_CHAIR,
    ROLE_COMMITTEE_MEMBER,
    ROLE_PUBLICATION_OFFICER,
    ROLE_REGISTRY_ADMIN,
    ROLE_VETTING_OFFICER,
    has_any_role,
    has_capability,
    has_role,
)
from .committee_policy import (
    has_active_committee_membership,
    has_active_membership_for_any_committee_ids,
)
from .registry_policy import has_organization_access

COMMITTEE_TRANSITION_ROLES = {ROLE_COMMITTEE_MEMBER, ROLE_COMMITTEE_CHAIR}
COMMITTEE_STAGE_OPERATIONAL_ROLES = {"member", "chair", "secretary"}


def _is_authenticated(user) -> bool:
    return bool(getattr(user, "is_authenticated", False))


def can_view_internal_record(
    user,
    *,
    organization_id=None,
    allow_membershipless_fallback: bool = False,
    enforce_org_scope_for_null: bool = False,
) -> bool:
    if not _is_authenticated(user):
        return False
    if not (has_role(user, ROLE_ADMIN) or has_capability(user, CAPABILITY_APPOINTMENT_VIEW_INTERNAL)):
        return False

    normalized_org_id = str(organization_id or "").strip()
    if not normalized_org_id and not enforce_org_scope_for_null:
        return True
    return has_organization_access(
        user,
        normalized_org_id or None,
        allow_membershipless_fallback=allow_membershipless_fallback,
    )


def can_advance_stage(
    user,
    *,
    organization_id=None,
    allow_membershipless_fallback: bool = False,
) -> bool:
    if not _is_authenticated(user):
        return False
    if not (
        has_role(user, ROLE_ADMIN)
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
    ):
        return False

    if organization_id is None:
        return True
    return has_organization_access(
        user,
        organization_id,
        allow_membershipless_fallback=allow_membershipless_fallback,
    )


def can_take_committee_action(
    user,
    *,
    committee=None,
    committee_ids=None,
    appointment_organization_id=None,
    allow_history_fallback: bool = False,
) -> bool:
    if not _is_authenticated(user):
        return False
    if has_role(user, ROLE_ADMIN):
        return True
    if not has_any_role(user, (ROLE_COMMITTEE_MEMBER, ROLE_COMMITTEE_CHAIR)):
        return False

    if committee is not None:
        return has_active_committee_membership(
            user=user,
            committee=committee,
            allow_observer=False,
        )

    if committee_ids:
        return has_active_membership_for_any_committee_ids(
            user=user,
            committee_ids=committee_ids,
            allow_observer=False,
        )

    return bool(allow_history_fallback)


def can_appoint(
    user,
    *,
    organization_id=None,
    allow_membershipless_fallback: bool = False,
) -> bool:
    if not _is_authenticated(user):
        return False
    if not (has_role(user, ROLE_ADMIN) or has_any_role(user, (ROLE_APPOINTING_AUTHORITY,))):
        return False

    if organization_id is None:
        return True
    return has_organization_access(
        user,
        organization_id,
        allow_membershipless_fallback=allow_membershipless_fallback,
    )


def can_publish(
    user,
    *,
    organization_id=None,
    allow_membershipless_fallback: bool = False,
) -> bool:
    if not _is_authenticated(user):
        return False
    if not (
        has_role(user, ROLE_ADMIN)
        or has_any_role(user, (ROLE_PUBLICATION_OFFICER, ROLE_APPOINTING_AUTHORITY))
    ):
        return False

    if organization_id is None:
        return True
    return has_organization_access(
        user,
        organization_id,
        allow_membershipless_fallback=allow_membershipless_fallback,
    )


def actor_matches_stage_role(actor, required_role: str) -> bool:
    role = str(required_role or "").strip().lower()
    if not role:
        return True

    if has_role(actor, ROLE_ADMIN):
        return True

    if role == ROLE_VETTING_OFFICER:
        return has_any_role(actor, (ROLE_VETTING_OFFICER,))
    if role in {ROLE_COMMITTEE_MEMBER, ROLE_COMMITTEE_CHAIR}:
        return has_any_role(actor, (ROLE_COMMITTEE_MEMBER, ROLE_COMMITTEE_CHAIR))
    if role == ROLE_APPOINTING_AUTHORITY:
        return has_any_role(actor, (ROLE_APPOINTING_AUTHORITY,))
    if role == ROLE_REGISTRY_ADMIN:
        return has_any_role(actor, (ROLE_REGISTRY_ADMIN,))
    if role == ROLE_PUBLICATION_OFFICER:
        return has_any_role(actor, (ROLE_PUBLICATION_OFFICER,))

    return has_role(actor, role)

