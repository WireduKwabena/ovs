from datetime import timedelta
import logging

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.audit.contracts import (
    APPOINTMENT_FINAL_DECISION_RECORDED_EVENT,
    APPOINTMENT_NOMINATION_CREATED_EVENT,
    APPOINTMENT_PUBLICATION_PUBLISHED_EVENT,
    APPOINTMENT_PUBLICATION_REVOKED_EVENT,
    APPOINTMENT_STAGE_ACTION_TAKEN_EVENT,
    APPOINTMENT_STAGE_TRANSITION_EVENT,
)
from apps.audit.events import log_event
from apps.billing.quotas import enforce_candidate_quota
from apps.candidates.models import Candidate, CandidateEnrollment
try:
    from apps.notifications.services import NotificationService
except Exception:  # pragma: no cover - notifications app may be optional in some setups
    NotificationService = None  # type: ignore[assignment]

from .models import AppointmentPublication, AppointmentRecord, AppointmentStageAction

logger = logging.getLogger(__name__)


class InvalidTransitionError(Exception):
    """Raised when an appointment state transition is not allowed."""


class StageAuthorizationError(Exception):
    """Raised when actor lacks permission for requested stage transition."""


class LinkageValidationError(Exception):
    """Raised when appointment campaign/case linkage is inconsistent."""


class PublicationLifecycleError(Exception):
    """Raised when appointment publication lifecycle action is invalid."""


ALLOWED_TRANSITIONS = {
    "nominated": {"under_vetting", "withdrawn"},
    "under_vetting": {"committee_review", "withdrawn"},
    "committee_review": {"confirmation_pending", "appointed", "rejected", "withdrawn"},
    "confirmation_pending": {"appointed", "rejected", "withdrawn"},
    "appointed": {"serving"},
    "serving": {"exited"},
}


APPOINTMENT_NOTIFICATION_EVENT_NOMINATION_CREATED = "appointment_nomination_created"
APPOINTMENT_NOTIFICATION_EVENT_MOVED_TO_INTAKE_CHECK = "appointment_moved_to_intake_check"
APPOINTMENT_NOTIFICATION_EVENT_MOVED_TO_UNDER_VETTING = "appointment_moved_to_under_vetting"
APPOINTMENT_NOTIFICATION_EVENT_MOVED_TO_COMMITTEE_REVIEW = "appointment_moved_to_committee_review"
APPOINTMENT_NOTIFICATION_EVENT_MOVED_TO_APPROVAL_CHAIN = "appointment_moved_to_approval_chain"
APPOINTMENT_NOTIFICATION_EVENT_APPROVED = "appointment_approved"
APPOINTMENT_NOTIFICATION_EVENT_REJECTED = "appointment_rejected"
APPOINTMENT_NOTIFICATION_EVENT_APPOINTED = "appointment_appointed"
APPOINTMENT_NOTIFICATION_EVENT_PUBLISHED = "appointment_published"
APPOINTMENT_NOTIFICATION_EVENT_REVOKED = "appointment_revoked"


def _safe_actor_display(actor) -> str:
    if actor is None:
        return ""
    return getattr(actor, "get_full_name", lambda: "")() or getattr(actor, "email", "")


def _safe_str_id(value) -> str:
    return str(value) if value is not None else ""


def _appointment_transition_notification_events(*, previous_status: str, new_status: str) -> list[str]:
    if previous_status == "nominated" and new_status == "under_vetting":
        return [
            APPOINTMENT_NOTIFICATION_EVENT_MOVED_TO_INTAKE_CHECK,
            APPOINTMENT_NOTIFICATION_EVENT_MOVED_TO_UNDER_VETTING,
        ]
    if new_status == "under_vetting":
        return [APPOINTMENT_NOTIFICATION_EVENT_MOVED_TO_UNDER_VETTING]
    if new_status == "committee_review":
        return [APPOINTMENT_NOTIFICATION_EVENT_MOVED_TO_COMMITTEE_REVIEW]
    if new_status == "confirmation_pending":
        return [APPOINTMENT_NOTIFICATION_EVENT_MOVED_TO_APPROVAL_CHAIN]
    if new_status == "appointed":
        return [
            APPOINTMENT_NOTIFICATION_EVENT_APPROVED,
            APPOINTMENT_NOTIFICATION_EVENT_APPOINTED,
        ]
    if new_status == "rejected":
        return [APPOINTMENT_NOTIFICATION_EVENT_REJECTED]
    return []


def _emit_appointment_notifications(
    *,
    appointment: AppointmentRecord,
    event_types: list[str],
    actor,
    previous_status: str = "",
    new_status: str = "",
    stage=None,
    metadata: dict | None = None,
    idempotency_seed: str = "",
) -> None:
    if not event_types or NotificationService is None:
        return

    for event_type in event_types:
        try:
            NotificationService.send_appointment_lifecycle_notification(
                appointment=appointment,
                event_type=event_type,
                actor=actor,
                previous_status=previous_status,
                new_status=new_status,
                stage=stage,
                metadata=metadata or {},
                idempotency_key=(
                    f"appointment:{appointment.id}:{event_type}:{idempotency_seed}"
                    if idempotency_seed
                    else None
                ),
            )
        except Exception:
            logger.warning(
                "Failed to send appointment lifecycle notification event=%s appointment_id=%s",
                event_type,
                appointment.id,
                exc_info=True,
            )


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


def _normalize_text(value) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _approval_template_for_appointment(appointment: AppointmentRecord):
    exercise = getattr(appointment, "appointment_exercise", None)
    if exercise is None:
        return None
    return getattr(exercise, "approval_template", None)


def _validate_campaign_position_and_rubric_alignment(appointment: AppointmentRecord) -> None:
    exercise = appointment.appointment_exercise
    if exercise is None:
        return

    position = appointment.position
    if exercise.positions.exists() and not exercise.positions.filter(id=position.id).exists():
        raise LinkageValidationError("Selected position is not linked to the appointment exercise.")

    if exercise.jurisdiction and exercise.jurisdiction != position.branch:
        raise LinkageValidationError("Appointment exercise jurisdiction does not match position branch.")

    if (
        exercise.appointment_authority
        and position.appointment_authority
        and _normalize_text(exercise.appointment_authority) != _normalize_text(position.appointment_authority)
    ):
        raise LinkageValidationError("Campaign appointing authority does not match position appointment authority.")

    if exercise.requires_parliamentary_confirmation and not position.confirmation_required:
        raise LinkageValidationError(
            "Campaign requires parliamentary confirmation, but selected position is not marked as confirmation-required."
        )

    if position.rubric_id:
        active_version = exercise.rubric_versions.filter(is_active=True).order_by("-version", "-created_at").first()
        if active_version is not None:
            payload = active_version.rubric_payload if isinstance(active_version.rubric_payload, dict) else {}
            source_rubric_id = payload.get("source_rubric_id")
            if source_rubric_id and str(source_rubric_id) != str(position.rubric_id):
                raise LinkageValidationError("Position rubric does not match the active campaign rubric source.")


def _validate_existing_vetting_case_linkage(appointment: AppointmentRecord) -> None:
    linked_case = appointment.vetting_case
    if linked_case is None:
        return

    exercise = appointment.appointment_exercise
    if exercise and linked_case.candidate_enrollment_id:
        if linked_case.candidate_enrollment.campaign_id != exercise.id:
            raise LinkageValidationError("Provided vetting case belongs to a different campaign.")

    if linked_case.position_applied and _normalize_text(linked_case.position_applied) != _normalize_text(appointment.position.title):
        raise LinkageValidationError("Provided vetting case position does not match selected appointment position.")

    if linked_case.department and _normalize_text(linked_case.department) != _normalize_text(appointment.position.institution[:100]):
        raise LinkageValidationError("Provided vetting case department does not match selected appointment position institution.")

    nominee = appointment.nominee
    if linked_case.candidate_enrollment_id and nominee.linked_candidate_id:
        if linked_case.candidate_enrollment.candidate_id != nominee.linked_candidate_id:
            raise LinkageValidationError("Provided vetting case candidate does not match nominee linked candidate.")


def _enforce_required_stage_context(*, appointment: AppointmentRecord, new_status: str, stage) -> None:
    template = _approval_template_for_appointment(appointment)
    if template is None:
        return

    required_stages = template.stages.filter(is_required=True).order_by("order", "id")
    if not required_stages.exists():
        return

    required_for_status = required_stages.filter(maps_to_status=new_status)
    if required_for_status.exists() and stage is None:
        raise InvalidTransitionError(
            f"Stage context is required for transition to '{new_status}' under approval template '{template.name}'."
        )

    if stage is None:
        return

    if stage.template_id != template.id:
        raise InvalidTransitionError(
            f"Stage '{stage.name}' does not belong to appointment approval template '{template.name}'."
        )

    if required_for_status.exists() and not required_for_status.filter(id=stage.id).exists():
        raise InvalidTransitionError(
            f"Transition to '{new_status}' must use a required stage configured for that status in template '{template.name}'."
        )

    if stage.is_required:
        completed_required_ids = set(
            appointment.stage_actions.filter(stage__template=template, stage__is_required=True).values_list("stage_id", flat=True)
        )
        missing_prior = required_stages.filter(order__lt=stage.order).exclude(id__in=completed_required_ids)
        if missing_prior.exists():
            pending = ", ".join(missing_prior.values_list("name", flat=True))
            raise InvalidTransitionError(
                f"Cannot transition via stage '{stage.name}' before completing required prior stages: {pending}."
            )


def _resolve_applicant_user(candidate: Candidate):
    from django.db import IntegrityError

    from apps.authentication.models import User

    existing_user = User.objects.filter(email__iexact=candidate.email).first()
    if existing_user:
        if getattr(existing_user, "user_type", "") != "applicant":
            raise LinkageValidationError(
                "Candidate email matches an existing non-applicant user; cannot attach vetting case applicant safely."
            )
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
            if getattr(recovered, "user_type", "") != "applicant":
                raise LinkageValidationError(
                    "Candidate email maps to non-applicant user after recovery; cannot attach vetting case applicant."
                )
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

    _validate_campaign_position_and_rubric_alignment(appointment)
    _validate_existing_vetting_case_linkage(appointment)

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

    if linked_case is not None and linked_case.candidate_enrollment_id and linked_case.candidate_enrollment_id != enrollment.id:
        raise LinkageValidationError("Resolved vetting case belongs to different candidate enrollment than appointment exercise.")

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
    elif linked_case.candidate_enrollment_id is None:
        linked_case.candidate_enrollment = enrollment
        linked_case.save(update_fields=["candidate_enrollment", "updated_at"])

    if appointment.vetting_case_id != linked_case.id:
        appointment.vetting_case = linked_case
        appointment.save(update_fields=["vetting_case", "updated_at"])

    _ensure_nominee_invitation(enrollment=enrollment, actor=actor)

    return appointment


def notify_nomination_created(*, appointment: AppointmentRecord, actor, request=None) -> None:
    """Emit nomination-created notification + additive lifecycle audit event."""
    _emit_appointment_notifications(
        appointment=appointment,
        event_types=[APPOINTMENT_NOTIFICATION_EVENT_NOMINATION_CREATED],
        actor=actor,
        previous_status="",
        new_status=appointment.status,
        metadata={
            "event": APPOINTMENT_NOMINATION_CREATED_EVENT,
            "campaign_id": _safe_str_id(appointment.appointment_exercise_id),
        },
        idempotency_seed=str(appointment.id),
    )

    if request is None:
        return
    log_event(
        request=request,
        action="create",
        entity_type="AppointmentRecord",
        entity_id=str(appointment.id),
        changes={
            "event": APPOINTMENT_NOMINATION_CREATED_EVENT,
            "position_id": _safe_str_id(appointment.position_id),
            "nominee_id": _safe_str_id(appointment.nominee_id),
            "status": appointment.status,
            "campaign_id": _safe_str_id(appointment.appointment_exercise_id),
            "nominated_by": _safe_actor_display(actor),
        },
    )


def ensure_publication_record_for_appointment(*, appointment: AppointmentRecord) -> AppointmentPublication:
    publication, _created = AppointmentPublication.objects.get_or_create(
        appointment=appointment,
        defaults={
            "status": "draft",
            "publication_reference": appointment.gazette_number or "",
            "publication_document_hash": "",
            "publication_notes": "",
            "published_by_id": None,
            "published_at": None,
        },
    )
    return publication


def publish_appointment_record(
    *,
    appointment: AppointmentRecord,
    actor,
    publication_reference: str = "",
    publication_document_hash: str = "",
    publication_notes: str = "",
    gazette_number: str | None = None,
    gazette_date=None,
    request=None,
) -> AppointmentPublication:
    publication_reference = (publication_reference or "").strip()
    publication_document_hash = (publication_document_hash or "").strip().lower()
    publication_notes = (publication_notes or "").strip()
    now = timezone.now()

    with transaction.atomic():
        publication = ensure_publication_record_for_appointment(appointment=appointment)
        previous_publication_status = publication.status
        publication.status = "published"
        publication.published_by = actor if getattr(actor, "is_authenticated", False) else None
        if previous_publication_status == "published":
            publication.published_at = publication.published_at or now
        else:
            publication.published_at = now
        publication.revoked_by = None
        publication.revoked_at = None
        publication.revocation_reason = ""
        if publication_reference:
            publication.publication_reference = publication_reference
        if publication_document_hash:
            publication.publication_document_hash = publication_document_hash
        if publication_notes:
            publication.publication_notes = publication_notes
        publication.save(
            update_fields=[
                "status",
                "published_by",
                "published_at",
                "revoked_by",
                "revoked_at",
                "revocation_reason",
                "publication_reference",
                "publication_document_hash",
                "publication_notes",
                "updated_at",
            ]
        )

        appointment.is_public = True
        if gazette_number is not None:
            appointment.gazette_number = str(gazette_number).strip()
        elif publication_reference and not appointment.gazette_number:
            appointment.gazette_number = publication_reference
        if gazette_date is not None:
            appointment.gazette_date = gazette_date
        appointment.save(update_fields=["is_public", "gazette_number", "gazette_date", "updated_at"])

        if previous_publication_status != "published":
            _emit_appointment_notifications(
                appointment=appointment,
                event_types=[APPOINTMENT_NOTIFICATION_EVENT_PUBLISHED],
                actor=actor,
                new_status=appointment.status,
                metadata={
                    "publication_status": publication.status,
                    "publication_reference": publication.publication_reference,
                    "published_at": publication.published_at.isoformat() if publication.published_at else "",
                },
                idempotency_seed=publication.published_at.isoformat() if publication.published_at else str(appointment.id),
            )

        if request is not None:
            log_event(
                request=request,
                action="update",
                entity_type="AppointmentRecord",
                entity_id=str(appointment.id),
                changes={
                    "event": APPOINTMENT_PUBLICATION_PUBLISHED_EVENT,
                    "publication_status": publication.status,
                    "publication_reference": publication.publication_reference,
                    "published_at": publication.published_at.isoformat() if publication.published_at else "",
                    "was_status": previous_publication_status,
                },
            )

    return publication


def revoke_appointment_publication(
    *,
    appointment: AppointmentRecord,
    actor,
    revocation_reason: str,
    make_private: bool = True,
    request=None,
) -> AppointmentPublication:
    reason = (revocation_reason or "").strip()
    if not reason:
        raise PublicationLifecycleError("revocation_reason is required to revoke publication.")

    now = timezone.now()
    with transaction.atomic():
        publication = ensure_publication_record_for_appointment(appointment=appointment)
        if publication.status != "published":
            raise PublicationLifecycleError("Only published appointments can be revoked.")

        publication.status = "revoked"
        publication.revoked_by = actor if getattr(actor, "is_authenticated", False) else None
        publication.revoked_at = now
        publication.revocation_reason = reason
        publication.save(
            update_fields=[
                "status",
                "revoked_by",
                "revoked_at",
                "revocation_reason",
                "updated_at",
            ]
        )

        if make_private and appointment.is_public:
            appointment.is_public = False
            appointment.save(update_fields=["is_public", "updated_at"])

        _emit_appointment_notifications(
            appointment=appointment,
            event_types=[APPOINTMENT_NOTIFICATION_EVENT_REVOKED],
            actor=actor,
            new_status=appointment.status,
            metadata={
                "publication_status": publication.status,
                "revoked_at": publication.revoked_at.isoformat() if publication.revoked_at else "",
                "make_private": bool(make_private),
            },
            idempotency_seed=publication.revoked_at.isoformat() if publication.revoked_at else str(appointment.id),
        )

        if request is not None:
            log_event(
                request=request,
                action="update",
                entity_type="AppointmentRecord",
                entity_id=str(appointment.id),
                changes={
                    "event": APPOINTMENT_PUBLICATION_REVOKED_EVENT,
                    "publication_status": publication.status,
                    "revoked_at": publication.revoked_at.isoformat() if publication.revoked_at else "",
                    "revocation_reason_present": bool(publication.revocation_reason),
                },
            )

    return publication


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
    try:
        send_invitation_task.delay(invitation.id)
    except Exception as exc:
        logger.warning(
            "Failed to dispatch invitation task for enrollment_id=%s invitation_id=%s error=%s",
            getattr(enrollment, "id", None),
            invitation.id,
            exc,
        )
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

    _enforce_required_stage_context(appointment=appointment, new_status=new_status, stage=stage)

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
        if new_status in {"serving", "exited"} and appointment.appointment_date is None:
            appointment.appointment_date = now.date()
        if new_status == "serving":
            position = appointment.position
            position.current_holder = appointment.nominee
            position.is_vacant = False
            position.save(update_fields=["current_holder", "is_vacant", "updated_at"])
            appointment.nominee.is_active_officeholder = True
            appointment.nominee.save(update_fields=["is_active_officeholder", "updated_at"])
        if new_status == "exited":
            if appointment.exit_date is None:
                appointment.exit_date = now.date()

            position = appointment.position
            if position.current_holder_id == appointment.nominee_id or not position.is_vacant:
                if position.current_holder_id == appointment.nominee_id:
                    position.current_holder = None
                position.is_vacant = True
                position.save(update_fields=["current_holder", "is_vacant", "updated_at"])

            nominee = appointment.nominee
            has_other_current_positions = nominee.current_positions.exclude(id=position.id).exists()
            if nominee.is_active_officeholder and not has_other_current_positions:
                nominee.is_active_officeholder = False
                nominee.save(update_fields=["is_active_officeholder", "updated_at"])

        appointment.save(update_fields=[
            "status",
            "appointment_date",
            "final_decision_by_user",
            "final_decision_by_display",
            "exit_date",
            "updated_at",
        ])

        stage_action = AppointmentStageAction.objects.create(
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

        _emit_appointment_notifications(
            appointment=appointment,
            event_types=_appointment_transition_notification_events(
                previous_status=previous_status,
                new_status=new_status,
            ),
            actor=actor,
            previous_status=previous_status,
            new_status=new_status,
            stage=stage,
            metadata={
                "stage_action_id": str(stage_action.id),
                "actor_id": _safe_str_id(getattr(actor, "id", None)),
                "actor_display": _safe_actor_display(actor),
                "decision_status": new_status if new_status in {"appointed", "rejected"} else "",
            },
            idempotency_seed=str(stage_action.id),
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
                    "stage_id": _safe_str_id(getattr(stage, "id", None)),
                    "stage_name": str(getattr(stage, "name", "")),
                    "has_reason_note": bool(str(reason_note or "").strip()),
                },
            )
            log_event(
                request=request,
                action="update",
                entity_type="AppointmentRecord",
                entity_id=str(appointment.id),
                changes={
                    "event": APPOINTMENT_STAGE_ACTION_TAKEN_EVENT,
                    "stage_action_id": str(stage_action.id),
                    "from": previous_status,
                    "to": new_status,
                    "stage_id": _safe_str_id(getattr(stage, "id", None)),
                    "stage_name": str(getattr(stage, "name", "")),
                    "actor_id": _safe_str_id(getattr(actor, "id", None)),
                    "actor_role": stage_action.actor_role,
                    "has_reason_note": bool(str(reason_note or "").strip()),
                },
            )
            if new_status in {"appointed", "rejected"}:
                log_event(
                    request=request,
                    action="update",
                    entity_type="AppointmentRecord",
                    entity_id=str(appointment.id),
                    changes={
                        "event": APPOINTMENT_FINAL_DECISION_RECORDED_EVENT,
                        "decision": new_status,
                        "decided_by": _safe_actor_display(actor),
                        "stage_action_id": str(stage_action.id),
                    },
                )

    return appointment
