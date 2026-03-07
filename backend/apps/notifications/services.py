"""Notification delivery service (in-app + email audit records)."""

from __future__ import annotations

import json
import logging
from typing import Any

from django.conf import settings
from django.core.mail import send_mail
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Q
from django.template.loader import render_to_string
from django.utils.html import strip_tags

from apps.notifications.models import Notification

logger = logging.getLogger(__name__)

try:
    from twilio.rest import Client as TwilioClient
except Exception:  # pragma: no cover - optional dependency
    TwilioClient = None  # type: ignore[assignment]

_twilio_client = None
if TwilioClient and getattr(settings, "TWILIO_ACCOUNT_SID", None) and getattr(settings, "TWILIO_AUTH_TOKEN", None):
    try:
        _twilio_client = TwilioClient(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
    except Exception:
        logger.exception("Failed to initialize Twilio client; SMS notifications will be unavailable.")


class NotificationService:
    """Service methods used by workflow tasks to notify users."""

    APPOINTMENT_EVENT_TEMPLATES: dict[str, dict[str, str]] = {
        "appointment_nomination_created": {
            "subject": "Nomination Created: {position_title}",
            "message": "A nomination has been created for {nominee_name} to {position_title}.",
            "priority": "high",
        },
        "appointment_moved_to_intake_check": {
            "subject": "Appointment Intake Check Started: {position_title}",
            "message": "Appointment nomination for {nominee_name} entered intake check.",
            "priority": "high",
        },
        "appointment_moved_to_under_vetting": {
            "subject": "Appointment Under Vetting: {position_title}",
            "message": "Appointment nomination for {nominee_name} moved to under vetting.",
            "priority": "high",
        },
        "appointment_moved_to_committee_review": {
            "subject": "Appointment in Committee Review: {position_title}",
            "message": "Appointment nomination for {nominee_name} moved to committee review.",
            "priority": "high",
        },
        "appointment_moved_to_approval_chain": {
            "subject": "Appointment in Approval Chain: {position_title}",
            "message": "Appointment nomination for {nominee_name} moved to approval chain.",
            "priority": "high",
        },
        "appointment_approved": {
            "subject": "Appointment Approved: {position_title}",
            "message": "Appointment nomination for {nominee_name} was approved.",
            "priority": "high",
        },
        "appointment_rejected": {
            "subject": "Appointment Rejected: {position_title}",
            "message": "Appointment nomination for {nominee_name} was rejected.",
            "priority": "high",
        },
        "appointment_appointed": {
            "subject": "Appointment Finalized: {position_title}",
            "message": "{nominee_name} has been formally appointed to {position_title}.",
            "priority": "urgent",
        },
        "appointment_published": {
            "subject": "Appointment Published: {position_title}",
            "message": "Appointment record for {nominee_name} has been published to gazette/public feed.",
            "priority": "high",
        },
        "appointment_revoked": {
            "subject": "Appointment Publication Revoked: {position_title}",
            "message": "Appointment publication for {nominee_name} has been revoked/unpublished.",
            "priority": "urgent",
        },
    }

    @staticmethod
    def _json_sanitize(value: Any) -> Any:
        """Best-effort JSON sanitization for metadata payloads."""
        try:
            json.dumps(value, cls=DjangoJSONEncoder)
            return value
        except TypeError:
            pass

        if isinstance(value, dict):
            return {str(key): NotificationService._json_sanitize(item) for key, item in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [NotificationService._json_sanitize(item) for item in value]
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
        if hasattr(value, "isoformat"):
            try:
                return value.isoformat()
            except Exception:
                return str(value)
        return str(value)

    @staticmethod
    def _normalize_metadata(metadata: Any | None) -> dict[str, Any]:
        """Normalize metadata to a JSON-safe dict for Notification.metadata."""
        sanitized = NotificationService._json_sanitize(metadata if metadata is not None else {})
        if isinstance(sanitized, dict):
            return sanitized
        return {"value": sanitized}

    @staticmethod
    def _resolve_idempotency_key(
        metadata: dict[str, Any],
        idempotency_key: str | None = None,
    ) -> str | None:
        if idempotency_key:
            return str(idempotency_key)
        value = metadata.get("idempotency_key")
        if value in (None, ""):
            return None
        return str(value)

    @staticmethod
    def _metadata_with_idempotency(
        metadata: Any | None,
        idempotency_key: str | None = None,
    ) -> tuple[dict[str, Any], str | None]:
        normalized = NotificationService._normalize_metadata(metadata)
        resolved = NotificationService._resolve_idempotency_key(normalized, idempotency_key)
        if resolved:
            normalized["idempotency_key"] = resolved
        return normalized, resolved

    @staticmethod
    def _find_existing_by_idempotency(
        *,
        recipient,
        notification_type: str,
        idempotency_key: str | None,
    ) -> Notification | None:
        if not idempotency_key:
            return None
        return (
            Notification.objects.filter(
                recipient=recipient,
                notification_type=notification_type,
                metadata__idempotency_key=idempotency_key,
            )
            .order_by("-created_at")
            .first()
        )

    @staticmethod
    def _create_in_app_notification(
        *,
        recipient,
        subject: str,
        message: str,
        related_case=None,
        related_interview=None,
        metadata: Any | None = None,
        priority: str = "normal",
        idempotency_key: str | None = None,
    ) -> Notification:
        metadata_payload, resolved_key = NotificationService._metadata_with_idempotency(
            metadata,
            idempotency_key,
        )
        existing = NotificationService._find_existing_by_idempotency(
            recipient=recipient,
            notification_type="in_app",
            idempotency_key=resolved_key,
        )
        if existing:
            return existing

        return Notification.objects.create(
            recipient=recipient,
            subject=subject,
            message=message,
            notification_type="in_app",
            status="sent",
            priority=priority,
            related_case=related_case,
            related_interview=related_interview,
            metadata=metadata_payload,
        )

    @staticmethod
    def _send_email_notification(
        *,
        recipient,
        subject: str,
        fallback_message: str,
        template_name: str | None = None,
        context: dict[str, Any] | None = None,
        related_case=None,
        related_interview=None,
        metadata: Any | None = None,
        priority: str = "normal",
        idempotency_key: str | None = None,
    ) -> Notification | None:
        email = getattr(recipient, "email", "")
        if not email:
            return None

        metadata_payload, resolved_key = NotificationService._metadata_with_idempotency(
            metadata,
            idempotency_key,
        )
        existing = NotificationService._find_existing_by_idempotency(
            recipient=recipient,
            notification_type="email",
            idempotency_key=resolved_key,
        )
        if existing:
            return existing

        email_notification = Notification.objects.create(
            recipient=recipient,
            subject=subject,
            message=fallback_message,
            notification_type="email",
            status="pending",
            priority=priority,
            related_case=related_case,
            related_interview=related_interview,
            email_to=email,
            metadata=metadata_payload,
        )

        html_message = None
        plain_message = fallback_message
        if template_name:
            try:
                html_message = render_to_string(template_name, context or {})
                plain_message = strip_tags(html_message) or fallback_message
            except Exception:
                logger.exception("Failed to render email template '%s'.", template_name)

        try:
            send_mail(
                subject=subject,
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                html_message=html_message,
                fail_silently=False,
            )
            email_notification.mark_sent()
            logger.info("Email notification sent to %s", email)
        except Exception as exc:
            email_notification.mark_failed(str(exc))
            logger.exception("Failed to send email notification to %s", email)

        return email_notification


    @staticmethod
    def _send_sms_notification(phone_number: str, message: str) -> bool:
        if not _twilio_client:
            logger.warning("Twilio client not configured; cannot send SMS.")
            return False
        try:
            _twilio_client.messages.create(
                body=message,
                from_=settings.TWILIO_PHONE_NUMBER,
                to=phone_number,
            )
            logger.info("SMS notification sent to %s", phone_number)
            return True
        except Exception as exc:
            logger.exception("Failed to send SMS notification to %s", phone_number)
            return False

    @staticmethod
    def _send_sms_notification_record(
        *,
        recipient,
        subject: str,
        message: str,
        related_case=None,
        related_interview=None,
        metadata: Any | None = None,
        priority: str = "normal",
        idempotency_key: str | None = None,
    ) -> Notification | None:
        if not bool(getattr(settings, "NOTIFICATIONS_SMS_ENABLED", False)):
            return None

        phone_number = str(getattr(recipient, "phone_number", "") or "").strip()
        if not phone_number:
            return None

        metadata_payload, resolved_key = NotificationService._metadata_with_idempotency(
            metadata,
            idempotency_key,
        )
        existing = NotificationService._find_existing_by_idempotency(
            recipient=recipient,
            notification_type="sms",
            idempotency_key=resolved_key,
        )
        if existing:
            return existing

        sms_notification = Notification.objects.create(
            recipient=recipient,
            subject=subject,
            message=message,
            notification_type="sms",
            status="pending",
            priority=priority,
            related_case=related_case,
            related_interview=related_interview,
            metadata=metadata_payload,
        )

        delivery_successful = NotificationService._send_sms_notification(
            phone_number,
            message,
        )
        if delivery_successful:
            sms_notification.mark_sent()
        else:
            sms_notification.mark_failed("SMS delivery failed")
        return sms_notification


    @staticmethod
    def _get_case_and_recipient(application):
        case = application
        recipient = getattr(case, "applicant", None)
        return case, recipient

    @staticmethod
    def _appointment_event_group_names(*, event_type: str, stage_role: str = "") -> set[str]:
        mapping = {
            "appointment_nomination_created": {"vetting_officer"},
            "appointment_moved_to_intake_check": {"vetting_officer"},
            "appointment_moved_to_under_vetting": {"vetting_officer"},
            "appointment_moved_to_committee_review": {"committee_member"},
            "appointment_moved_to_approval_chain": {"appointing_authority"},
            "appointment_approved": {"appointing_authority"},
            "appointment_rejected": {"appointing_authority"},
            "appointment_appointed": {"appointing_authority", "registry_admin"},
            "appointment_published": {"appointing_authority", "registry_admin"},
            "appointment_revoked": {"appointing_authority", "registry_admin"},
        }
        group_names = set(mapping.get(event_type, set()))
        normalized_stage_role = str(stage_role or "").strip().lower()
        if normalized_stage_role:
            group_names.add(normalized_stage_role)
        return group_names

    @staticmethod
    def _appointment_notification_recipients(*, appointment, event_type: str, actor=None, stage_role: str = ""):
        from apps.authentication.models import User

        recipient_ids = set()
        for candidate_user in (
            getattr(appointment, "nominated_by_user", None),
            getattr(getattr(appointment, "appointment_exercise", None), "initiated_by", None),
            getattr(appointment, "final_decision_by_user", None),
            actor,
        ):
            if candidate_user is None:
                continue
            if not getattr(candidate_user, "is_active", True):
                continue
            recipient_ids.add(candidate_user.id)

        group_names = NotificationService._appointment_event_group_names(
            event_type=event_type,
            stage_role=stage_role,
        )
        if group_names:
            recipient_ids.update(
                User.objects.filter(is_active=True, groups__name__in=group_names).values_list("id", flat=True)
            )

        recipient_ids.update(
            User.objects.filter(is_active=True)
            .filter(Q(user_type="admin") | Q(is_staff=True) | Q(is_superuser=True))
            .values_list("id", flat=True)
        )

        if actor is not None:
            recipient_ids.discard(getattr(actor, "id", None))

        if not recipient_ids:
            return User.objects.none()
        return User.objects.filter(id__in=recipient_ids, is_active=True).distinct()

    @staticmethod
    def send_appointment_lifecycle_notification(
        *,
        appointment,
        event_type: str,
        actor=None,
        previous_status: str = "",
        new_status: str = "",
        stage=None,
        metadata: Any | None = None,
        idempotency_key: str | None = None,
    ):
        """Notify government actors about appointment lifecycle events."""
        if appointment is None:
            return None

        template = NotificationService.APPOINTMENT_EVENT_TEMPLATES.get(event_type)
        if template is None:
            logger.warning("Unsupported appointment lifecycle notification event: %s", event_type)
            return None

        recipients = NotificationService._appointment_notification_recipients(
            appointment=appointment,
            event_type=event_type,
            actor=actor,
            stage_role=getattr(stage, "required_role", ""),
        )
        if not recipients.exists():
            return None

        position_title = str(getattr(getattr(appointment, "position", None), "title", "") or "appointment")
        nominee_name = str(getattr(getattr(appointment, "nominee", None), "full_name", "") or "nominee")
        subject = template["subject"].format(position_title=position_title, nominee_name=nominee_name)
        message = template["message"].format(position_title=position_title, nominee_name=nominee_name)
        priority = template.get("priority", "normal")

        event_metadata = {
            "event_type": event_type,
            "appointment_id": str(getattr(appointment, "id", "")),
            "position_id": str(getattr(appointment, "position_id", "")),
            "position_title": position_title,
            "nominee_id": str(getattr(appointment, "nominee_id", "")),
            "nominee_name": nominee_name,
            "previous_status": str(previous_status or ""),
            "new_status": str(new_status or ""),
            "stage_id": str(getattr(stage, "id", "")) if stage is not None else "",
            "stage_name": str(getattr(stage, "name", "")) if stage is not None else "",
        }
        event_metadata.update(NotificationService._normalize_metadata(metadata))
        event_idempotency_key = idempotency_key or (
            "appointment"
            f":{event_metadata['appointment_id']}"
            f":{event_type}"
            f":{event_metadata['previous_status']}"
            f":{event_metadata['new_status']}"
            f":{event_metadata['stage_id']}"
        )

        related_case = getattr(appointment, "vetting_case", None)
        for recipient in recipients:
            NotificationService._create_in_app_notification(
                recipient=recipient,
                subject=subject,
                message=message,
                related_case=related_case,
                metadata=event_metadata,
                priority=priority,
                idempotency_key=event_idempotency_key,
            )
            NotificationService._send_email_notification(
                recipient=recipient,
                subject=subject,
                fallback_message=message,
                related_case=related_case,
                metadata=event_metadata,
                priority=priority,
                idempotency_key=event_idempotency_key,
            )
            NotificationService._send_sms_notification_record(
                recipient=recipient,
                subject=subject,
                message=message,
                related_case=related_case,
                metadata=event_metadata,
                priority=priority,
                idempotency_key=event_idempotency_key,
            )
        return True

    @staticmethod
    def send_application_submitted(application):
        """Notify candidate when a vetting case is submitted."""
        case, recipient = NotificationService._get_case_and_recipient(application)
        if recipient is None:
            logger.warning("Skipping send_application_submitted: case has no applicant.")
            return None

        subject = "Application Submitted - Online Vetting System"
        message = f"Your application {case.case_id} has been submitted and is pending review."
        metadata = {"case_id": case.case_id, "event_type": "application_submitted"}

        NotificationService._create_in_app_notification(
            recipient=recipient,
            subject=subject,
            message=message,
            related_case=case,
            metadata=metadata,
        )
        NotificationService._send_email_notification(
            recipient=recipient,
            subject=subject,
            fallback_message=message,
            template_name="emails/application_submitted.html",
            context={"user": recipient, "case_id": case.case_id},
            related_case=case,
            metadata=metadata,
        )
        NotificationService._send_sms_notification_record(
            recipient=recipient,
            subject=subject,
            message=message,
            related_case=case,
            metadata=metadata,
        )
        return True

    @staticmethod
    def send_document_verified(document):
        """Notify candidate when a document verification is completed."""
        case = document.case
        recipient = case.applicant
        document_type_display = (
            document.get_document_type_display()
            if hasattr(document, "get_document_type_display")
            else str(document.document_type)
        )
        document_status = getattr(document, "status", "")

        subject = "Document Verification Update - Online Vetting System"
        message = f"Your {document_type_display} status is now '{document_status}'."
        metadata = {
            "case_id": case.case_id,
            "event_type": "document_verified",
            "document_id": document.id,
            "document_type": document.document_type,
            "document_status": document_status,
        }

        NotificationService._create_in_app_notification(
            recipient=recipient,
            subject=subject,
            message=message,
            related_case=case,
            metadata=metadata,
        )
        NotificationService._send_email_notification(
            recipient=recipient,
            subject=subject,
            fallback_message=message,
            template_name="emails/document_verified.html",
            context={
                "user": recipient,
                "case_id": case.case_id,
                "document_type": document_type_display,
                "status": document_status,
            },
            related_case=case,
            metadata=metadata,
        )
        NotificationService._send_sms_notification_record(
            recipient=recipient,
            subject=subject,
            message=message,
            related_case=case,
            metadata=metadata,
        )
        return True

    @staticmethod
    def send_status_updated(application, old_status, new_status):
        """Notify candidate when vetting-case status changes."""
        case, recipient = NotificationService._get_case_and_recipient(application)
        if recipient is None:
            logger.warning("Skipping send_status_updated: case has no applicant.")
            return None

        subject = f"Application Status Update - {new_status}"
        message = (
            f"Your application {case.case_id} status changed from {old_status} to {new_status}."
        )
        metadata = {
            "case_id": case.case_id,
            "event_type": "status_updated",
            "old_status": old_status,
            "new_status": new_status,
        }

        NotificationService._create_in_app_notification(
            recipient=recipient,
            subject=subject,
            message=message,
            related_case=case,
            metadata=metadata,
        )
        NotificationService._send_email_notification(
            recipient=recipient,
            subject=subject,
            fallback_message=message,
            template_name="emails/status_updated.html",
            context={
                "user": recipient,
                "case_id": case.case_id,
                "old_status": old_status,
                "new_status": new_status,
            },
            related_case=case,
            metadata=metadata,
        )
        NotificationService._send_sms_notification_record(
            recipient=recipient,
            subject=subject,
            message=message,
            related_case=case,
            metadata=metadata,
        )
        return True

    @staticmethod
    def send_interview_scheduled(session):
        """Notify candidate when an interview session is created/scheduled."""
        case = getattr(session, "case", None)
        if case is None:
            logger.warning("Skipping send_interview_scheduled: session has no case.")
            return None

        recipient = getattr(case, "applicant", None)
        if recipient is None:
            logger.warning("Skipping send_interview_scheduled: case has no applicant.")
            return None

        session_reference = getattr(session, "session_id", "") or str(getattr(session, "id", ""))
        subject = "Interview Session Scheduled - Online Vetting System"
        message = (
            f"Your interview session for application {case.case_id} has been scheduled. "
            f"Session reference: {session_reference}."
        )
        metadata = {
            "case_id": case.case_id,
            "event_type": "interview_scheduled",
            "interview_session_id": str(getattr(session, "id", "")),
            "interview_session_code": session_reference,
            "interview_url": f"/interview/interrogation/{case.case_id}",
            "case_url": f"/applications/{case.case_id}",
        }
        idempotency_key = (
            f"interview_scheduled:{getattr(session, 'id', '')}:{case.case_id}"
        )

        NotificationService._create_in_app_notification(
            recipient=recipient,
            subject=subject,
            message=message,
            related_case=case,
            related_interview=session,
            metadata=metadata,
            priority="high",
            idempotency_key=idempotency_key,
        )
        NotificationService._send_email_notification(
            recipient=recipient,
            subject=subject,
            fallback_message=message,
            related_case=case,
            related_interview=session,
            metadata=metadata,
            priority="high",
            idempotency_key=idempotency_key,
        )
        NotificationService._send_sms_notification_record(
            recipient=recipient,
            subject=subject,
            message=message,
            related_case=case,
            related_interview=session,
            metadata=metadata,
            priority="high",
            idempotency_key=idempotency_key,
        )
        return True

    @staticmethod
    def send_evaluation_complete(application, evaluation):
        """Notify candidate when rubric evaluation is completed."""
        case, recipient = NotificationService._get_case_and_recipient(application)
        if recipient is None:
            logger.warning("Skipping send_evaluation_complete: case has no applicant.")
            return None

        score = evaluation.total_weighted_score
        recommendation = evaluation.final_decision
        passed = evaluation.passes_threshold

        score_text = f"{float(score):.1f}%" if score is not None else "N/A"
        subject = "Application Evaluation Complete"
        message = f"Your application {case.case_id} has been evaluated. Score: {score_text}."
        metadata = {
            "case_id": case.case_id,
            "event_type": "evaluation_complete",
            "evaluation_id": getattr(evaluation, "id", None),
            "score": score,
            "passed": passed,
            "recommendation": recommendation,
        }

        NotificationService._create_in_app_notification(
            recipient=recipient,
            subject=subject,
            message=message,
            related_case=case,
            metadata=metadata,
        )
        NotificationService._send_email_notification(
            recipient=recipient,
            subject=subject,
            fallback_message=message,
            template_name="emails/evaluation_complete.html",
            context={
                "user": recipient,
                "case_id": case.case_id,
                "overall_score": score,
                "passed": passed,
                "recommendation": recommendation,
            },
            related_case=case,
            metadata=metadata,
        )
        NotificationService._send_sms_notification_record(
            recipient=recipient,
            subject=subject,
            message=message,
            related_case=case,
            metadata=metadata,
        )
        return True

    @staticmethod
    def send_admin_notification(admin_user, notification_type, title, message, metadata=None):
        """Send notification to an admin/staff recipient."""
        if admin_user is None:
            logger.warning("Skipping send_admin_notification: missing admin user.")
            return None

        extra_metadata = NotificationService._normalize_metadata(metadata)
        payload = {"event_type": notification_type, **extra_metadata}

        NotificationService._create_in_app_notification(
            recipient=admin_user,
            subject=title,
            message=message,
            metadata=payload,
            priority="high",
        )
        NotificationService._send_email_notification(
            recipient=admin_user,
            subject=f"[Admin] {title}",
            fallback_message=message,
            metadata=payload,
            priority="high",
        )
        NotificationService._send_sms_notification_record(
            recipient=admin_user,
            subject=f"[Admin] {title}",
            message=message,
            metadata=payload,
            priority="high",
        )
        return True

    @staticmethod
    def send_approval_notification(application):
        """Notify candidate when application is approved."""
        case, recipient = NotificationService._get_case_and_recipient(application)
        if recipient is None:
            logger.warning("Skipping send_approval_notification: case has no applicant.")
            return None

        subject = "Application Approved - Online Vetting System"
        message = f"Your application {case.case_id} has been approved."
        metadata = {"case_id": case.case_id, "event_type": "approval"}

        NotificationService._create_in_app_notification(
            recipient=recipient,
            subject=subject,
            message=message,
            related_case=case,
            metadata=metadata,
            priority="high",
        )
        NotificationService._send_email_notification(
            recipient=recipient,
            subject=subject,
            fallback_message=message,
            template_name="emails/application_approved.html",
            context={"user": recipient, "case_id": case.case_id},
            related_case=case,
            metadata=metadata,
            priority="high",
        )
        NotificationService._send_sms_notification_record(
            recipient=recipient,
            subject=subject,
            message=message,
            related_case=case,
            metadata=metadata,
            priority="high",
        )
        return True

    @staticmethod
    def send_rejection_notification(application, reason=None):
        """Notify candidate when application is rejected."""
        case, recipient = NotificationService._get_case_and_recipient(application)
        if recipient is None:
            logger.warning("Skipping send_rejection_notification: case has no applicant.")
            return None

        message = f"Your application {case.case_id} has been rejected."
        if reason:
            message = f"{message} Reason: {reason}"

        subject = "Application Status Update - Online Vetting System"
        metadata = {
            "case_id": case.case_id,
            "event_type": "rejection",
            "reason": reason,
        }

        NotificationService._create_in_app_notification(
            recipient=recipient,
            subject=subject,
            message=message,
            related_case=case,
            metadata=metadata,
            priority="high",
        )
        NotificationService._send_email_notification(
            recipient=recipient,
            subject=subject,
            fallback_message=message,
            template_name="emails/application_rejected.html",
            context={"user": recipient, "case_id": case.case_id, "reason": reason},
            related_case=case,
            metadata=metadata,
            priority="high",
        )
        NotificationService._send_sms_notification_record(
            recipient=recipient,
            subject=subject,
            message=message,
            related_case=case,
            metadata=metadata,
            priority="high",
        )
        return True
