from __future__ import annotations

import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

logger = logging.getLogger(__name__)


def _warning_for_notification_failure(label: str, meeting_id, failure_count: int, max_retries: int, exc: Exception) -> None:
    logger.warning(
        "Video meeting %s notification failed meeting=%s attempt=%s/%s error=%s",
        label,
        meeting_id,
        failure_count,
        max_retries,
        f"{exc.__class__.__name__}: {exc}",
    )


def _compute_next_retry_at(
    *,
    now,
    failure_count: int,
    max_retries: int,
    base_retry_seconds: int,
    max_retry_seconds: int,
):
    if failure_count >= max_retries:
        return None
    backoff_seconds = min(
        max_retry_seconds,
        base_retry_seconds * (2 ** max(0, failure_count - 1)),
    )
    return now + timedelta(seconds=backoff_seconds)


def _process_reminders_for_schema(
    *,
    now,
    soon_cutoff,
    claim_until,
    max_retries: int,
    base_retry_seconds: int,
    max_retry_seconds: int,
) -> dict[str, int]:
    """
    Runs all video meeting reminder logic for the current DB schema context.
    Must be called from within a schema_context() block.
    """
    # Import here to ensure models are resolved in the correct schema context.
    from apps.video_calls.models import VideoMeeting
    from apps.video_calls.services import (
        notify_meeting_start_now,
        notify_meeting_starting_soon,
        notify_meeting_time_up,
    )

    stats = {
        "soon": 0,
        "start_now": 0,
        "completed": 0,
        "soon_failed": 0,
        "start_now_failed": 0,
        "completed_failed": 0,
    }

    # ── 1. Starting-soon reminders ────────────────────────────────────────────

    meetings_starting_soon = (
        VideoMeeting.objects.select_related("organizer")
        .prefetch_related("participants__user")
        .filter(
            status=VideoMeeting.STATUS_SCHEDULED,
            scheduled_start__gt=now,
            scheduled_start__lte=soon_cutoff,
            reminder_before_sent_at__isnull=True,
            reminder_before_failure_count__lt=max_retries,
        )
        .filter(
            Q(reminder_before_next_retry_at__isnull=True) | Q(reminder_before_next_retry_at__lte=now)
        )
    )

    for meeting in meetings_starting_soon:
        reminder_minutes = int(getattr(meeting, "reminder_before_minutes", 15) or 15)
        minutes_until_start = (meeting.scheduled_start - now).total_seconds() / 60
        if minutes_until_start <= 0 or minutes_until_start > reminder_minutes:
            continue

        claimed = VideoMeeting.objects.filter(
            id=meeting.id,
            reminder_before_sent_at__isnull=True,
            reminder_before_failure_count__lt=max_retries,
        ).filter(
            Q(reminder_before_next_retry_at__isnull=True) | Q(reminder_before_next_retry_at__lte=now)
        ).update(
            reminder_before_sent_at=now,
            reminder_before_next_retry_at=claim_until,
            updated_at=now,
        )
        if not claimed:
            continue

        try:
            notify_meeting_starting_soon(meeting, minutes=reminder_minutes)
            VideoMeeting.objects.filter(id=meeting.id).update(
                reminder_before_failure_count=0,
                reminder_before_last_failure_at=None,
                reminder_before_next_retry_at=None,
                updated_at=timezone.now(),
            )
        except Exception as exc:
            failure_count = int(getattr(meeting, "reminder_before_failure_count", 0) or 0) + 1
            next_retry_at = _compute_next_retry_at(
                now=now,
                failure_count=failure_count,
                max_retries=max_retries,
                base_retry_seconds=base_retry_seconds,
                max_retry_seconds=max_retry_seconds,
            )
            _warning_for_notification_failure(
                "starting_soon", meeting.id, failure_count, max_retries, exc,
            )
            VideoMeeting.objects.filter(
                id=meeting.id,
                reminder_before_sent_at=now,
            ).update(
                reminder_before_sent_at=None,
                reminder_before_failure_count=failure_count,
                reminder_before_last_failure_at=now,
                reminder_before_next_retry_at=next_retry_at,
                updated_at=timezone.now(),
            )
            stats["soon_failed"] += 1
            continue

        stats["soon"] += 1

    # ── 2. Start-now transition ───────────────────────────────────────────────

    start_window = now - timedelta(minutes=1)
    meetings_needing_start_transition = (
        VideoMeeting.objects.select_related("organizer")
        .prefetch_related("participants__user")
        .filter(
            status=VideoMeeting.STATUS_SCHEDULED,
            scheduled_start__gte=start_window,
            scheduled_start__lte=now,
            reminder_start_sent_at__isnull=True,
        )
    )

    for meeting in meetings_needing_start_transition:
        with transaction.atomic():
            try:
                meeting.mark_ongoing()
            except ValidationError:
                continue
            meeting.save(update_fields=["updated_at"])

    # ── 3. Start-now notifications ────────────────────────────────────────────

    meetings_start_notifications = (
        VideoMeeting.objects.select_related("organizer")
        .prefetch_related("participants__user")
        .filter(
            status=VideoMeeting.STATUS_ONGOING,
            scheduled_start__lte=now,
            scheduled_end__gte=now,
            reminder_start_sent_at__isnull=True,
            reminder_start_failure_count__lt=max_retries,
        )
        .filter(
            Q(reminder_start_next_retry_at__isnull=True) | Q(reminder_start_next_retry_at__lte=now)
        )
    )

    for meeting in meetings_start_notifications:
        claimed = VideoMeeting.objects.filter(
            id=meeting.id,
            status=VideoMeeting.STATUS_ONGOING,
            reminder_start_sent_at__isnull=True,
            reminder_start_failure_count__lt=max_retries,
        ).filter(
            Q(reminder_start_next_retry_at__isnull=True) | Q(reminder_start_next_retry_at__lte=now)
        ).update(
            reminder_start_next_retry_at=claim_until,
            updated_at=now,
        )
        if not claimed:
            continue

        try:
            notify_meeting_start_now(meeting)
            VideoMeeting.objects.filter(id=meeting.id).update(
                reminder_start_sent_at=timezone.now(),
                reminder_start_failure_count=0,
                reminder_start_last_failure_at=None,
                reminder_start_next_retry_at=None,
                updated_at=timezone.now(),
            )
        except Exception as exc:
            failure_count = int(getattr(meeting, "reminder_start_failure_count", 0) or 0) + 1
            next_retry_at = _compute_next_retry_at(
                now=now,
                failure_count=failure_count,
                max_retries=max_retries,
                base_retry_seconds=base_retry_seconds,
                max_retry_seconds=max_retry_seconds,
            )
            _warning_for_notification_failure(
                "start_now", meeting.id, failure_count, max_retries, exc,
            )
            VideoMeeting.objects.filter(
                id=meeting.id,
                reminder_start_sent_at__isnull=True,
            ).update(
                reminder_start_failure_count=failure_count,
                reminder_start_last_failure_at=now,
                reminder_start_next_retry_at=next_retry_at,
                updated_at=timezone.now(),
            )
            stats["start_now_failed"] += 1
            continue

        stats["start_now"] += 1

    # ── 4. Complete overdue meetings ──────────────────────────────────────────

    meetings_to_complete = (
        VideoMeeting.objects.select_related("organizer")
        .prefetch_related("participants__user")
        .filter(
            status__in=[VideoMeeting.STATUS_SCHEDULED, VideoMeeting.STATUS_ONGOING],
            scheduled_end__lte=now,
        )
    )

    for meeting in meetings_to_complete:
        try:
            with transaction.atomic():
                if meeting.status == VideoMeeting.STATUS_SCHEDULED:
                    meeting.mark_ongoing()
                meeting.mark_completed()
        except ValidationError:
            continue

    # ── 5. Time-up notifications ──────────────────────────────────────────────

    meetings_time_up_notifications = (
        VideoMeeting.objects.select_related("organizer")
        .prefetch_related("participants__user")
        .filter(
            status=VideoMeeting.STATUS_COMPLETED,
            scheduled_end__lte=now,
            reminder_time_up_sent_at__isnull=True,
            reminder_time_up_failure_count__lt=max_retries,
        )
        .filter(
            Q(reminder_time_up_next_retry_at__isnull=True) | Q(reminder_time_up_next_retry_at__lte=now)
        )
    )

    for meeting in meetings_time_up_notifications:
        claimed = VideoMeeting.objects.filter(
            id=meeting.id,
            status=VideoMeeting.STATUS_COMPLETED,
            reminder_time_up_sent_at__isnull=True,
            reminder_time_up_failure_count__lt=max_retries,
        ).filter(
            Q(reminder_time_up_next_retry_at__isnull=True) | Q(reminder_time_up_next_retry_at__lte=now)
        ).update(
            reminder_time_up_next_retry_at=claim_until,
            updated_at=now,
        )
        if not claimed:
            continue

        try:
            notify_meeting_time_up(meeting)
            VideoMeeting.objects.filter(id=meeting.id).update(
                reminder_time_up_sent_at=timezone.now(),
                reminder_time_up_failure_count=0,
                reminder_time_up_last_failure_at=None,
                reminder_time_up_next_retry_at=None,
                updated_at=timezone.now(),
            )
        except Exception as exc:
            failure_count = int(getattr(meeting, "reminder_time_up_failure_count", 0) or 0) + 1
            next_retry_at = _compute_next_retry_at(
                now=now,
                failure_count=failure_count,
                max_retries=max_retries,
                base_retry_seconds=base_retry_seconds,
                max_retry_seconds=max_retry_seconds,
            )
            _warning_for_notification_failure(
                "time_up", meeting.id, failure_count, max_retries, exc,
            )
            VideoMeeting.objects.filter(
                id=meeting.id,
                reminder_time_up_sent_at__isnull=True,
            ).update(
                reminder_time_up_failure_count=failure_count,
                reminder_time_up_last_failure_at=now,
                reminder_time_up_next_retry_at=next_retry_at,
                updated_at=timezone.now(),
            )
            stats["completed_failed"] += 1
            continue

        stats["completed"] += 1

    return stats


@shared_task(name="apps.video_calls.tasks.process_video_meeting_reminders")
def process_video_meeting_reminders() -> dict[str, int]:
    """
    Iterates over all active tenant schemas and processes video meeting
    reminders for each one. The public schema has no video_calls tables
    so it is always skipped.
    """
    from django_tenants.utils import schema_context
    from apps.tenants.models import Organization

    now = timezone.now()

    max_lead_minutes = int(getattr(settings, "VIDEO_CALLS_MAX_REMINDER_BEFORE_MINUTES", 120))
    if max_lead_minutes < 1:
        max_lead_minutes = 120
    max_retries = int(getattr(settings, "VIDEO_CALLS_REMINDER_RETRY_MAX_ATTEMPTS", 3))
    if max_retries < 1:
        max_retries = 1
    base_retry_seconds = int(getattr(settings, "VIDEO_CALLS_REMINDER_RETRY_BASE_SECONDS", 60))
    if base_retry_seconds < 1:
        base_retry_seconds = 1
    max_retry_seconds = int(getattr(settings, "VIDEO_CALLS_REMINDER_RETRY_MAX_SECONDS", 900))
    if max_retry_seconds < base_retry_seconds:
        max_retry_seconds = base_retry_seconds

    soon_cutoff = now + timedelta(minutes=max_lead_minutes)
    claim_until = now + timedelta(seconds=base_retry_seconds)

    totals: dict[str, int] = {
        "soon": 0,
        "start_now": 0,
        "completed": 0,
        "soon_failed": 0,
        "start_now_failed": 0,
        "completed_failed": 0,
    }

    tenant_schemas = (
        Organization.objects.filter(is_active=True)
        .exclude(schema_name="public")
        .values_list("schema_name", flat=True)
    )

    for schema_name in tenant_schemas:
        try:
            with schema_context(schema_name):
                schema_stats = _process_reminders_for_schema(
                    now=now,
                    soon_cutoff=soon_cutoff,
                    claim_until=claim_until,
                    max_retries=max_retries,
                    base_retry_seconds=base_retry_seconds,
                    max_retry_seconds=max_retry_seconds,
                )
            for key, value in schema_stats.items():
                totals[key] += value
        except Exception as exc:
            logger.error(
                "process_video_meeting_reminders failed for schema=%s error=%s",
                schema_name,
                f"{exc.__class__.__name__}: {exc}",
                exc_info=True,
            )

    return totals