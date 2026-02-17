# backend/apps/notifications/alert_service.py
from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from celery import shared_task
import logging

logger = logging.getLogger(__name__)


class InterviewAlertService:
    """
    Real-time email alerts for critical interview events
    """
    
    # Alert thresholds
    HIGH_DECEPTION_THRESHOLD = 80
    CRITICAL_FLAG_COUNT = 3
    LOW_RESPONSE_QUALITY = 40
    
    @staticmethod
    def check_and_send_alerts(exchange, session):
        """
        Check if any alerts should be triggered after each exchange
        Called after every applicant response
        """
        alerts_triggered = []
        
        # 1. High Deception Alert
        if hasattr(exchange, 'nonverbal_analysis'):
            nonverbal = exchange.nonverbal_analysis
            if nonverbal.deception_score >= InterviewAlertService.HIGH_DECEPTION_THRESHOLD:
                send_high_deception_alert.delay(session.id, exchange.id)
                alerts_triggered.append('high_deception')
        
        # 2. Critical Flags Alert
        critical_flags = session.interrogation_flags.filter(
            severity='critical',
            status__in=['pending', 'addressed']
        ).count()
        
        if critical_flags >= InterviewAlertService.CRITICAL_FLAG_COUNT:
            send_critical_flags_alert.delay(session.id)
            alerts_triggered.append('critical_flags')
        
        # 3. Poor Response Quality Alert
        if exchange.response_quality_score and exchange.response_quality_score < InterviewAlertService.LOW_RESPONSE_QUALITY:
            send_poor_response_alert.delay(session.id, exchange.id)
            alerts_triggered.append('poor_response')
        
        # 4. Behavioral Red Flags Alert
        if hasattr(exchange, 'nonverbal_analysis'):
            red_flags = exchange.nonverbal_analysis.behavioral_red_flags
            if len(red_flags) >= 3:  # 3+ red flags in single response
                send_behavioral_alert.delay(session.id, exchange.id)
                alerts_triggered.append('behavioral_red_flags')
        
        return alerts_triggered
    
    @staticmethod
    def send_interview_complete_summary(session_id):
        """Send comprehensive summary when interview completes"""
        send_completion_summary.delay(session_id)


@shared_task(max_retries=3)
def send_high_deception_alert(session_id, exchange_id):
    """Send immediate alert for high deception score"""
    
    from apps.interviews.models import DynamicInterviewSession, InterviewExchange
    
    try:
        session = DynamicInterviewSession.objects.get(id=session_id)
        exchange = InterviewExchange.objects.get(id=exchange_id)
        nonverbal = exchange.nonverbal_analysis
        
        # Get HR manager email
        hr_emails = get_hr_manager_emails()
        
        # Email context
        context = {
            'session_id': session.session_id,
            'applicant_name': session.application.applicant.full_name,
            'deception_score': nonverbal.deception_score,
            'question': exchange.question_text,
            'transcript': exchange.transcript,
            'behavioral_flags': nonverbal.behavioral_red_flags,
            'eye_contact': nonverbal.eye_contact_percentage,
            'stress_level': nonverbal.stress_level,
            'dashboard_url': f"{settings.FRONTEND_URL}/admin/interviews/{session.session_id}"
        }
        
        # Render email
        subject = f"🚨 HIGH DECEPTION ALERT - {session.session_id}"
        html_content = render_to_string('emails/high_deception_alert.html', context)
        text_content = render_to_string('emails/high_deception_alert.txt', context)
        
        # Send email
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=hr_emails
        )
        email.attach_alternative(html_content, "text/html")
        email.send()
        
        logger.info(f"High deception alert sent for session {session.session_id}")
        
    except Exception as e:
        logger.error(f"Failed to send deception alert: {str(e)}")
        raise


@shared_task(max_retries=3)
def send_critical_flags_alert(session_id):
    """Alert when multiple critical flags are unresolved"""
    
    from apps.interviews.models import DynamicInterviewSession
    
    try:
        session = DynamicInterviewSession.objects.get(id=session_id)
        critical_flags = session.interrogation_flags.filter(
            severity='critical',
            status__in=['pending', 'addressed']
        )
        
        hr_emails = get_hr_manager_emails()
        
        context = {
            'session_id': session.session_id,
            'applicant_name': session.application.applicant.full_name,
            'critical_flags': [
                {
                    'type': flag.flag_type,
                    'context': flag.context,
                    'status': flag.status
                }
                for flag in critical_flags
            ],
            'flag_count': critical_flags.count(),
            'dashboard_url': f"{settings.FRONTEND_URL}/admin/interviews/{session.session_id}"
        }
        
        subject = f"⚠️ CRITICAL FLAGS - {session.session_id}"
        html_content = render_to_string('emails/critical_flags_alert.html', context)
        text_content = render_to_string('emails/critical_flags_alert.txt', context)
        
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=hr_emails
        )
        email.attach_alternative(html_content, "text/html")
        email.send()
        
        logger.info(f"Critical flags alert sent for session {session.session_id}")
        
    except Exception as e:
        logger.error(f"Failed to send critical flags alert: {str(e)}")
        raise


@shared_task(max_retries=3)
def send_poor_response_alert(session_id, exchange_id):
    """Alert for very poor response quality"""
    
    from apps.interviews.models import DynamicInterviewSession, InterviewExchange
    
    try:
        session = DynamicInterviewSession.objects.get(id=session_id)
        exchange = InterviewExchange.objects.get(id=exchange_id)
        
        hr_emails = get_hr_manager_emails()
        
        context = {
            'session_id': session.session_id,
            'applicant_name': session.application.applicant.full_name,
            'question': exchange.question_text,
            'transcript': exchange.transcript,
            'quality_score': exchange.response_quality_score,
            'relevance_score': exchange.relevance_score,
            'dashboard_url': f"{settings.FRONTEND_URL}/admin/interviews/{session.session_id}"
        }
        
        subject = f"📉 Poor Response Quality - {session.session_id}"
        html_content = render_to_string('emails/poor_response_alert.html', context)
        text_content = render_to_string('emails/poor_response_alert.txt', context)
        
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=hr_emails
        )
        email.attach_alternative(html_content, "text/html")
        email.send()
        
    except Exception as e:
        logger.error(f"Failed to send poor response alert: {str(e)}")
        raise


@shared_task(max_retries=3)
def send_behavioral_alert(session_id, exchange_id):
    """Alert for multiple behavioral red flags"""
    
    from apps.interviews.models import DynamicInterviewSession, InterviewExchange
    
    try:
        session = DynamicInterviewSession.objects.get(id=session_id)
        exchange = InterviewExchange.objects.get(id=exchange_id)
        nonverbal = exchange.nonverbal_analysis
        
        hr_emails = get_hr_manager_emails()
        
        context = {
            'session_id': session.session_id,
            'applicant_name': session.application.applicant.full_name,
            'question': exchange.question_text,
            'red_flags': nonverbal.behavioral_red_flags,
            'eye_contact': nonverbal.eye_contact_percentage,
            'fidgeting': nonverbal.fidgeting_detected,
            'stress_indicators': nonverbal.stress_indicators,
            'dashboard_url': f"{settings.FRONTEND_URL}/admin/interviews/{session.session_id}"
        }
        
        subject = f"🚩 Behavioral Red Flags - {session.session_id}"
        html_content = render_to_string('emails/behavioral_alert.html', context)
        text_content = render_to_string('emails/behavioral_alert.txt', context)
        
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=hr_emails
        )
        email.attach_alternative(html_content, "text/html")
        email.send()
        
    except Exception as e:
        logger.error(f"Failed to send behavioral alert: {str(e)}")
        raise


@shared_task(max_retries=3)
def send_completion_summary(session_id):
    """Send comprehensive summary when interview completes"""
    
    from apps.interviews.models import DynamicInterviewSession
    
    try:
        session = DynamicInterviewSession.objects.get(id=session_id)
        
        hr_emails = get_hr_manager_emails()
        
        # Gather comprehensive data
        exchanges = session.exchanges.all()
        flags = session.interrogation_flags.all()
        
        context = {
            'session_id': session.session_id,
            'applicant_name': session.application.applicant.full_name,
            'overall_score': session.overall_score,
            'confidence_score': session.confidence_score,
            'consistency_score': session.consistency_score,
            'duration_minutes': round(session.duration_seconds / 60, 1),
            'questions_asked': session.current_question_number,
            'recommendation': session.recommendations,
            'summary': session.interview_summary,
            'red_flags': session.red_flags,
            'flags_resolved': flags.filter(status='resolved').count(),
            'flags_unresolved': flags.filter(status='unresolved').count(),
            'avg_deception': calculate_avg_deception(exchanges),
            'dashboard_url': f"{settings.FRONTEND_URL}/admin/interviews/{session.session_id}",
            'playback_url': f"{settings.FRONTEND_URL}/admin/playback/{session.session_id}"
        }
        
        subject = f"✅ Interview Complete - {session.session_id}"
        html_content = render_to_string('emails/completion_summary.html', context)
        text_content = render_to_string('emails/completion_summary.txt', context)
        
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=hr_emails
        )
        email.attach_alternative(html_content, "text/html")
        email.send()
        
        logger.info(f"Completion summary sent for session {session.session_id}")
        
    except Exception as e:
        logger.error(f"Failed to send completion summary: {str(e)}")
        raise


def get_hr_manager_emails():
    """Get list of HR manager emails to notify"""
    from apps.authentication.models import AdminUser
    
    hr_users = AdminUser.objects.filter(
        role__in=['hr_manager', 'admin', 'super_admin'],
        is_active=True
    )
    
    return [user.email for user in hr_users if user.email]


def calculate_avg_deception(exchanges):
    """Calculate average deception score across exchanges"""
    deception_scores = [
        ex.nonverbal_analysis.deception_score
        for ex in exchanges
        if hasattr(ex, 'nonverbal_analysis')
    ]
    
    return round(sum(deception_scores) / len(deception_scores), 1) if deception_scores else 0

