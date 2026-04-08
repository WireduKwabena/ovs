import uuid

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.applications.models import VettingCase


class BackgroundCheck(models.Model):
    CHECK_TYPE_CHOICES = [
        ("criminal", "Criminal Records"),
        ("employment", "Employment History"),
        ("education", "Education Verification"),
        ("kyc_aml", "KYC/AML"),
        ("identity", "Identity Verification"),
    ]

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("submitted", "Submitted"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
        ("manual_review", "Manual Review"),
        ("failed", "Failed"),
        ("cancelled", "Cancelled"),
    ]

    RISK_LEVEL_CHOICES = [
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
        ("unknown", "Unknown"),
    ]

    RECOMMENDATION_CHOICES = [
        ("clear", "Clear"),
        ("review", "Manual Review"),
        ("reject", "Reject"),
        ("unavailable", "Unavailable"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    case = models.ForeignKey(VettingCase, on_delete=models.CASCADE, related_name="background_checks")

    check_type = models.CharField(max_length=30, choices=CHECK_TYPE_CHOICES, db_index=True)
    provider_key = models.CharField(max_length=50, default="mock", db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending", db_index=True)

    external_reference = models.CharField(max_length=255, blank=True, db_index=True)

    score = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Normalized provider score (0-100).",
    )
    risk_level = models.CharField(max_length=20, choices=RISK_LEVEL_CHOICES, default="unknown")
    recommendation = models.CharField(max_length=20, choices=RECOMMENDATION_CHOICES, default="unavailable")

    request_payload = models.JSONField(default=dict, blank=True)
    response_payload = models.JSONField(default=dict, blank=True)
    result_summary = models.JSONField(default=dict, blank=True)
    consent_evidence = models.JSONField(default=dict, blank=True)

    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="submitted_background_checks",
        db_constraint=False,
    )

    error_code = models.CharField(max_length=100, blank=True)
    error_message = models.TextField(blank=True)

    submitted_at = models.DateTimeField(null=True, blank=True)
    last_polled_at = models.DateTimeField(null=True, blank=True)
    webhook_received_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["case", "status"]),
            models.Index(fields=["check_type", "status"]),
            models.Index(fields=["provider_key", "external_reference"]),
        ]

    def __str__(self):
        return f"{self.case.case_id}::{self.check_type}::{self.status}"


class BackgroundCheckEvent(models.Model):
    EVENT_TYPE_CHOICES = [
        ("submitted", "Submitted"),
        ("provider_update", "Provider Update"),
        ("webhook", "Webhook"),
        ("manual", "Manual Update"),
        ("error", "Error"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    background_check = models.ForeignKey(BackgroundCheck, on_delete=models.CASCADE, related_name="events")
    event_type = models.CharField(max_length=30, choices=EVENT_TYPE_CHOICES)
    status_before = models.CharField(max_length=20, blank=True)
    status_after = models.CharField(max_length=20, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["background_check", "event_type"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"{self.background_check_id}::{self.event_type}"

