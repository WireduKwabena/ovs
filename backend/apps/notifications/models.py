# # backend/apps/notifications/models.py
# # From: Development Guide PDF
# import uuid
# from django.db import models
# from apps.auth_actions.models.models import User, AdminUser
# from apps.interviews import DynamicInterviewSession
#
# class Notification(models.Model):
#     """User notifications"""
#     NOTIFICATION_TYPES = [
#         ('application_submitted', 'Application Submitted'),
#         ('document_verified', 'Document Verified'),
#         ('status_updated', 'Status Updated'),
#         ('approval', 'Approval'),
#         ('rejection', 'Rejection'),
#         ('review_required', 'Review Required'),
#     ]
#
#     STATUS_CHOICES = [
#         ('unread', 'Unread'),
#         ('read', 'Read'),
#         ('archived', 'Archived'),
#     ]
#
#     id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
#     # Can be sent to either user or admin
#     user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='notifications')
#     admin_user = models.ForeignKey(AdminUser, on_delete=models.CASCADE, null=True, blank=True, related_name='notifications')
#
#     notification_type = models.CharField(max_length=50, choices=NOTIFICATION_TYPES)
#     title = models.CharField(max_length=200)
#     message = models.TextField()
#     status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='unread')
#
#     metadata = models.JSONField(default=dict)  # Additional data (case_id, etc)
#
#     created_at = models.DateTimeField(auto_now_add=True)
#     read_at = models.DateTimeField(null=True, blank=True)
#
#     class Meta:
#         db_table = 'notifications'
#         ordering = ['-created_at']
#
#
#
# # apps/notifications/models.py
# class AlertLog(models.Model):
#     session = models.ForeignKey(DynamicInterviewSession, on_delete=models.CASCADE)
#     alert_type = models.CharField(max_length=50)
#     triggered_at = models.DateTimeField(auto_now_add=True)
#
#     class Meta:
#         db_table = 'alert_logs'
#         ordering = ['-triggered_at']
#


"""
Notifications Models
====================
Email alerts and system notification models.

Academic Note:
--------------
Implements notification system for:
1. Real-time alerts (high-risk detections)
2. Status updates (vetting completion)
3. Task assignments (manual review required)
4. Audit trail (who was notified when)
"""

from django.db import models
from django.utils import timezone
from apps.authentication.models import User
from apps.applications.models import VettingCase
from apps.interviews.models import InterviewSession


class NotificationTemplate(models.Model):
    """
    Email/notification templates.

    Reusable templates for different notification types.

    Academic Note:
    --------------
    Template pattern for consistent messaging.
    Supports variable interpolation for personalization.
    """

    TEMPLATE_TYPE_CHOICES = [
        ('email', 'Email'),
        ('sms', 'SMS'),
        ('in_app', 'In-App Notification'),
    ]

    CATEGORY_CHOICES = [
        ('alert', 'Alert/Warning'),
        ('status_update', 'Status Update'),
        ('task_assignment', 'Task Assignment'),
        ('completion', 'Completion Notice'),
        ('reminder', 'Reminder'),
    ]

    # Template identification
    name = models.CharField(max_length=200, unique=True)
    template_type = models.CharField(
        max_length=20,
        choices=TEMPLATE_TYPE_CHOICES
    )
    category = models.CharField(
        max_length=30,
        choices=CATEGORY_CHOICES
    )

    # Content
    subject = models.CharField(
        max_length=200,
        help_text="Email subject or notification title"
    )

    body = models.TextField(
        help_text="Template body with {{variable}} placeholders"
    )

    # Email specific
    from_email = models.EmailField(blank=True)
    cc_emails = models.JSONField(
        default=list,
        blank=True,
        help_text="Default CC recipients"
    )

    # Metadata
    is_active = models.BooleanField(default=True)
    variables_used = models.JSONField(
        default=list,
        help_text="List of variables used in template"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['category', 'name']
        verbose_name = 'Notification Template'
        verbose_name_plural = 'Notification Templates'
        app_label = 'notifications'

    def __str__(self):
        return f"{self.name} ({self.get_template_type_display()})"


class Notification(models.Model):
    """
    Individual notification record.

    Tracks all notifications sent through the system.

    Academic Note:
    --------------
    Audit trail for compliance and debugging.
    Enables analysis of notification patterns and user engagement.
    """

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
        ('read', 'Read'),
    ]

    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]

    # Relationships
    recipient = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='notifications'
    )

    template = models.ForeignKey(
        NotificationTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sent_notifications'
    )

    # Related entities (optional)
    related_case = models.ForeignKey(
        VettingCase,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notifications'
    )

    related_interview = models.ForeignKey(
        InterviewSession,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notifications'
    )

    # Content
    subject = models.CharField(max_length=200)
    message = models.TextField()

    # Delivery
    notification_type = models.CharField(
        max_length=20,
        choices=NotificationTemplate.TEMPLATE_TYPE_CHOICES
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        db_index=True
    )

    priority = models.CharField(
        max_length=20,
        choices=PRIORITY_CHOICES,
        default='normal'
    )

    # Email specific
    email_to = models.EmailField(blank=True)
    email_cc = models.JSONField(default=list, blank=True)

    # Delivery tracking
    sent_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    failed_at = models.DateTimeField(null=True, blank=True)
    failure_reason = models.TextField(blank=True)
    retry_count = models.IntegerField(default=0)

    # Metadata
    metadata = models.JSONField(
        default=dict,
        help_text="Additional context data"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', 'status']),
            models.Index(fields=['status', 'priority']),
            models.Index(fields=['-created_at']),
        ]
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'
        app_label = 'notifications'

    def __str__(self):
        return f"{self.subject} to {self.recipient.email}"

    def mark_sent(self):
        """Mark notification as sent."""
        self.status = 'sent'
        self.sent_at = timezone.now()
        self.save()

    def mark_read(self):
        """Mark notification as read."""
        self.status = 'read'
        self.read_at = timezone.now()
        self.save()

    def mark_failed(self, reason):
        """Mark notification as failed."""
        self.status = 'failed'
        self.failed_at = timezone.now()
        self.failure_reason = reason
        self.retry_count += 1
        self.save()


class AlertRule(models.Model):
    """
    Automated alert rules.

    Defines conditions that trigger automatic notifications.

    Academic Note:
    --------------
    Rule-based expert system for proactive alerting.
    Helps ensure timely human review of critical issues.
    """

    TRIGGER_TYPE_CHOICES = [
        ('fraud_score_threshold', 'Fraud Score Above Threshold'),
        ('authenticity_score_threshold', 'Authenticity Score Below Threshold'),
        ('critical_flag_detected', 'Critical Flag Detected'),
        ('interview_red_flag', 'Interview Red Flag'),
        ('processing_error', 'Processing Error'),
        ('sla_breach', 'SLA Breach'),
        ('manual_review_required', 'Manual Review Required'),
    ]

    # Rule definition
    name = models.CharField(max_length=200)
    description = models.TextField()
    trigger_type = models.CharField(
        max_length=50,
        choices=TRIGGER_TYPE_CHOICES
    )

    # Conditions
    threshold_value = models.FloatField(
        null=True,
        blank=True,
        help_text="Threshold value for score-based triggers"
    )

    additional_conditions = models.JSONField(
        default=dict,
        help_text="Additional conditions in JSON format"
    )

    # Notification settings
    notification_template = models.ForeignKey(
        NotificationTemplate,
        on_delete=models.CASCADE,
        related_name='alert_rules'
    )

    notify_users = models.ManyToManyField(
        User,
        related_name='alert_subscriptions',
        help_text="Users to notify when rule triggers"
    )

    # Priority and throttling
    priority = models.CharField(
        max_length=20,
        choices=Notification.PRIORITY_CHOICES,
        default='high'
    )

    cooldown_minutes = models.IntegerField(
        default=0,
        help_text="Minimum minutes between alerts for same case"
    )

    # Status
    is_active = models.BooleanField(default=True)

    # Usage tracking
    times_triggered = models.IntegerField(default=0)
    last_triggered_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Alert Rule'
        verbose_name_plural = 'Alert Rules'
        app_label = 'notifications'

    def __str__(self):
        return self.name

    def can_trigger(self, case_id=None):
        """Check if rule can trigger (cooldown check)."""
        if not self.is_active:
            return False

        if self.cooldown_minutes > 0 and self.last_triggered_at:
            cooldown_end = self.last_triggered_at + timezone.timedelta(
                minutes=self.cooldown_minutes
            )
            if timezone.now() < cooldown_end:
                return False

        return True

    def trigger(self):
        """Mark rule as triggered."""
        self.times_triggered += 1
        self.last_triggered_at = timezone.now()
        self.save()



