from __future__ import annotations

import json
import time
from datetime import timezone as dt_timezone
from typing import Iterable
from urllib.parse import urlencode

from django.conf import settings
from django.utils import timezone

from apps.users.models import User
from apps.notifications.services import NotificationService
from apps.video_calls.models import VideoMeeting

try:
    import jwt
except ImportError:  # pragma: no cover - runtime dependency
    jwt = None


def _unique_users(users: Iterable[User]) -> list[User]:
    seen: set[str] = set()
    deduped: list[User] = []
    for user in users:
        user_key = str(user.id)
        if user_key in seen:
            continue
        seen.add(user_key)
        deduped.append(user)
    return deduped


def meeting_recipients(meeting: VideoMeeting) -> list[User]:
    participants = [entry.user for entry in meeting.participants.select_related("user").all()]
    return _unique_users([meeting.organizer, *participants])


def _frontend_url(base_path: str) -> str:
    base = str(getattr(settings, "FRONTEND_URL", "")).strip().rstrip("/")
    if not base:
        return base_path
    return f"{base}{base_path}"


def _api_url(base_path: str) -> str:
    base = str(getattr(settings, "DJANGO_API_URL", "")).strip().rstrip("/")
    if not base:
        return base_path
    return f"{base}{base_path}"


def build_meeting_frontend_url(meeting: VideoMeeting, *, autojoin: bool = False) -> str:
    params = {"meeting": str(meeting.id)}
    if autojoin:
        params["autojoin"] = "1"
    return _frontend_url(f"/video-calls?{urlencode(params)}")


def _calendar_timestamp(value) -> str:
    aware = value.astimezone(dt_timezone.utc)
    return aware.strftime("%Y%m%dT%H%M%SZ")


def build_meeting_google_calendar_url(meeting: VideoMeeting) -> str:
    details = meeting.description or "Scheduled vetting video interview"
    meeting_url = build_meeting_frontend_url(meeting, autojoin=False)
    details_with_link = f"{details}\n\nJoin meeting: {meeting_url}"
    params = urlencode(
        {
            "action": "TEMPLATE",
            "text": meeting.title or "Video Meeting",
            "dates": f"{_calendar_timestamp(meeting.scheduled_start)}/{_calendar_timestamp(meeting.scheduled_end)}",
            "details": details_with_link,
            "location": f"LiveKit Room: {meeting.livekit_room_name}",
            "ctz": meeting.timezone or "UTC",
        }
    )
    return f"https://calendar.google.com/calendar/render?{params}"


def build_meeting_calendar_ics_url(meeting: VideoMeeting) -> str:
    return _api_url(f"/api/video-calls/meetings/{meeting.id}/calendar-ics/")


def _escape_ics(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace(",", "\\,")
        .replace(";", "\\;")
    )


def build_meeting_ics_content(meeting: VideoMeeting) -> str:
    now_stamp = _calendar_timestamp(timezone.now())
    start = _calendar_timestamp(meeting.scheduled_start)
    end = _calendar_timestamp(meeting.scheduled_end)
    join_url = build_meeting_frontend_url(meeting, autojoin=False)
    description = meeting.description or "Scheduled vetting video interview"
    description = f"{description}\\n\\nJoin meeting: {join_url}"
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//OVS//Video Calls//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        f"UID:{meeting.id}@ovs.local",
        f"DTSTAMP:{now_stamp}",
        f"DTSTART:{start}",
        f"DTEND:{end}",
        f"SUMMARY:{_escape_ics(meeting.title or 'Video Meeting')}",
        f"DESCRIPTION:{_escape_ics(description)}",
        f"LOCATION:{_escape_ics(f'LiveKit Room: {meeting.livekit_room_name}')}",
        "END:VEVENT",
        "END:VCALENDAR",
    ]
    return "\r\n".join(lines) + "\r\n"


def build_livekit_join_token(*, meeting: VideoMeeting, user: User, role: str = "participant") -> str:
    if jwt is None:
        raise RuntimeError("PyJWT is not installed. Install dependency required for LiveKit tokens.")

    api_key = str(getattr(settings, "LIVEKIT_API_KEY", "")).strip()
    api_secret = str(getattr(settings, "LIVEKIT_API_SECRET", "")).strip()
    if not api_key or not api_secret:
        raise RuntimeError("LiveKit credentials are not configured.")

    now = int(time.time())
    ttl_seconds = int(getattr(settings, "LIVEKIT_TOKEN_TTL_SECONDS", 3600))
    can_publish = role in {"host", "moderator", "participant"}

    payload = {
        "iss": api_key,
        "sub": str(user.id),
        "nbf": now,
        "exp": now + ttl_seconds,
        "name": user.get_full_name() or user.email,
        "metadata": json.dumps(
            {
                "meeting_id": str(meeting.id),
                "user_type": getattr(user, "user_type", ""),
                "role": role,
            }
        ),
        "video": {
            "roomJoin": True,
            "room": meeting.livekit_room_name,
            "canPublish": can_publish,
            "canSubscribe": True,
            "canPublishData": can_publish,
        },
    }
    return jwt.encode(payload, api_secret, algorithm="HS256")


def _meeting_event_idempotency_key(
    *,
    meeting: VideoMeeting,
    event_type: str,
    fingerprint: str,
) -> str:
    return f"{event_type}:{meeting.id}:{fingerprint}"


def _notify_users(
    *,
    users: Iterable[User],
    subject: str,
    message: str,
    meeting: VideoMeeting,
    event_type: str,
    priority: str = "normal",
    idempotency_fingerprint: str | None = None,
):
    meeting_url = build_meeting_frontend_url(meeting, autojoin=False)
    meeting_autojoin_url = build_meeting_frontend_url(meeting, autojoin=True)
    meeting_google_calendar_url = build_meeting_google_calendar_url(meeting)
    meeting_calendar_ics_url = build_meeting_calendar_ics_url(meeting)

    payload = {
        "event_type": event_type,
        "meeting_id": str(meeting.id),
        "meeting_title": meeting.title,
        "meeting_status": meeting.status,
        "scheduled_start": meeting.scheduled_start.isoformat(),
        "scheduled_end": meeting.scheduled_end.isoformat(),
        "allow_join_before_seconds": int(getattr(meeting, "allow_join_before_seconds", 300) or 300),
        "room_name": meeting.livekit_room_name,
        "case_id": str(meeting.case_id) if meeting.case_id else "",
        "meeting_url": meeting_url,
        "meeting_autojoin_url": meeting_autojoin_url,
        "meeting_google_calendar_url": meeting_google_calendar_url,
        "meeting_calendar_ics_url": meeting_calendar_ics_url,
    }
    fingerprint = str(
        idempotency_fingerprint
        or f"{meeting.scheduled_start.isoformat()}:{meeting.scheduled_end.isoformat()}"
    )
    event_idempotency_key = _meeting_event_idempotency_key(
        meeting=meeting,
        event_type=event_type,
        fingerprint=fingerprint,
    )
    payload["idempotency_key"] = event_idempotency_key

    message_with_links = message
    if event_type in {"video_call_scheduled", "video_call_updated", "video_call_reminder", "video_call_start_now"}:
        message_with_links = (
            f"{message}\n\n"
            f"Open meeting: {meeting_url}\n"
            f"Auto-join: {meeting_autojoin_url}\n"
            f"Google Calendar: {meeting_google_calendar_url}\n"
            f"Calendar (.ics): {meeting_calendar_ics_url}"
        )

    for user in _unique_users(users):
        NotificationService._create_in_app_notification(
            recipient=user,
            subject=subject,
            message=message_with_links,
            related_case=meeting.case,
            metadata=payload,
            priority=priority,
            idempotency_key=event_idempotency_key,
        )
        NotificationService._send_email_notification(
            recipient=user,
            subject=subject,
            fallback_message=message_with_links,
            related_case=meeting.case,
            metadata=payload,
            priority=priority,
            idempotency_key=event_idempotency_key,
        )
        NotificationService._send_sms_notification_record(
            recipient=user,
            subject=subject,
            message=message_with_links,
            related_case=meeting.case,
            metadata=payload,
            priority=priority,
            idempotency_key=event_idempotency_key,
        )


def notify_meeting_created(meeting: VideoMeeting):
    users = meeting_recipients(meeting)
    readable_start = timezone.localtime(meeting.scheduled_start).strftime("%Y-%m-%d %H:%M %Z")
    readable_end = timezone.localtime(meeting.scheduled_end).strftime("%Y-%m-%d %H:%M %Z")
    subject = f"Video call scheduled: {meeting.title}"
    message = (
        f"A video call has been scheduled from {readable_start} to {readable_end}. "
        f"Meeting room: {meeting.livekit_room_name}."
    )
    _notify_users(
        users=users,
        subject=subject,
        message=message,
        meeting=meeting,
        event_type="video_call_scheduled",
        priority="high",
        idempotency_fingerprint=str(getattr(meeting, "created_at", "") or meeting.scheduled_start.isoformat()),
    )


def notify_meeting_updated(meeting: VideoMeeting):
    users = meeting_recipients(meeting)
    readable_start = timezone.localtime(meeting.scheduled_start).strftime("%Y-%m-%d %H:%M %Z")
    readable_end = timezone.localtime(meeting.scheduled_end).strftime("%Y-%m-%d %H:%M %Z")
    subject = f"Video call updated: {meeting.title}"
    message = (
        f"The meeting schedule has been updated to {readable_start} - {readable_end}. "
        f"Meeting room: {meeting.livekit_room_name}."
    )
    _notify_users(
        users=users,
        subject=subject,
        message=message,
        meeting=meeting,
        event_type="video_call_updated",
        priority="high",
        idempotency_fingerprint=str(getattr(meeting, "updated_at", "") or timezone.now().isoformat()),
    )


def notify_meeting_cancelled(meeting: VideoMeeting):
    users = meeting_recipients(meeting)
    subject = f"Video call cancelled: {meeting.title}"
    reason = f" Reason: {meeting.cancellation_reason}" if meeting.cancellation_reason else ""
    message = f"The scheduled video call has been cancelled.{reason}"
    _notify_users(
        users=users,
        subject=subject,
        message=message,
        meeting=meeting,
        event_type="video_call_cancelled",
        priority="high",
        idempotency_fingerprint=str(getattr(meeting, "updated_at", "") or timezone.now().isoformat()),
    )


def notify_meeting_starting_soon(meeting: VideoMeeting, minutes: int):
    users = meeting_recipients(meeting)
    subject = f"Reminder: video call starts in {minutes} minutes"
    message = f"Your meeting '{meeting.title}' starts in {minutes} minutes."
    _notify_users(
        users=users,
        subject=subject,
        message=message,
        meeting=meeting,
        event_type="video_call_reminder",
        priority="normal",
        idempotency_fingerprint=f"{meeting.scheduled_start.isoformat()}:{minutes}",
    )


def notify_meeting_start_now(meeting: VideoMeeting):
    users = meeting_recipients(meeting)
    subject = f"Meeting time: {meeting.title}"
    message = "The scheduled meeting time is now. Join the room to begin the video call."
    _notify_users(
        users=users,
        subject=subject,
        message=message,
        meeting=meeting,
        event_type="video_call_start_now",
        priority="high",
        idempotency_fingerprint=meeting.scheduled_start.isoformat(),
    )


def notify_meeting_time_up(meeting: VideoMeeting):
    users = meeting_recipients(meeting)
    subject = f"Meeting ended: {meeting.title}"
    message = "The scheduled meeting time is up. The call window has been closed."
    _notify_users(
        users=users,
        subject=subject,
        message=message,
        meeting=meeting,
        event_type="video_call_time_up",
        priority="normal",
        idempotency_fingerprint=meeting.scheduled_end.isoformat(),
    )
