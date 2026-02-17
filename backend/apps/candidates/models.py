from django.conf import settings
from django.db import models

from apps.campaigns.models import VettingCampaign


class Candidate(models.Model):
    CHANNEL_CHOICES = [
        ("email", "Email"),
        ("sms", "SMS"),
    ]

    id = models.BigAutoField(primary_key=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    phone_number = models.CharField(max_length=20, blank=True)
    preferred_channel = models.CharField(max_length=10, choices=CHANNEL_CHOICES, default="email")
    consent_recording = models.BooleanField(default=False)
    consent_ai_processing = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.first_name} {self.last_name} <{self.email}>"


class CandidateEnrollment(models.Model):
    STATUS_CHOICES = [
        ("invited", "Invited"),
        ("registered", "Registered"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
        ("reviewed", "Reviewed"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("escalated", "Escalated"),
    ]

    id = models.BigAutoField(primary_key=True)
    campaign = models.ForeignKey(VettingCampaign, on_delete=models.CASCADE, related_name="enrollments")
    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE, related_name="enrollments")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="invited", db_index=True)

    invited_at = models.DateTimeField(null=True, blank=True)
    registered_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    review_notes = models.TextField(blank=True)
    decision_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_candidate_enrollments",
    )
    metadata = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["campaign", "candidate"], name="uniq_campaign_candidate_enrollment"),
        ]

    def __str__(self):
        return f"{self.campaign.name} :: {self.candidate.email} ({self.status})"
