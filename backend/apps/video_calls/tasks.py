from __future__ import annotations

from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.video_calls.models import VideoMeeting
from apps.video_calls.services import (
    notify_meeting_start_now,
    notify_meeting_starting_soon,
    notify_meeting_time_up,
)


@shared_task(name="apps.video_calls.tasks.process_video_meeting_reminders")
def process_video_meeting_reminders() -> dict[str, int]:
    now = timezone.now()
    max_lead_minutes = int(getattr(settings, "VIDEO_CALLS_MAX_REMINDER_BEFORE_MINUTES", 120))
    if max_lead_minutes < 1:
        max_lead_minutes = 120
    soon_cutoff = now + timedelta(minutes=max_lead_minutes)
    stats = {"soon": 0, "start_now": 0, "completed": 0}

    meetings_starting_soon = (
        VideoMeeting.objects.select_related("organizer")
        .prefetch_related("participants__user")
        .filter(
            status=VideoMeeting.STATUS_SCHEDULED,
            scheduled_start__gt=now,
            scheduled_start__lte=soon_cutoff,
            reminder_before_sent_at__isnull=True,
        )
    )

    for meeting in meetings_starting_soon:
        reminder_minutes = int(getattr(meeting, "reminder_before_minutes", 15) or 15)
        minutes_until_start = (meeting.scheduled_start - now).total_seconds() / 60
        if minutes_until_start <= 0 or minutes_until_start > reminder_minutes:
            continue

        notify_meeting_starting_soon(meeting, minutes=reminder_minutes)
        meeting.reminder_before_sent_at = now
        meeting.save(update_fields=["reminder_before_sent_at", "updated_at"])
        stats["soon"] += 1

    start_window = now - timedelta(minutes=1)
    meetings_starting_now = (
        VideoMeeting.objects.select_related("organizer")
        .prefetch_related("participants__user")
        .filter(
            status=VideoMeeting.STATUS_SCHEDULED,
            scheduled_start__gte=start_window,
            scheduled_start__lte=now,
            reminder_start_sent_at__isnull=True,
        )
    )

    for meeting in meetings_starting_now:
        notify_meeting_start_now(meeting)
        with transaction.atomic():
            meeting.status = VideoMeeting.STATUS_ONGOING
            meeting.reminder_start_sent_at = now
            meeting.save(update_fields=["status", "reminder_start_sent_at", "updated_at"])
        stats["start_now"] += 1

    meetings_completed = (
        VideoMeeting.objects.select_related("organizer")
        .prefetch_related("participants__user")
        .filter(
            status__in=[VideoMeeting.STATUS_SCHEDULED, VideoMeeting.STATUS_ONGOING],
            scheduled_end__lte=now,
        )
    )
    for meeting in meetings_completed:
        notify_meeting_time_up(meeting)
        meeting.status = VideoMeeting.STATUS_COMPLETED
        meeting.save(update_fields=["status", "updated_at"])
        stats["completed"] += 1
    return stats
