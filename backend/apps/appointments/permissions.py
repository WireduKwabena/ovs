from rest_framework.permissions import BasePermission

from apps.core.policies.appointment_policy import (
    can_advance_stage,
    can_appoint,
    can_publish,
    can_take_committee_action,
)


def _is_appointment_record(obj) -> bool:
    return getattr(getattr(obj, "_meta", None), "model_name", "") == "appointmentrecord"


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
        return can_advance_stage(user)


class IsCommitteeMemberOrAdmin(BasePermission):
    message = "Only committee actors or admins can perform this action."

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        return can_take_committee_action(
            user,
            allow_history_fallback=True,
        )

    def has_object_permission(self, request, view, obj):
        user = getattr(request, "user", None)

        if not _is_appointment_record(obj):
            return self.has_permission(request, view)

        committee = getattr(obj, "committee", None)
        if committee is None:
            history_committee_ids = _history_committee_ids_for_appointment(obj)
            if not history_committee_ids:
                return self.has_permission(request, view)
            return can_take_committee_action(
                user=user,
                committee_ids=history_committee_ids,
                allow_history_fallback=False,
            )

        return can_take_committee_action(
            user=user,
            committee=committee,
            allow_history_fallback=False,
        )


class IsAppointingAuthorityOrAdmin(BasePermission):
    message = "Only appointing authority or admins can perform this action."

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        return can_appoint(user)


class IsPublicationOfficerOrAuthorityOrAdmin(BasePermission):
    message = "Only publication officers, appointing authority, or admins can perform this action."

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        return can_publish(user)
