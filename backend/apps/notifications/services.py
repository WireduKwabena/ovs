# backend/apps/notifications/services.py
# From: Development Guide PDF - Notification Service COMPLETE

from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from apps.notifications.models import Notification
import logging

logger = logging.getLogger(__name__)

class NotificationService:
    """
    Service for sending notifications (email + in-app)
    From: Development Guide PDF
    COMPLETE IMPLEMENTATION
    """
    
    @staticmethod
    def send_application_submitted(application):
        """
        Send notification when application is submitted
        From: Development Guide PDF
        """
        user = application.applicant
        
        # Create in-app notification
        Notification.objects.create(
            user=user,
            notification_type='application_submitted',
            title='Application Submitted Successfully',
            message=f'Your application {application.case_id} has been submitted and is pending review.',
            metadata={'case_id': application.case_id}
        )
        
        # Send email
        try:
            subject = 'Application Submitted - Online Vetting System'
            html_message = render_to_string('emails/application_submitted.html', {
                'user': user,
                'case_id': application.case_id,
                'application_type': application.get_application_type_display()
            })
            plain_message = strip_tags(html_message)
            
            send_mail(
                subject=subject,
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                html_message=html_message,
                fail_silently=False
            )
            
            logger.info(f"✓ Email sent to {user.email}")
        
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
    
    @staticmethod
    def send_document_verified(document):
        """Notification when document verification completes"""
        user = document.case.applicant
        
        Notification.objects.create(
            user=user,
            notification_type='document_verified',
            title='Document Verified',
            message=f'Your {document.get_document_type_display()} has been verified.',
            metadata={
                'case_id': document.case.case_id,
                'document_type': document.document_type,
                'verification_status': document.verification_status
            }
        )
        
        # Send email
        try:
            subject = 'Document Verified - Online Vetting System'
            html_message = render_to_string('emails/document_verified.html', {
                'user': user,
                'case_id': document.case.case_id,
                'document_type': document.get_document_type_display(),
                'status': document.verification_status
            })
            plain_message = strip_tags(html_message)
            
            send_mail(
                subject=subject,
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                html_message=html_message,
                fail_silently=False
            )
        
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
    
    @staticmethod
    def send_status_updated(application, old_status, new_status):
        """Notification when application status changes"""
        user = application.applicant
        
        Notification.objects.create(
            user=user,
            notification_type='status_updated',
            title='Application Status Updated',
            message=f'Your application {application.case_id} status changed from {old_status} to {new_status}.',
            metadata={
                'case_id': application.case_id,
                'old_status': old_status,
                'new_status': new_status
            }
        )
        
        # Send email
        try:
            subject = f'Application Status: {new_status.upper()}'
            html_message = render_to_string('emails/status_updated.html', {
                'user': user,
                'case_id': application.case_id,
                'old_status': old_status,
                'new_status': new_status
            })
            plain_message = strip_tags(html_message)
            
            send_mail(
                subject=subject,
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                html_message=html_message,
                fail_silently=False
            )
        
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
    
    @staticmethod
    def send_evaluation_complete(application, evaluation):
        """
        Notification when rubric evaluation completes
        From: Rubrics PDF
        """
        user = application.applicant
        
        Notification.objects.create(
            user=user,
            notification_type='evaluation_complete',
            title='Evaluation Complete',
            message=f'Your application has been evaluated. Score: {evaluation.overall_score:.1f}%',
            metadata={
                'case_id': application.case_id,
                'overall_score': evaluation.overall_score,
                'passed': evaluation.passed,
                'recommendation': evaluation.ai_recommendation
            }
        )
        
        # Send email
        try:
            subject = 'Application Evaluation Complete'
            html_message = render_to_string('emails/evaluation_complete.html', {
                'user': user,
                'case_id': application.case_id,
                'overall_score': evaluation.overall_score,
                'passed': evaluation.passed,
                'recommendation': evaluation.ai_recommendation
            })
            plain_message = strip_tags(html_message)
            
            send_mail(
                subject=subject,
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                html_message=html_message,
                fail_silently=False
            )
        
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
    
    @staticmethod
    def send_admin_notification(admin_user, notification_type, title, message, metadata=None):
        """Send notification to admin users"""
        Notification.objects.create(
            admin_user=admin_user,
            notification_type=notification_type,
            title=title,
            message=message,
            metadata=metadata or {}
        )
        
        # Send email to admin
        try:
            send_mail(
                subject=f'[Admin] {title}',
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[admin_user.email],
                fail_silently=False
            )
        
        except Exception as e:
            logger.error(f"Failed to send admin email: {e}")
    
    @staticmethod
    def send_approval_notification(application):
        """Notification when application is approved"""
        user = application.applicant
        
        Notification.objects.create(
            user=user,
            notification_type='approval',
            title='Application Approved!',
            message=f'Congratulations! Your application {application.case_id} has been approved.',
            metadata={'case_id': application.case_id}
        )
        
        # Send email
        try:
            subject = '🎉 Application Approved - Online Vetting System'
            html_message = render_to_string('emails/application_approved.html', {
                'user': user,
                'case_id': application.case_id
            })
            plain_message = strip_tags(html_message)
            
            send_mail(
                subject=subject,
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                html_message=html_message,
                fail_silently=False
            )
        
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
    
    @staticmethod
    def send_rejection_notification(application, reason=None):
        """Notification when application is rejected"""
        user = application.applicant
        
        message = f'Your application {application.case_id} has been rejected.'
        if reason:
            message += f' Reason: {reason}'
        
        Notification.objects.create(
            user=user,
            notification_type='rejection',
            title='Application Rejected',
            message=message,
            metadata={
                'case_id': application.case_id,
                'reason': reason
            }
        )
        
        # Send email
        try:
            subject = 'Application Status - Online Vetting System'
            html_message = render_to_string('emails/application_rejected.html', {
                'user': user,
                'case_id': application.case_id,
                'reason': reason
            })
            plain_message = strip_tags(html_message)
            
            send_mail(
                subject=subject,
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                html_message=html_message,
                fail_silently=False
            )
        
        except Exception as e:
            logger.error(f"Failed to send email: {e}")