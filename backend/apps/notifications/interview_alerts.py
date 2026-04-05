"""Interview email alerts for critical events."""

from __future__ import annotations

import logging

from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db.models import Q
from django.template import TemplateDoesNotExist
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


def _safe_render(template_name: str, context: dict, fallback: str) -> str:
    try:
        return render_to_string(template_name, context)
    except TemplateDoesNotExist:
        logger.warning("Email template '%s' is missing; using fallback content.", template_name)
        return fallback
    except Exception:
        logger.exception("Failed to render template '%s'.", template_name)
        return fallback


def _retry_with_backoff(task, exc: Exception, *, message: str):
    retries = int(getattr(task.request, "retries", 0))
    delay_seconds = min(300, 30 * (retries + 1))
    logger.exception(message)
    raise task.retry(exc=exc, countdown=delay_seconds)


def _send_html_email(subject: str, html_template: str, text_template: str, context: dict, to: list[str]):
    if not to:
        logger.warning("No recipients found for alert '%s'.", subject)
        return

    html_content = _safe_render(html_template, context, context.get("summary", ""))
    text_content = _safe_render(text_template, context, context.get("summary", ""))

    email = EmailMultiAlternatives(
        subject=subject,
        body=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=to,
    )
    email.attach_alternative(html_content, "text/html")
    email.send()


def _get_response_analysis(exchange):
    # Legacy compatibility: older modules referenced `nonverbal_analysis`.
    return getattr(exchange, "video_analysis", None) or getattr(exchange, "nonverbal_analysis", None)


class InterviewAlertService:
    """Real-time email alerts for critical interview events."""

    HIGH_STRESS_THRESHOLD = 80
    CRITICAL_FLAG_COUNT = 3
    LOW_RESPONSE_QUALITY = 40

    @staticmethod
    def check_and_send_alerts(exchange, session):
        """Check alert conditions after each interview response."""
        alerts_triggered = []
        analysis = _get_response_analysis(exchange)

        if analysis and (analysis.stress_level or 0) >= InterviewAlertService.HIGH_STRESS_THRESHOLD:
            send_high_deception_alert.delay(session.id, exchange.id)
            alerts_triggered.append("high_deception")

        critical_flags = session.case.interrogation_flags.filter(
            severity="critical",
            status__in=["pending", "addressed"],
        ).count()
        if critical_flags >= InterviewAlertService.CRITICAL_FLAG_COUNT:
            send_critical_flags_alert.delay(session.id)
            alerts_triggered.append("critical_flags")

        if (
            exchange.response_quality_score is not None
            and exchange.response_quality_score < InterviewAlertService.LOW_RESPONSE_QUALITY
        ):
            send_poor_response_alert.delay(session.id, exchange.id)
            alerts_triggered.append("poor_response")

        behavioral_indicators = getattr(analysis, "behavioral_indicators", []) if analysis else []
        if len(behavioral_indicators) >= 3:
            send_behavioral_alert.delay(session.id, exchange.id)
            alerts_triggered.append("behavioral_red_flags")

        return alerts_triggered

    @staticmethod
    def send_interview_complete_summary(session_id):
        send_completion_summary.delay(session_id)


@shared_task(bind=True, max_retries=3)
def send_high_deception_alert(self, session_id, exchange_id):
    """Send alert when very high stress/deception indicators are detected."""
    from apps.interviews.models import InterviewResponse, InterviewSession

    try:
        session = InterviewSession.objects.get(id=session_id)
    except InterviewSession.DoesNotExist:
        logger.warning("Skipping high deception alert: InterviewSession %s not found.", session_id)
        return {"success": False, "error": f"InterviewSession {session_id} not found"}

    try:
        exchange = InterviewResponse.objects.get(id=exchange_id)
    except InterviewResponse.DoesNotExist:
        logger.warning("Skipping high deception alert: InterviewResponse %s not found.", exchange_id)
        return {"success": False, "error": f"InterviewResponse {exchange_id} not found"}

    analysis = _get_response_analysis(exchange)
    internal_emails = get_internal_emails(organization_id=getattr(session.case, "organization_id", None))

    context = {
        "session_id": session.session_id,
        "applicant_name": session.case.applicant.get_full_name(),
        "deception_score": getattr(analysis, "stress_level", 0),
        "question": getattr(exchange.question, "question_text", ""),
        "transcript": exchange.transcript,
        "behavioral_flags": getattr(analysis, "behavioral_indicators", []),
        "eye_contact": getattr(analysis, "eye_contact_percentage", None),
        "stress_level": getattr(analysis, "stress_level", None),
        "dashboard_url": f"{settings.FRONTEND_URL}/admin/interviews/{session.session_id}",
        "summary": "High stress pattern detected in interview response.",
    }

    try:
        _send_html_email(
            subject=f"HIGH INTERVIEW ALERT - {session.session_id}",
            html_template="emails/high_deception_alert.html",
            text_template="emails/high_deception_alert.txt",
            context=context,
            to=internal_emails,
        )
    except Exception as exc:
        _retry_with_backoff(self, exc, message="Failed to send high deception/stress alert.")

    logger.info("High deception/stress alert sent for session %s", session.session_id)
    return {"success": True, "session_id": session_id, "exchange_id": exchange_id}


@shared_task(bind=True, max_retries=3)
def send_critical_flags_alert(self, session_id):
    """Alert when multiple critical flags remain unresolved."""
    from apps.interviews.models import InterviewSession

    try:
        session = InterviewSession.objects.get(id=session_id)
    except InterviewSession.DoesNotExist:
        logger.warning("Skipping critical flags alert: InterviewSession %s not found.", session_id)
        return {"success": False, "error": f"InterviewSession {session_id} not found"}

    critical_flags = session.case.interrogation_flags.filter(
        severity="critical",
        status__in=["pending", "addressed"],
    )
    internal_emails = get_internal_emails(organization_id=getattr(session.case, "organization_id", None))

    context = {
        "session_id": session.session_id,
        "applicant_name": session.case.applicant.get_full_name(),
        "critical_flags": [
            {
                "type": flag.flag_type,
                "context": flag.description,
                "status": flag.status,
            }
            for flag in critical_flags
        ],
        "flag_count": critical_flags.count(),
        "dashboard_url": f"{settings.FRONTEND_URL}/admin/interviews/{session.session_id}",
        "summary": "Multiple critical flags need manual review.",
    }

    try:
        _send_html_email(
            subject=f"CRITICAL FLAGS - {session.session_id}",
            html_template="emails/critical_flags_alert.html",
            text_template="emails/critical_flags_alert.txt",
            context=context,
            to=internal_emails,
        )
    except Exception as exc:
        _retry_with_backoff(self, exc, message="Failed to send critical flags alert.")

    logger.info("Critical flags alert sent for session %s", session.session_id)
    return {"success": True, "session_id": session_id}


@shared_task(bind=True, max_retries=3)
def send_poor_response_alert(self, session_id, exchange_id):
    """Alert for very poor response quality."""
    from apps.interviews.models import InterviewResponse, InterviewSession

    try:
        session = InterviewSession.objects.get(id=session_id)
    except InterviewSession.DoesNotExist:
        logger.warning("Skipping poor response alert: InterviewSession %s not found.", session_id)
        return {"success": False, "error": f"InterviewSession {session_id} not found"}

    try:
        exchange = InterviewResponse.objects.get(id=exchange_id)
    except InterviewResponse.DoesNotExist:
        logger.warning("Skipping poor response alert: InterviewResponse %s not found.", exchange_id)
        return {"success": False, "error": f"InterviewResponse {exchange_id} not found"}

    internal_emails = get_internal_emails(organization_id=getattr(session.case, "organization_id", None))

    context = {
        "session_id": session.session_id,
        "applicant_name": session.case.applicant.get_full_name(),
        "question": getattr(exchange.question, "question_text", ""),
        "transcript": exchange.transcript,
        "quality_score": exchange.response_quality_score,
        "relevance_score": exchange.relevance_score,
        "dashboard_url": f"{settings.FRONTEND_URL}/admin/interviews/{session.session_id}",
        "summary": "Low-quality answer detected in active interview session.",
    }

    try:
        _send_html_email(
            subject=f"POOR RESPONSE QUALITY - {session.session_id}",
            html_template="emails/poor_response_alert.html",
            text_template="emails/poor_response_alert.txt",
            context=context,
            to=internal_emails,
        )
    except Exception as exc:
        _retry_with_backoff(self, exc, message="Failed to send poor response alert.")
    return {"success": True, "session_id": session_id, "exchange_id": exchange_id}


@shared_task(bind=True, max_retries=3)
def send_behavioral_alert(self, session_id, exchange_id):
    """Alert for multiple behavioral red flags in a single response."""
    from apps.interviews.models import InterviewResponse, InterviewSession

    try:
        session = InterviewSession.objects.get(id=session_id)
    except InterviewSession.DoesNotExist:
        logger.warning("Skipping behavioral alert: InterviewSession %s not found.", session_id)
        return {"success": False, "error": f"InterviewSession {session_id} not found"}

    try:
        exchange = InterviewResponse.objects.get(id=exchange_id)
    except InterviewResponse.DoesNotExist:
        logger.warning("Skipping behavioral alert: InterviewResponse %s not found.", exchange_id)
        return {"success": False, "error": f"InterviewResponse {exchange_id} not found"}

    analysis = _get_response_analysis(exchange)
    internal_emails = get_internal_emails(organization_id=getattr(session.case, "organization_id", None))

    context = {
        "session_id": session.session_id,
        "applicant_name": session.case.applicant.get_full_name(),
        "question": getattr(exchange.question, "question_text", ""),
        "red_flags": getattr(analysis, "behavioral_indicators", []),
        "eye_contact": getattr(analysis, "eye_contact_percentage", None),
        "fidgeting": getattr(analysis, "fidgeting_detected", False),
        "stress_indicators": getattr(analysis, "behavioral_indicators", []),
        "dashboard_url": f"{settings.FRONTEND_URL}/admin/interviews/{session.session_id}",
        "summary": "Behavioral indicators exceeded alert threshold.",
    }

    try:
        _send_html_email(
            subject=f"BEHAVIORAL RED FLAGS - {session.session_id}",
            html_template="emails/behavioral_alert.html",
            text_template="emails/behavioral_alert.txt",
            context=context,
            to=internal_emails,
        )
    except Exception as exc:
        _retry_with_backoff(self, exc, message="Failed to send behavioral alert.")
    return {"success": True, "session_id": session_id, "exchange_id": exchange_id}


@shared_task(bind=True, max_retries=3)
def send_completion_summary(self, session_id):
    """Send comprehensive summary when interview completes."""
    from apps.interviews.models import InterviewSession

    try:
        session = InterviewSession.objects.get(id=session_id)
    except InterviewSession.DoesNotExist:
        logger.warning("Skipping completion summary: InterviewSession %s not found.", session_id)
        return {"success": False, "error": f"InterviewSession {session_id} not found"}

    internal_emails = get_internal_emails(organization_id=getattr(session.case, "organization_id", None))

    responses = session.responses.select_related("question").all()
    flags = session.case.interrogation_flags.all()

    context = {
        "session_id": session.session_id,
        "applicant_name": session.case.applicant.get_full_name(),
        "overall_score": session.overall_score,
        "confidence_score": session.confidence_score,
        "consistency_score": session.consistency_score,
        "duration_minutes": round((session.duration_seconds or 0) / 60, 1),
        "questions_asked": session.total_questions_asked,
        "recommendation": session.interview_summary,
        "summary": session.interview_summary,
        "red_flags": session.red_flags_detected,
        "flags_resolved": flags.filter(status="resolved").count(),
        "flags_unresolved": flags.exclude(status__in=["resolved", "dismissed"]).count(),
        "avg_deception": calculate_avg_deception(responses),
        "dashboard_url": f"{settings.FRONTEND_URL}/admin/interviews/{session.session_id}",
        "playback_url": f"{settings.FRONTEND_URL}/admin/playback/{session.session_id}",
    }

    try:
        _send_html_email(
            subject=f"INTERVIEW COMPLETE - {session.session_id}",
            html_template="emails/completion_summary.html",
            text_template="emails/completion_summary.txt",
            context=context,
            to=internal_emails,
        )
    except Exception as exc:
        _retry_with_backoff(self, exc, message="Failed to send completion summary.")

    logger.info("Completion summary sent for session %s", session.session_id)
    return {"success": True, "session_id": session_id}


def get_internal_emails(*, organization_id=None):
    """
    Get active internal workflow actor emails for interview alerts.

    Legacy function name retained for compatibility with existing imports.
    """
    from apps.users.models import User
    from apps.core.permissions import is_government_workflow_operator, is_platform_admin_user

    # organization_id param kept for API compatibility; schema isolation handles tenant scoping.
    users = User.objects.filter(is_active=True).filter(
        Q(organization_memberships__is_active=True)
        | Q(user_type="admin")
        | Q(is_superuser=True)
    ).distinct().only("id", "email", "user_type", "is_superuser")

    recipients: list[str] = []
    for user in users:
        if not user.email:
            continue
        if is_platform_admin_user(user) or is_government_workflow_operator(user, organization_id=organization_id):
            recipients.append(user.email)
    return recipients


def calculate_avg_deception(responses):
    """Estimate average deception proxy using stress-level signals."""
    stress_scores = []
    for response in responses:
        analysis = _get_response_analysis(response)
        if analysis and analysis.stress_level is not None:
            stress_scores.append(float(analysis.stress_level))

    if not stress_scores:
        return 0.0
    return round(sum(stress_scores) / len(stress_scores), 1)


