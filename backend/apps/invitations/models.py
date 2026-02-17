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
