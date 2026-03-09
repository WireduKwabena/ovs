from rest_framework.permissions import BasePermission

from apps.core.authz import (
    ROLE_APPOINTING_AUTHORITY,
    ROLE_COMMITTEE_CHAIR,
    ROLE_COMMITTEE_MEMBER,
    ROLE_PUBLICATION_OFFICER,
    ROLE_REGISTRY_ADMIN,
    ROLE_VETTING_OFFICER,
    has_any_role,
)
from apps.core.permissions import is_admin_user


def _is_appointment_record(obj) -> bool:
    return getattr(getattr(obj, "_meta", None), "model_name", "") == "appointmentrecord"


def _has_eligible_committee_membership(*, user, committee) -> bool:
    try:
        from apps.governance.models import CommitteeMembership
    except Exception:  # pragma: no cover - governance app may be optional in some setups
        return False

    membership = (
        CommitteeMembership.objects.filter(
            user=user,
            committee_id=getattr(committee, "id", None),
            is_active=True,
            committee__is_active=True,
            committee__organization__is_active=True,
        )
        .exclude(committee_role="observer")
        .first()
    )
    return membership is not None


def _has_eligible_committee_membership_for_ids(*, user, committee_ids) -> bool:
    normalized_committee_ids = [value for value in committee_ids if value]
    if not normalized_committee_ids:
        return False
    try:
        from apps.governance.models import CommitteeMembership
    except Exception:  # pragma: no cover - governance app may be optional in some setups
        return False

    return CommitteeMembership.objects.filter(
        user=user,
        committee_id__in=normalized_committee_ids,
        is_active=True,
        committee__is_active=True,
        committee__organization__is_active=True,
    ).exclude(committee_role="observer").exists()


def _history_committee_ids_for_appointment(obj) -> set:
    stage_actions = getattr(obj, "stage_actions", None)
    if stage_actions is None:
        return set()

    committee_ids = set(
        stage_actions.exclude(committee_membership__committee_id__isnull=True).values_list(
            "committee_membership__committee_id", flat=True
        )
    )
    committee_ids.update(
        stage_actions.exclude(stage__committee_id__isnull=True).values_list(
            "stage__committee_id", flat=True
        )
    )
    return {value for value in committee_ids if value}


class IsStageActorOrAdmin(BasePermission):
    message = "Only authorized stage actors or admins can perform this action."

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        return bool(
            is_admin_user(user)
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
        )


class IsCommitteeMemberOrAdmin(BasePermission):
    message = "Only committee actors or admins can perform this action."

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        return bool(
            is_admin_user(user)
            or has_any_role(user, (ROLE_COMMITTEE_MEMBER, ROLE_COMMITTEE_CHAIR))
        )

    def has_object_permission(self, request, view, obj):
        user = getattr(request, "user", None)
        if is_admin_user(user):
            return True

        if not _is_appointment_record(obj):
            return self.has_permission(request, view)

        committee = getattr(obj, "committee", None)
        if committee is None:
            history_committee_ids = _history_committee_ids_for_appointment(obj)
            if not history_committee_ids:
                return self.has_permission(request, view)
            return _has_eligible_committee_membership_for_ids(
                user=user,
                committee_ids=history_committee_ids,
            )

        if getattr(obj, "organization_id", None) and getattr(committee, "organization_id", None):
            if obj.organization_id != committee.organization_id:
                return False

        return _has_eligible_committee_membership(user=user, committee=committee)


class IsAppointingAuthorityOrAdmin(BasePermission):
    message = "Only appointing authority or admins can perform this action."

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        return bool(is_admin_user(user) or has_any_role(user, (ROLE_APPOINTING_AUTHORITY,)))


class IsPublicationOfficerOrAuthorityOrAdmin(BasePermission):
    message = "Only publication officers, appointing authority, or admins can perform this action."

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        return bool(
            is_admin_user(user)
            or has_any_role(user, (ROLE_PUBLICATION_OFFICER, ROLE_APPOINTING_AUTHORITY))
        )
