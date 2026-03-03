import uuid
from datetime import timedelta

from django.core.validators import MaxValueValidator, MinValueValidator
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.applications.models import VettingCase
from apps.authentication.models import User


class VideoMeeting(models.Model):
    STATUS_SCHEDULED = "scheduled"
    STATUS_ONGOING = "ongoing"
    STATUS_COMPLETED = "completed"
    STATUS_CANCELLED = "cancelled"

    STATUS_CHOICES = [
        (STATUS_SCHEDULED, "Scheduled"),
        (STATUS_ONGOING, "Ongoing"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    series_id = models.UUIDField(null=True, blank=True, db_index=True)
    organizer = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="organized_video_meetings",
    )
    case = models.ForeignKey(
        VettingCase,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_constraint=False,
        related_name="video_meetings",
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_SCHEDULED,
        db_index=True,
    )
    scheduled_start = models.DateTimeField(db_index=True)
    scheduled_end = models.DateTimeField(db_index=True)
    timezone = models.CharField(max_length=64, default="UTC")
    livekit_room_name = models.CharField(max_length=128, unique=True, editable=False)
    allow_join_before_seconds = models.PositiveIntegerField(default=300)
    reminder_before_minutes = models.PositiveSmallIntegerField(
        default=15,
        validators=[MinValueValidator(1), MaxValueValidator(120)],
    )
    reminder_before_sent_at = models.DateTimeField(null=True, blank=True)
    reminder_start_sent_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["scheduled_start", "-created_at"]
        indexes = [
            models.Index(fields=["status", "scheduled_start"]),
            models.Index(fields=["organizer", "scheduled_start"]),
        ]
        verbose_name = "Video Meeting"
        verbose_name_plural = "Video Meetings"

    def __str__(self) -> str:
        return f"{self.title} ({self.scheduled_start.isoformat()})"

    def clean(self):
        if self.scheduled_end <= self.scheduled_start:
            raise ValidationError("scheduled_end must be after scheduled_start.")
        if (self.scheduled_end - self.scheduled_start) > timedelta(hours=8):
            raise ValidationError("Meeting duration cannot exceed 8 hours.")

    def save(self, *args, **kwargs):
        if not self.livekit_room_name:
            self.livekit_room_name = f"vc-{uuid.uuid4().hex[:16]}"
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def is_joinable(self) -> bool:
        now = timezone.now()
        join_window_start = self.scheduled_start - timedelta(seconds=self.allow_join_before_seconds)
        return (
            self.status in {self.STATUS_SCHEDULED, self.STATUS_ONGOING}
            and join_window_start <= now <= self.scheduled_end + timedelta(minutes=30)
        )

    def has_participant(self, user: User) -> bool:
        return self.participants.filter(user=user).exists()


class VideoMeetingParticipant(models.Model):
    ROLE_HOST = "host"
    ROLE_CANDIDATE = "candidate"
    ROLE_OBSERVER = "observer"

    ROLE_CHOICES = [
        (ROLE_HOST, "Host"),
        (ROLE_CANDIDATE, "Candidate"),
        (ROLE_OBSERVER, "Observer"),
    ]

    STATUS_INVITED = "invited"
    STATUS_JOINED = "joined"
    STATUS_LEFT = "left"
    STATUS_DECLINED = "declined"

    STATUS_CHOICES = [
        (STATUS_INVITED, "Invited"),
        (STATUS_JOINED, "Joined"),
        (STATUS_LEFT, "Left"),
        (STATUS_DECLINED, "Declined"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    meeting = models.ForeignKey(
        VideoMeeting,
        on_delete=models.CASCADE,
        related_name="participants",
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="video_meeting_participations",
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_CANDIDATE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_INVITED, db_index=True)
    invited_at = models.DateTimeField(auto_now_add=True)
    joined_at = models.DateTimeField(null=True, blank=True)
    left_at = models.DateTimeField(null=True, blank=True)
    last_reminded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["invited_at"]
        unique_together = [("meeting", "user")]
        indexes = [
            models.Index(fields=["meeting", "role"]),
            models.Index(fields=["user", "status"]),
        ]
        verbose_name = "Video Meeting Participant"
        verbose_name_plural = "Video Meeting Participants"

    def __str__(self) -> str:
        return f"{self.user.email} @ {self.meeting.livekit_room_name}"

    def mark_joined(self):
        self.status = self.STATUS_JOINED
        self.joined_at = timezone.now()
        self.save(update_fields=["status", "joined_at"])

    def mark_left(self):
        self.status = self.STATUS_LEFT
        self.left_at = timezone.now()
        self.save(update_fields=["status", "left_at"])


class VideoMeetingEvent(models.Model):
    ACTION_CREATED = "created"
    ACTION_RESCHEDULED = "rescheduled"
    ACTION_EXTENDED = "extended"
    ACTION_CANCELLED = "cancelled"
    ACTION_STARTED = "started"
    ACTION_COMPLETED = "completed"
    ACTION_LEFT = "left"

    ACTION_CHOICES = [
        (ACTION_CREATED, "Created"),
        (ACTION_RESCHEDULED, "Rescheduled"),
        (ACTION_EXTENDED, "Extended"),
        (ACTION_CANCELLED, "Cancelled"),
        (ACTION_STARTED, "Started"),
        (ACTION_COMPLETED, "Completed"),
        (ACTION_LEFT, "Left"),
    ]

    SCOPE_SINGLE = "single"
    SCOPE_FUTURE = "future"
    SCOPE_ALL = "all"

    SCOPE_CHOICES = [
        (SCOPE_SINGLE, "Single"),
        (SCOPE_FUTURE, "Future"),
        (SCOPE_ALL, "All"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    meeting = models.ForeignKey(
        VideoMeeting,
        on_delete=models.CASCADE,
        related_name="events",
    )
    actor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="video_meeting_events",
    )
    action = models.CharField(max_length=32, choices=ACTION_CHOICES)
    scope = models.CharField(max_length=12, choices=SCOPE_CHOICES, default=SCOPE_SINGLE)
    detail = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["meeting", "created_at"]),
            models.Index(fields=["action", "created_at"]),
        ]
        verbose_name = "Video Meeting Event"
        verbose_name_plural = "Video Meeting Events"

    def __str__(self) -> str:
        return f"{self.meeting_id} [{self.action}] {self.created_at.isoformat()}"
