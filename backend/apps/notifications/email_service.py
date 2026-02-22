"""Interview email alerts for critical events."""

from __future__ import annotations

import logging

from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


def _safe_render(template_name: str, context: dict, fallback: str) -> str:
    try:
        return render_to_string(template_name, context)
    except Exception:
        logger.exception("Failed to render template '%s'.", template_name)
        return fallback


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


@shared_task(max_retries=3)
def send_high_deception_alert(session_id, exchange_id):
    """Send alert when very high stress/deception indicators are detected."""
    from apps.interviews.models import InterviewResponse, InterviewSession

    try:
        session = InterviewSession.objects.get(id=session_id)
        exchange = InterviewResponse.objects.get(id=exchange_id)
        analysis = _get_response_analysis(exchange)
        hr_emails = get_hr_manager_emails()

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

        _send_html_email(
            subject=f"HIGH INTERVIEW ALERT - {session.session_id}",
            html_template="emails/high_deception_alert.html",
            text_template="emails/high_deception_alert.txt",
            context=context,
            to=hr_emails,
        )
        logger.info("High deception/stress alert sent for session %s", session.session_id)
    except Exception:
        logger.exception("Failed to send high deception/stress alert.")
        raise


@shared_task(max_retries=3)
def send_critical_flags_alert(session_id):
    """Alert when multiple critical flags remain unresolved."""
    from apps.interviews.models import InterviewSession

    try:
        session = InterviewSession.objects.get(id=session_id)
        critical_flags = session.case.interrogation_flags.filter(
            severity="critical",
            status__in=["pending", "addressed"],
        )
        hr_emails = get_hr_manager_emails()

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

        _send_html_email(
            subject=f"CRITICAL FLAGS - {session.session_id}",
            html_template="emails/critical_flags_alert.html",
            text_template="emails/critical_flags_alert.txt",
            context=context,
            to=hr_emails,
        )
        logger.info("Critical flags alert sent for session %s", session.session_id)
    except Exception:
        logger.exception("Failed to send critical flags alert.")
        raise


@shared_task(max_retries=3)
def send_poor_response_alert(session_id, exchange_id):
    """Alert for very poor response quality."""
    from apps.interviews.models import InterviewResponse, InterviewSession

    try:
        session = InterviewSession.objects.get(id=session_id)
        exchange = InterviewResponse.objects.get(id=exchange_id)
        hr_emails = get_hr_manager_emails()

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

        _send_html_email(
            subject=f"POOR RESPONSE QUALITY - {session.session_id}",
            html_template="emails/poor_response_alert.html",
            text_template="emails/poor_response_alert.txt",
            context=context,
            to=hr_emails,
        )
    except Exception:
        logger.exception("Failed to send poor response alert.")
        raise


@shared_task(max_retries=3)
def send_behavioral_alert(session_id, exchange_id):
    """Alert for multiple behavioral red flags in a single response."""
    from apps.interviews.models import InterviewResponse, InterviewSession

    try:
        session = InterviewSession.objects.get(id=session_id)
        exchange = InterviewResponse.objects.get(id=exchange_id)
        analysis = _get_response_analysis(exchange)
        hr_emails = get_hr_manager_emails()

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

        _send_html_email(
            subject=f"BEHAVIORAL RED FLAGS - {session.session_id}",
            html_template="emails/behavioral_alert.html",
            text_template="emails/behavioral_alert.txt",
            context=context,
            to=hr_emails,
        )
    except Exception:
        logger.exception("Failed to send behavioral alert.")
        raise


@shared_task(max_retries=3)
def send_completion_summary(session_id):
    """Send comprehensive summary when interview completes."""
    from apps.interviews.models import InterviewSession

    try:
        session = InterviewSession.objects.get(id=session_id)
        hr_emails = get_hr_manager_emails()

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

        _send_html_email(
            subject=f"INTERVIEW COMPLETE - {session.session_id}",
            html_template="emails/completion_summary.html",
            text_template="emails/completion_summary.txt",
            context=context,
            to=hr_emails,
        )
        logger.info("Completion summary sent for session %s", session.session_id)
    except Exception:
        logger.exception("Failed to send completion summary.")
        raise


def get_hr_manager_emails():
    """Get active HR/admin emails for interview alerts."""
    from apps.authentication.models import User

    hr_users = User.objects.filter(
        user_type__in=["hr_manager", "admin"],
        is_active=True,
    ).only("email")
    return [user.email for user in hr_users if user.email]


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

