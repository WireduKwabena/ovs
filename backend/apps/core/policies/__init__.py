"""Policy layer for centralized authorization decisions."""

from .appointment_policy import (
    actor_matches_stage_role,
    can_advance_stage,
    can_appoint,
    can_publish,
    can_take_committee_action,
    can_view_internal_record,
)
from .audit_policy import can_view_audit
from .committee_policy import (
    get_active_committee_membership,
    has_active_committee_membership,
    has_active_membership_for_any_committee_ids,
)
from .registry_policy import (
    can_manage_registry,
    can_manage_registry_record,
    has_organization_access,
    is_platform_admin_actor,
)

__all__ = [
    "actor_matches_stage_role",
    "can_advance_stage",
    "can_appoint",
    "can_manage_registry",
    "can_manage_registry_record",
    "can_publish",
    "can_take_committee_action",
    "can_view_audit",
    "can_view_internal_record",
    "get_active_committee_membership",
    "has_active_committee_membership",
    "has_active_membership_for_any_committee_ids",
    "has_organization_access",
    "is_platform_admin_actor",
]
