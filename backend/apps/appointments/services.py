from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.audit.contracts import APPOINTMENT_STAGE_TRANSITION_EVENT
from apps.audit.events import log_event
from apps.billing.quotas import enforce_candidate_quota
from apps.candidates.models import Candidate, CandidateEnrollment

from .models import AppointmentRecord, AppointmentStageAction


class InvalidTransitionError(Exception):
    """Raised when an appointment state transition is not allowed."""


class StageAuthorizationError(Exception):
    """Raised when actor lacks permission for requested stage transition."""


ALLOWED_TRANSITIONS = {
    "nominated": {"under_vetting", "withdrawn"},
    "under_vetting": {"committee_review", "withdrawn"},
    "committee_review": {"confirmation_pending", "appointed", "rejected", "withdrawn"},
    "confirmation_pending": {"appointed", "rejected", "withdrawn"},
    "appointed": {"serving"},
    "serving": {"exited"},
}


def _has_named_group(user, group_name: str) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    return user.groups.filter(name=group_name).exists()


def _actor_matches_stage_role(actor, required_role: str) -> bool:
    role = str(required_role or "").strip().lower()
    if not role:
        return True

    if getattr(actor, "is_staff", False) or getattr(actor, "is_superuser", False) or getattr(actor, "user_type", "") == "admin":
        return True

    if role == "vetting_officer":
        return getattr(actor, "user_type", "") == "hr_manager" and _has_named_group(actor, "vetting_officer")
    if role == "committee_member":
        return getattr(actor, "user_type", "") == "hr_manager" and _has_named_group(actor, "committee_member")
    if role == "appointing_authority":
        return _has_named_group(actor, "appointing_authority")
    if role == "registry_admin":
        return _has_named_group(actor, "registry_admin")

    return _has_named_group(actor, role)


def _resolve_applicant_user(candidate: Candidate):
    from django.db import IntegrityError

    from apps.authentication.models import User

    existing_user = User.objects.filter(email__iexact=candidate.email).first()
    if existing_user:
        return existing_user

    name_parts = (candidate.first_name or "").strip(), (candidate.last_name or "").strip()
    try:
        return User.objects.create_user(
            email=candidate.email,
            password=None,
            first_name=name_parts[0],
            last_name=name_parts[1],
            user_type="applicant",
        )
    except IntegrityError:
        recovered = User.objects.filter(email__iexact=candidate.email).first()
        if recovered:
            return recovered
        raise


def _candidate_from_personnel_nominee(appointment: AppointmentRecord) -> Candidate:
    nominee = appointment.nominee
    linked = nominee.linked_candidate
    if linked is not None:
        return linked

    full_name = (nominee.full_name or "").strip()
    name_tokens = full_name.split()
    first_name = name_tokens[0] if name_tokens else "Nominee"
    last_name = " ".join(name_tokens[1:]) if len(name_tokens) > 1 else "Candidate"

    candidate_email = (nominee.contact_email or "").strip().lower()
    if not candidate_email:
        candidate_email = f"nominee-{nominee.id}@example.invalid"

    candidate, _created = Candidate.objects.get_or_create(
        email=candidate_email,
        defaults={
            "first_name": first_name,
            "last_name": last_name,
            "phone_number": nominee.contact_phone or "",
            "preferred_channel": "email",
        },
    )
    if nominee.linked_candidate_id != candidate.id:
        nominee.linked_candidate = candidate
        nominee.save(update_fields=["linked_candidate", "updated_at"])
    return candidate


def ensure_vetting_linkage_for_appointment(*, appointment: AppointmentRecord, actor):
    """Ensure appointment has campaign enrollment and a linked vetting case."""
    if appointment.appointment_exercise_id is None:
        return appointment

    from apps.applications.models import VettingCase

    candidate = _candidate_from_personnel_nominee(appointment)

    existing_enrollment = CandidateEnrollment.objects.filter(
        campaign=appointment.appointment_exercise,
        candidate=candidate,
    ).first()
    if existing_enrollment is None and getattr(actor, "user_type", "") == "hr_manager":
        enforce_candidate_quota(user=actor, additional=1)

    enrollment, _created = CandidateEnrollment.objects.get_or_create(
        campaign=appointment.appointment_exercise,
        candidate=candidate,
        defaults={
            "status": "invited",
            "invited_at": timezone.now(),
        },
    )

    linked_case = appointment.vetting_case
    if linked_case is None:
        linked_case = VettingCase.objects.filter(candidate_enrollment=enrollment).order_by("-created_at").first()

    if linked_case is None:
        linked_case = VettingCase.objects.create(
            applicant=_resolve_applicant_user(candidate),
            candidate_enrollment=enrollment,
            assigned_to=appointment.appointment_exercise.initiated_by,
            position_applied=appointment.position.title,
            department=appointment.position.institution[:100],
            job_description=appointment.position.required_qualifications,
            priority="medium",
            status="document_upload",
        )

    if appointment.vetting_case_id != linked_case.id:
        appointment.vetting_case = linked_case
        appointment.save(update_fields=["vetting_case", "updated_at"])

    _ensure_nominee_invitation(enrollment=enrollment, actor=actor)

    return appointment


def _ensure_nominee_invitation(*, enrollment, actor):
    from apps.invitations.models import Invitation
    from apps.invitations.tasks import send_invitation_task

    existing = (
        Invitation.objects.filter(
            enrollment=enrollment,
            status__in={"pending", "sent", "accepted"},
        )
        .order_by("-created_at")
        .first()
    )
    if existing is not None and not existing.is_expired:
        return existing

    candidate = enrollment.candidate
    preferred = "sms" if (candidate.preferred_channel == "sms" and candidate.phone_number) else "email"
    send_to = candidate.phone_number if preferred == "sms" else candidate.email
    if not send_to:
        return None

    ttl_hours = int(getattr(settings, "CANDIDATE_INVITATION_TTL_HOURS", 72))
    invitation = Invitation.objects.create(
        enrollment=enrollment,
        channel=preferred,
        send_to=send_to,
        expires_at=timezone.now() + timedelta(hours=ttl_hours),
        created_by=actor if getattr(actor, "is_authenticated", False) else None,
    )
    send_invitation_task.delay(invitation.id)
    return invitation


def advance_stage(
    *,
    appointment: AppointmentRecord,
    new_status: str,
    actor,
    stage=None,
    reason_note: str = "",
    evidence_links=None,
    request=None,
) -> AppointmentRecord:
    allowed = ALLOWED_TRANSITIONS.get(appointment.status, set())
    if new_status not in allowed:
        raise InvalidTransitionError(f"{appointment.status} -> {new_status} is not permitted.")

    if stage is not None:
        if stage.maps_to_status != new_status:
            raise InvalidTransitionError(
                f"Stage '{stage.name}' maps to '{stage.maps_to_status}', cannot advance to '{new_status}'."
            )
        if not _actor_matches_stage_role(actor, stage.required_role):
            raise StageAuthorizationError(f"Actor lacks required role '{stage.required_role}' for stage '{stage.name}'.")

    if new_status in {"appointed", "rejected"} and not (
        getattr(actor, "is_staff", False)
        or getattr(actor, "is_superuser", False)
        or getattr(actor, "user_type", "") == "admin"
        or _has_named_group(actor, "appointing_authority")
    ):
        raise StageAuthorizationError("Only appointing authority/admin can finalize appointment decisions.")

    previous_status = appointment.status
    now = timezone.now()

    with transaction.atomic():
        appointment.status = new_status

        if new_status == "appointed":
            appointment.appointment_date = appointment.appointment_date or now.date()
            appointment.final_decision_by_user = appointment.final_decision_by_user or actor
            if not appointment.final_decision_by_display:
                appointment.final_decision_by_display = getattr(actor, "get_full_name", lambda: "")() or getattr(
                    actor, "email", ""
                )
        if new_status == "exited" and appointment.exit_date is None:
            appointment.exit_date = now.date()
        if new_status == "serving":
            position = appointment.position
            position.current_holder = appointment.nominee
            position.is_vacant = False
            position.save(update_fields=["current_holder", "is_vacant", "updated_at"])
            appointment.nominee.is_active_officeholder = True
            appointment.nominee.save(update_fields=["is_active_officeholder", "updated_at"])

        appointment.save(update_fields=[
            "status",
            "appointment_date",
            "final_decision_by_user",
            "final_decision_by_display",
            "exit_date",
            "updated_at",
        ])

        AppointmentStageAction.objects.create(
            appointment=appointment,
            stage=stage,
            actor=actor,
            actor_role=getattr(actor, "user_type", "") or ("admin" if getattr(actor, "is_staff", False) else "user"),
            action="noted",
            reason_note=reason_note,
            evidence_links=evidence_links or [],
            previous_status=previous_status,
            new_status=new_status,
        )

        if request is not None:
            log_event(
                request=request,
                action="update",
                entity_type="AppointmentRecord",
                entity_id=str(appointment.id),
                changes={
                    "event": APPOINTMENT_STAGE_TRANSITION_EVENT,
                    "from": previous_status,
                    "to": new_status,
                    "reason_note": reason_note,
                },
            )

    return appointment
