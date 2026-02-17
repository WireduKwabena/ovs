# ============================================================================
# Signals
# ============================================================================
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import InterviewExchange, DynamicInterviewSession

@receiver(post_save, sender=InterviewExchange)
def check_for_alerts(sender, instance, created, **kwargs):
    """
    Check if alerts should be triggered after exchange is saved
    """
    if not created and instance.transcript: # Changed has_response to transcript check
        # Check and send alerts asynchronously
        from apps.notifications import check_interview_alerts
        check_interview_alerts.delay(instance.id)

@receiver(post_save, sender=DynamicInterviewSession)
def update_application_status(sender, instance, **kwargs):
    """
    Update application status when interview is completed
    """
    if instance.status == 'completed' and instance.overall_score:
        application = instance.application
        # Update application with interview results
        # application.interview_score = instance.overall_score # Field might not exist on VettingCase
        # application.interview_completed = True # Field might not exist on VettingCase
        # Determine next status based on score
        if instance.overall_score >= 80:
            application.status = 'approved'
        elif instance.overall_score < 50:
            application.status = 'rejected'
        else:
            application.status = 'under_review'
        application.save()
