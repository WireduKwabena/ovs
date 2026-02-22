import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.candidates.models import CandidateEnrollment


class Invitation(models.Model):
    CHANNEL_CHOICES = [
        ("email", "Email"),
        ("sms", "SMS"),
    ]

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("sent", "Sent"),
        ("failed", "Failed"),
        ("accepted", "Accepted"),
        ("expired", "Expired"),
    ]

    id = models.BigAutoField(primary_key=True)
    enrollment = models.ForeignKey(CandidateEnrollment, on_delete=models.CASCADE, related_name="invitations")

    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    channel = models.CharField(max_length=10, choices=CHANNEL_CHOICES, default="email")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending", db_index=True)

    send_to = models.CharField(max_length=255)
    expires_at = models.DateTimeField()
    sent_at = models.DateTimeField(null=True, blank=True)
    accepted_at = models.DateTimeField(null=True, blank=True)

    attempts = models.PositiveIntegerField(default=0)
    last_error = models.TextField(blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_invitations",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "expires_at"]),
            models.Index(fields=["token"]),
        ]

    def __str__(self):
        return f"Invitation<{self.enrollment_id}>:{self.channel}:{self.status}"

    @property
    def is_expired(self):
        return timezone.now() >= self.expires_at


class CandidateAccessPass(models.Model):
    PASS_TYPE_CHOICES = [
        ("portal", "Portal Access"),
        ("results", "Results Access"),
    ]

    STATUS_CHOICES = [
        ("issued", "Issued"),
        ("revoked", "Revoked"),
        ("expired", "Expired"),
    ]

    id = models.BigAutoField(primary_key=True)
    enrollment = models.ForeignKey(CandidateEnrollment, on_delete=models.CASCADE, related_name="access_passes")
    invitation = models.ForeignKey(
        Invitation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="access_passes",
    )

    pass_type = models.CharField(max_length=20, choices=PASS_TYPE_CHOICES, default="portal", db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="issued", db_index=True)

    token_hash = models.CharField(max_length=64, unique=True, db_index=True)
    token_hint = models.CharField(max_length=12, blank=True)

    max_uses = models.PositiveIntegerField(default=50)
    use_count = models.PositiveIntegerField(default=0)
    first_used_at = models.DateTimeField(null=True, blank=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    expires_at = models.DateTimeField(db_index=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_reason = models.CharField(max_length=255, blank=True)

    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="issued_candidate_access_passes",
    )
    metadata = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["enrollment", "pass_type", "status"]),
            models.Index(fields=["expires_at", "status"]),
        ]

    def __str__(self):
        return f"CandidateAccessPass<{self.enrollment_id}>:{self.pass_type}:{self.status}"

    @property
    def is_expired(self) -> bool:
        return timezone.now() >= self.expires_at

    @property
    def remaining_uses(self) -> int:
        remaining = self.max_uses - self.use_count
        return remaining if remaining > 0 else 0

    def can_be_used(self) -> bool:
        return self.status == "issued" and not self.is_expired and self.use_count < self.max_uses


class CandidateAccessSession(models.Model):
    STATUS_CHOICES = [
        ("active", "Active"),
        ("expired", "Expired"),
        ("closed", "Closed"),
    ]

    id = models.BigAutoField(primary_key=True)
    session_key = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    access_pass = models.ForeignKey(CandidateAccessPass, on_delete=models.CASCADE, related_name="sessions")
    enrollment = models.ForeignKey(CandidateEnrollment, on_delete=models.CASCADE, related_name="access_sessions")

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active", db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)

    issued_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(db_index=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    closed_reason = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-issued_at"]
        indexes = [
            models.Index(fields=["session_key", "status"]),
            models.Index(fields=["enrollment", "status"]),
        ]

    def __str__(self):
        return f"CandidateAccessSession<{self.enrollment_id}>:{self.status}"

    @property
    def is_expired(self) -> bool:
        return timezone.now() >= self.expires_at
