from datetime import datetime, timedelta
from unittest.mock import patch

from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from django.db import IntegrityError
from rest_framework import status
from rest_framework.test import APITestCase

from apps.applications.models import VettingCase
from apps.users.models import User
from apps.notifications.models import Notification
from apps.video_calls.models import VideoMeeting, VideoMeetingEvent, VideoMeetingParticipant
from apps.video_calls.services import (
    notify_meeting_cancelled,
    notify_meeting_start_now,
    notify_meeting_updated,
)
from apps.video_calls.tasks import process_video_meeting_reminders


class VideoMeetingApiTests(APITestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(
            email="admin-video-tests@example.com",
            password="SecurePass123!",
            first_name="Platform",
            last_name="Admin",
            user_type="admin",
            is_staff=True,
        )
        self.internal_user = User.objects.create_user(
            email="hr-video-tests@example.com",
            password="SecurePass123!",
            first_name="Internal",
            last_name="Manager",
            user_type="internal",
        )
        vetting_group, _ = Group.objects.get_or_create(name="vetting_officer")
        self.internal_user.groups.add(vetting_group)
        self.candidate = User.objects.create_user(
            email="candidate-video-tests@example.com",
            password="SecurePass123!",
            first_name="Candidate",
            last_name="User",
            user_type="applicant",
        )
        self.case = VettingCase.objects.create(
            applicant=self.candidate,
            position_applied="Backend Engineer",
            priority="medium",
        )
        self.client.force_authenticate(self.internal_user)

    def test_internal_can_schedule_video_meeting(self):
        response = self.client.post(
            reverse("video-meeting-list"),
            data={
                "title": "Candidate Follow-up",
                "description": "Discussion of flagged sections.",
                "case": str(self.case.id),
                "scheduled_start": (timezone.now() + timedelta(hours=1)).isoformat(),
                "scheduled_end": (timezone.now() + timedelta(hours=2)).isoformat(),
                "timezone": "UTC",
                "reminder_before_minutes": 25,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(VideoMeeting.objects.count(), 1)
        meeting = VideoMeeting.objects.first()
        self.assertEqual(meeting.organizer, self.internal_user)
        self.assertTrue(meeting.participants.filter(user=self.candidate).exists())
        self.assertEqual(meeting.reminder_before_minutes, 25)
        self.assertTrue(
            meeting.events.filter(action=VideoMeetingEvent.ACTION_CREATED, scope=VideoMeetingEvent.SCOPE_SINGLE).exists()
        )

    def test_plain_internal_without_operational_role_cannot_schedule_video_meeting(self):
        plain_internal = User.objects.create_user(
            email="plain-video-hr@example.com",
            password="SecurePass123!",
            first_name="Plain",
            last_name="Reviewer",
            user_type="internal",
        )
        self.client.force_authenticate(plain_internal)
        response = self.client.post(
            reverse("video-meeting-list"),
            data={
                "title": "Unauthorized Candidate Follow-up",
                "description": "Should be denied.",
                "case": str(self.case.id),
                "scheduled_start": (timezone.now() + timedelta(hours=1)).isoformat(),
                "scheduled_end": (timezone.now() + timedelta(hours=2)).isoformat(),
                "timezone": "UTC",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_internal_can_schedule_meeting_with_participant_emails(self):
        response = self.client.post(
            reverse("video-meeting-list"),
            data={
                "title": "Bulk candidate sync",
                "description": "1vMany screening session.",
                "scheduled_start": (timezone.now() + timedelta(hours=2)).isoformat(),
                "scheduled_end": (timezone.now() + timedelta(hours=3)).isoformat(),
                "timezone": "UTC",
                "participant_emails": [self.candidate.email],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        meeting = VideoMeeting.objects.get(id=response.data["id"])
        self.assertTrue(meeting.participants.filter(user=self.candidate).exists())

    def test_internal_can_schedule_daily_series(self):
        response = self.client.post(
            reverse("video-meeting-schedule-series"),
            data={
                "title": "Daily panel",
                "description": "Series for final interviews.",
                "case": str(self.case.id),
                "scheduled_start": (timezone.now() + timedelta(hours=2)).isoformat(),
                "scheduled_end": (timezone.now() + timedelta(hours=3)).isoformat(),
                "timezone": "UTC",
                "recurrence": "daily",
                "occurrences": 3,
                "reminder_before_minutes": 20,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["count"], 3)

        meetings = VideoMeeting.objects.filter(title="Daily panel").order_by("scheduled_start")
        self.assertEqual(meetings.count(), 3)
        self.assertEqual((meetings[1].scheduled_start - meetings[0].scheduled_start).days, 1)
        self.assertEqual((meetings[2].scheduled_start - meetings[1].scheduled_start).days, 1)
        self.assertTrue(all(item.reminder_before_minutes == 20 for item in meetings))
        series_ids = {item.series_id for item in meetings}
        self.assertEqual(len(series_ids), 1)
        self.assertIsNotNone(next(iter(series_ids)))

    def test_internal_can_reschedule_future_series_occurrences(self):
        base_start = timezone.now() + timedelta(hours=2)
        response = self.client.post(
            reverse("video-meeting-schedule-series"),
            data={
                "title": "Weekly panel",
                "description": "Weekly interviews.",
                "case": str(self.case.id),
                "scheduled_start": base_start.isoformat(),
                "scheduled_end": (base_start + timedelta(hours=1)).isoformat(),
                "timezone": "UTC",
                "recurrence": "weekly",
                "occurrences": 3,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        anchor_id = response.data["results"][1]["id"]

        new_anchor_start = base_start + timedelta(days=7, minutes=30)
        reschedule_response = self.client.post(
            reverse("video-meeting-reschedule-series", kwargs={"pk": anchor_id}),
            data={
                "scheduled_start": new_anchor_start.isoformat(),
                "scheduled_end": (new_anchor_start + timedelta(hours=1)).isoformat(),
                "timezone": "UTC",
                "scope": "future",
            },
            format="json",
        )

        self.assertEqual(reschedule_response.status_code, status.HTTP_200_OK)
        self.assertEqual(reschedule_response.data["count"], 2)

        meetings = VideoMeeting.objects.filter(title="Weekly panel").order_by("scheduled_start")
        self.assertEqual(meetings.count(), 3)
        # First occurrence remains unchanged; later ones shift.
        self.assertEqual(meetings[0].scheduled_start, base_start)
        self.assertEqual(meetings[1].scheduled_start, new_anchor_start)
        self.assertEqual(meetings[2].scheduled_start, new_anchor_start + timedelta(days=7))

    def test_internal_can_cancel_all_series_occurrences(self):
        base_start = timezone.now() + timedelta(hours=3)
        response = self.client.post(
            reverse("video-meeting-schedule-series"),
            data={
                "title": "Cancel me series",
                "description": "Series to cancel.",
                "case": str(self.case.id),
                "scheduled_start": base_start.isoformat(),
                "scheduled_end": (base_start + timedelta(hours=1)).isoformat(),
                "timezone": "UTC",
                "recurrence": "daily",
                "occurrences": 2,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        anchor_id = response.data["results"][0]["id"]

        cancel_response = self.client.post(
            reverse("video-meeting-cancel-series", kwargs={"pk": anchor_id}),
            data={"scope": "all", "reason": "Panel no longer required."},
            format="json",
        )

        self.assertEqual(cancel_response.status_code, status.HTTP_200_OK)
        self.assertEqual(cancel_response.data["count"], 2)
        cancelled = VideoMeeting.objects.filter(title="Cancel me series")
        self.assertTrue(all(item.status == VideoMeeting.STATUS_CANCELLED for item in cancelled))

    def test_series_requires_occurrence_one_when_recurrence_none(self):
        response = self.client.post(
            reverse("video-meeting-schedule-series"),
            data={
                "title": "Invalid recurrence",
                "case": str(self.case.id),
                "scheduled_start": (timezone.now() + timedelta(hours=2)).isoformat(),
                "scheduled_end": (timezone.now() + timedelta(hours=3)).isoformat(),
                "timezone": "UTC",
                "recurrence": "none",
                "occurrences": 2,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @override_settings(
        LIVEKIT_API_KEY="test-api-key",
        LIVEKIT_API_SECRET="test-secret-32-chars-minimum-value",
        LIVEKIT_URL="wss://livekit.example.test",
        LIVEKIT_TOKEN_TTL_SECONDS=600,
    )
    def test_participant_can_fetch_join_token(self):
        meeting = VideoMeeting.objects.create(
            organizer=self.internal_user,
            case=self.case,
            title="Live interview",
            scheduled_start=timezone.now() - timedelta(minutes=1),
            scheduled_end=timezone.now() + timedelta(minutes=30),
            timezone="UTC",
        )
        meeting.participants.create(user=self.internal_user, role="host")
        meeting.participants.create(user=self.candidate, role="candidate")

        self.client.force_authenticate(self.candidate)
        response = self.client.get(reverse("video-meeting-join-token", kwargs={"pk": meeting.pk}))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("token", response.data)
        self.assertEqual(response.data["room_name"], meeting.livekit_room_name)

    @override_settings(
        LIVEKIT_API_KEY="",
        LIVEKIT_API_SECRET="",
        LIVEKIT_URL="",
    )
    def test_join_token_returns_503_when_livekit_not_configured(self):
        meeting = VideoMeeting.objects.create(
            organizer=self.internal_user,
            case=self.case,
            title="Live interview",
            scheduled_start=timezone.now() - timedelta(minutes=1),
            scheduled_end=timezone.now() + timedelta(minutes=30),
            timezone="UTC",
        )
        meeting.participants.create(user=self.internal_user, role="host")
        meeting.participants.create(user=self.candidate, role="candidate")

        self.client.force_authenticate(self.candidate)
        response = self.client.get(reverse("video-meeting-join-token", kwargs={"pk": meeting.pk}))
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)

    def test_reminder_task_completes_past_meetings(self):
        meeting = VideoMeeting.objects.create(
            organizer=self.internal_user,
            case=self.case,
            title="Expired interview",
            scheduled_start=timezone.now() - timedelta(hours=2),
            scheduled_end=timezone.now() - timedelta(minutes=1),
            timezone="UTC",
        )
        meeting.participants.create(user=self.internal_user, role="host")
        meeting.participants.create(user=self.candidate, role="candidate")

        result = process_video_meeting_reminders()
        meeting.refresh_from_db()

        self.assertEqual(meeting.status, VideoMeeting.STATUS_COMPLETED)
        self.assertGreaterEqual(result["completed"], 1)

    def test_calendar_ics_endpoint_returns_file(self):
        meeting = VideoMeeting.objects.create(
            organizer=self.internal_user,
            case=self.case,
            title="Calendar Interview",
            scheduled_start=timezone.now() + timedelta(minutes=30),
            scheduled_end=timezone.now() + timedelta(minutes=90),
            timezone="UTC",
        )
        meeting.participants.create(user=self.internal_user, role="host")
        meeting.participants.create(user=self.candidate, role="candidate")

        response = self.client.get(reverse("video-meeting-calendar-ics", kwargs={"pk": meeting.pk}))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("text/calendar", response["Content-Type"])
        self.assertIn("BEGIN:VCALENDAR", response.content.decode("utf-8"))
        self.assertIn("SUMMARY:Calendar Interview", response.content.decode("utf-8"))

    @override_settings(NOTIFICATIONS_SMS_ENABLED=False)
    @patch("apps.notifications.services.send_mail", return_value=1)
    def test_notify_meeting_start_now_is_idempotent(self, _send_mail):
        meeting = VideoMeeting.objects.create(
            organizer=self.internal_user,
            case=self.case,
            title="Idempotent start-now reminder",
            status=VideoMeeting.STATUS_ONGOING,
            scheduled_start=timezone.now() - timedelta(minutes=1),
            scheduled_end=timezone.now() + timedelta(minutes=20),
            timezone="UTC",
        )
        meeting.participants.create(user=self.internal_user, role="host")
        meeting.participants.create(user=self.candidate, role="candidate")
        Notification.objects.filter(metadata__event_type="video_call_start_now").delete()

        notify_meeting_start_now(meeting)
        notify_meeting_start_now(meeting)

        notifications = Notification.objects.filter(
            metadata__event_type="video_call_start_now",
        )
        self.assertEqual(notifications.count(), 4)
        self.assertEqual(
            set(notifications.values_list("notification_type", flat=True)),
            {"in_app", "email"},
        )
        idempotency_keys = set(
            notifications.values_list("metadata__idempotency_key", flat=True),
        )
        self.assertEqual(len(idempotency_keys), 1)

    @override_settings(NOTIFICATIONS_SMS_ENABLED=False)
    @patch("apps.notifications.services.send_mail", return_value=1)
    def test_notify_meeting_updated_is_idempotent(self, _send_mail):
        meeting = VideoMeeting.objects.create(
            organizer=self.internal_user,
            case=self.case,
            title="Idempotent updated notification",
            status=VideoMeeting.STATUS_SCHEDULED,
            scheduled_start=timezone.now() + timedelta(hours=2),
            scheduled_end=timezone.now() + timedelta(hours=3),
            timezone="UTC",
        )
        meeting.participants.create(user=self.internal_user, role="host")
        meeting.participants.create(user=self.candidate, role="candidate")
        Notification.objects.filter(metadata__event_type="video_call_updated").delete()

        notify_meeting_updated(meeting)
        notify_meeting_updated(meeting)

        notifications = Notification.objects.filter(
            metadata__event_type="video_call_updated",
        )
        self.assertEqual(notifications.count(), 4)
        self.assertEqual(
            set(notifications.values_list("notification_type", flat=True)),
            {"in_app", "email"},
        )
        idempotency_keys = set(
            notifications.values_list("metadata__idempotency_key", flat=True),
        )
        self.assertEqual(len(idempotency_keys), 1)
        self.assertEqual(_send_mail.call_count, 2)

    @override_settings(NOTIFICATIONS_SMS_ENABLED=False)
    @patch("apps.notifications.services.send_mail", return_value=1)
    def test_notify_meeting_cancelled_is_idempotent(self, _send_mail):
        meeting = VideoMeeting.objects.create(
            organizer=self.internal_user,
            case=self.case,
            title="Idempotent cancelled notification",
            status=VideoMeeting.STATUS_CANCELLED,
            scheduled_start=timezone.now() + timedelta(hours=2),
            scheduled_end=timezone.now() + timedelta(hours=3),
            timezone="UTC",
            cancellation_reason="Panel withdrawn",
        )
        meeting.participants.create(user=self.internal_user, role="host")
        meeting.participants.create(user=self.candidate, role="candidate")
        Notification.objects.filter(metadata__event_type="video_call_cancelled").delete()

        notify_meeting_cancelled(meeting)
        notify_meeting_cancelled(meeting)

        notifications = Notification.objects.filter(
            metadata__event_type="video_call_cancelled",
        )
        self.assertEqual(notifications.count(), 4)
        self.assertEqual(
            set(notifications.values_list("notification_type", flat=True)),
            {"in_app", "email"},
        )
        idempotency_keys = set(
            notifications.values_list("metadata__idempotency_key", flat=True),
        )
        self.assertEqual(len(idempotency_keys), 1)
        self.assertEqual(_send_mail.call_count, 2)

    @override_settings(NOTIFICATIONS_SMS_ENABLED=False)
    @patch("apps.notifications.services.send_mail", return_value=1)
    def test_reminder_task_retry_does_not_duplicate_video_call_reminder_notifications(
        self,
        _send_mail,
    ):
        meeting = VideoMeeting.objects.create(
            organizer=self.internal_user,
            case=self.case,
            title="Retry-safe soon reminder",
            scheduled_start=timezone.now() + timedelta(minutes=4),
            scheduled_end=timezone.now() + timedelta(minutes=34),
            timezone="UTC",
            reminder_before_minutes=5,
        )
        meeting.participants.create(user=self.internal_user, role="host")
        meeting.participants.create(user=self.candidate, role="candidate")
        Notification.objects.filter(metadata__event_type="video_call_reminder").delete()

        first_stats = process_video_meeting_reminders()
        self.assertEqual(first_stats["soon"], 1)

        first_notifications = Notification.objects.filter(
            metadata__event_type="video_call_reminder",
        )
        self.assertEqual(first_notifications.count(), 4)
        first_idempotency_keys = set(
            first_notifications.values_list("metadata__idempotency_key", flat=True),
        )
        self.assertEqual(len(first_idempotency_keys), 1)
        self.assertEqual(_send_mail.call_count, 2)

        # Simulate a retry edge where scheduler state is reopened for the same reminder window.
        VideoMeeting.objects.filter(id=meeting.id).update(
            reminder_before_sent_at=None,
            reminder_before_next_retry_at=None,
            updated_at=timezone.now(),
        )

        second_stats = process_video_meeting_reminders()
        self.assertEqual(second_stats["soon"], 1)

        final_notifications = Notification.objects.filter(
            metadata__event_type="video_call_reminder",
        )
        self.assertEqual(final_notifications.count(), 4)
        final_idempotency_keys = set(
            final_notifications.values_list("metadata__idempotency_key", flat=True),
        )
        self.assertEqual(final_idempotency_keys, first_idempotency_keys)
        self.assertEqual(_send_mail.call_count, 2)

    @override_settings(NOTIFICATIONS_SMS_ENABLED=False)
    @patch("apps.notifications.services.send_mail", return_value=1)
    def test_time_up_retry_does_not_duplicate_video_call_time_up_notifications(
        self,
        _send_mail,
    ):
        meeting = VideoMeeting.objects.create(
            organizer=self.internal_user,
            case=self.case,
            title="Retry-safe time-up reminder",
            status=VideoMeeting.STATUS_COMPLETED,
            scheduled_start=timezone.now() - timedelta(hours=1),
            scheduled_end=timezone.now() - timedelta(minutes=1),
            timezone="UTC",
        )
        meeting.participants.create(user=self.internal_user, role="host")
        meeting.participants.create(user=self.candidate, role="candidate")
        Notification.objects.filter(metadata__event_type="video_call_time_up").delete()

        first_stats = process_video_meeting_reminders()
        self.assertEqual(first_stats["completed"], 1)

        first_notifications = Notification.objects.filter(
            metadata__event_type="video_call_time_up",
        )
        self.assertEqual(first_notifications.count(), 4)
        first_idempotency_keys = set(
            first_notifications.values_list("metadata__idempotency_key", flat=True),
        )
        self.assertEqual(len(first_idempotency_keys), 1)
        self.assertEqual(_send_mail.call_count, 2)

        VideoMeeting.objects.filter(id=meeting.id).update(
            reminder_time_up_sent_at=None,
            reminder_time_up_next_retry_at=None,
            updated_at=timezone.now(),
        )

        second_stats = process_video_meeting_reminders()
        self.assertEqual(second_stats["completed"], 1)

        final_notifications = Notification.objects.filter(
            metadata__event_type="video_call_time_up",
        )
        self.assertEqual(final_notifications.count(), 4)
        final_idempotency_keys = set(
            final_notifications.values_list("metadata__idempotency_key", flat=True),
        )
        self.assertEqual(final_idempotency_keys, first_idempotency_keys)
        self.assertEqual(_send_mail.call_count, 2)

    def test_reminder_task_uses_per_meeting_lead_minutes(self):
        starts_in_ten = VideoMeeting.objects.create(
            organizer=self.internal_user,
            case=self.case,
            title="Ten minute meeting",
            scheduled_start=timezone.now() + timedelta(minutes=10),
            scheduled_end=timezone.now() + timedelta(minutes=40),
            timezone="UTC",
            reminder_before_minutes=5,
        )
        starts_in_ten.participants.create(user=self.internal_user, role="host")
        starts_in_ten.participants.create(user=self.candidate, role="candidate")

        starts_in_four = VideoMeeting.objects.create(
            organizer=self.internal_user,
            case=self.case,
            title="Four minute meeting",
            scheduled_start=timezone.now() + timedelta(minutes=4),
            scheduled_end=timezone.now() + timedelta(minutes=34),
            timezone="UTC",
            reminder_before_minutes=5,
        )
        starts_in_four.participants.create(user=self.internal_user, role="host")
        starts_in_four.participants.create(user=self.candidate, role="candidate")

        result = process_video_meeting_reminders()
        starts_in_ten.refresh_from_db()
        starts_in_four.refresh_from_db()

        self.assertEqual(result["soon"], 1)
        self.assertIsNone(starts_in_ten.reminder_before_sent_at)
        self.assertIsNotNone(starts_in_four.reminder_before_sent_at)

    def test_reminder_task_resets_claim_when_soon_notification_fails(self):
        meeting = VideoMeeting.objects.create(
            organizer=self.internal_user,
            case=self.case,
            title="Soon reminder failure retry",
            scheduled_start=timezone.now() + timedelta(minutes=4),
            scheduled_end=timezone.now() + timedelta(minutes=34),
            timezone="UTC",
            reminder_before_minutes=5,
        )
        meeting.participants.create(user=self.internal_user, role="host")
        meeting.participants.create(user=self.candidate, role="candidate")

        with patch("apps.video_calls.tasks.notify_meeting_starting_soon", side_effect=RuntimeError("delivery failed")):
            stats = process_video_meeting_reminders()

        meeting.refresh_from_db()
        self.assertEqual(stats["soon"], 0)
        self.assertEqual(stats["soon_failed"], 1)
        self.assertIsNone(meeting.reminder_before_sent_at)
        self.assertEqual(meeting.reminder_before_failure_count, 1)
        self.assertIsNotNone(meeting.reminder_before_last_failure_at)
        self.assertIsNotNone(meeting.reminder_before_next_retry_at)

    @override_settings(VIDEO_CALLS_REMINDER_RETRY_MAX_ATTEMPTS=2)
    def test_reminder_task_skips_soon_notification_after_max_failures(self):
        meeting = VideoMeeting.objects.create(
            organizer=self.internal_user,
            case=self.case,
            title="Skip after max failures",
            scheduled_start=timezone.now() + timedelta(minutes=4),
            scheduled_end=timezone.now() + timedelta(minutes=34),
            timezone="UTC",
            reminder_before_minutes=5,
            reminder_before_failure_count=2,
        )
        meeting.participants.create(user=self.internal_user, role="host")
        meeting.participants.create(user=self.candidate, role="candidate")

        with patch("apps.video_calls.tasks.notify_meeting_starting_soon") as notify_mock:
            stats = process_video_meeting_reminders()

        meeting.refresh_from_db()
        self.assertEqual(stats["soon"], 0)
        notify_mock.assert_not_called()
        self.assertIsNone(meeting.reminder_before_sent_at)

    def test_reminder_task_skips_soon_notification_before_retry_window(self):
        meeting = VideoMeeting.objects.create(
            organizer=self.internal_user,
            case=self.case,
            title="Skip before retry window",
            scheduled_start=timezone.now() + timedelta(minutes=4),
            scheduled_end=timezone.now() + timedelta(minutes=34),
            timezone="UTC",
            reminder_before_minutes=5,
            reminder_before_failure_count=1,
            reminder_before_next_retry_at=timezone.now() + timedelta(minutes=2),
        )
        meeting.participants.create(user=self.internal_user, role="host")
        meeting.participants.create(user=self.candidate, role="candidate")

        with patch("apps.video_calls.tasks.notify_meeting_starting_soon") as notify_mock:
            stats = process_video_meeting_reminders()

        meeting.refresh_from_db()
        self.assertEqual(stats["soon"], 0)
        notify_mock.assert_not_called()
        self.assertIsNone(meeting.reminder_before_sent_at)

    def test_start_now_notification_failure_records_retry_state(self):
        meeting = VideoMeeting.objects.create(
            organizer=self.internal_user,
            case=self.case,
            title="Start now failure retry",
            status=VideoMeeting.STATUS_ONGOING,
            scheduled_start=timezone.now() - timedelta(minutes=1),
            scheduled_end=timezone.now() + timedelta(minutes=29),
            timezone="UTC",
        )
        meeting.participants.create(user=self.internal_user, role="host")
        meeting.participants.create(user=self.candidate, role="candidate")

        with patch("apps.video_calls.tasks.notify_meeting_start_now", side_effect=RuntimeError("start delivery failed")):
            stats = process_video_meeting_reminders()

        meeting.refresh_from_db()
        self.assertEqual(stats["start_now"], 0)
        self.assertEqual(stats["start_now_failed"], 1)
        self.assertIsNone(meeting.reminder_start_sent_at)
        self.assertEqual(meeting.reminder_start_failure_count, 1)
        self.assertIsNotNone(meeting.reminder_start_last_failure_at)
        self.assertIsNotNone(meeting.reminder_start_next_retry_at)

    @override_settings(VIDEO_CALLS_REMINDER_RETRY_MAX_ATTEMPTS=1)
    def test_start_now_notification_skipped_after_max_failures(self):
        meeting = VideoMeeting.objects.create(
            organizer=self.internal_user,
            case=self.case,
            title="Start now max failures",
            status=VideoMeeting.STATUS_ONGOING,
            scheduled_start=timezone.now() - timedelta(minutes=1),
            scheduled_end=timezone.now() + timedelta(minutes=29),
            timezone="UTC",
            reminder_start_failure_count=1,
        )
        meeting.participants.create(user=self.internal_user, role="host")
        meeting.participants.create(user=self.candidate, role="candidate")

        with patch("apps.video_calls.tasks.notify_meeting_start_now") as notify_mock:
            stats = process_video_meeting_reminders()

        meeting.refresh_from_db()
        self.assertEqual(stats["start_now"], 0)
        notify_mock.assert_not_called()
        self.assertIsNone(meeting.reminder_start_sent_at)

    def test_time_up_notification_failure_records_retry_state(self):
        meeting = VideoMeeting.objects.create(
            organizer=self.internal_user,
            case=self.case,
            title="Time up failure retry",
            status=VideoMeeting.STATUS_COMPLETED,
            scheduled_start=timezone.now() - timedelta(hours=1),
            scheduled_end=timezone.now() - timedelta(minutes=1),
            timezone="UTC",
        )
        meeting.participants.create(user=self.internal_user, role="host")
        meeting.participants.create(user=self.candidate, role="candidate")

        with patch("apps.video_calls.tasks.notify_meeting_time_up", side_effect=RuntimeError("time up delivery failed")):
            stats = process_video_meeting_reminders()

        meeting.refresh_from_db()
        self.assertEqual(stats["completed"], 0)
        self.assertEqual(stats["completed_failed"], 1)
        self.assertIsNone(meeting.reminder_time_up_sent_at)
        self.assertEqual(meeting.reminder_time_up_failure_count, 1)
        self.assertIsNotNone(meeting.reminder_time_up_last_failure_at)
        self.assertIsNotNone(meeting.reminder_time_up_next_retry_at)

    @override_settings(VIDEO_CALLS_REMINDER_RETRY_MAX_ATTEMPTS=1)
    def test_time_up_notification_skipped_after_max_failures(self):
        meeting = VideoMeeting.objects.create(
            organizer=self.internal_user,
            case=self.case,
            title="Time up max failures",
            status=VideoMeeting.STATUS_COMPLETED,
            scheduled_start=timezone.now() - timedelta(hours=1),
            scheduled_end=timezone.now() - timedelta(minutes=1),
            timezone="UTC",
            reminder_time_up_failure_count=1,
        )
        meeting.participants.create(user=self.internal_user, role="host")
        meeting.participants.create(user=self.candidate, role="candidate")

        with patch("apps.video_calls.tasks.notify_meeting_time_up") as notify_mock:
            stats = process_video_meeting_reminders()

        meeting.refresh_from_db()
        self.assertEqual(stats["completed"], 0)
        notify_mock.assert_not_called()
        self.assertIsNone(meeting.reminder_time_up_sent_at)

    def test_reschedule_rejects_duration_over_eight_hours(self):
        meeting = VideoMeeting.objects.create(
            organizer=self.internal_user,
            case=self.case,
            title="Long interview",
            scheduled_start=timezone.now() + timedelta(hours=2),
            scheduled_end=timezone.now() + timedelta(hours=3),
            timezone="UTC",
        )
        meeting.participants.create(user=self.internal_user, role="host")
        meeting.participants.create(user=self.candidate, role="candidate")

        response = self.client.post(
            reverse("video-meeting-reschedule", kwargs={"pk": meeting.pk}),
            data={
                "scheduled_start": (timezone.now() + timedelta(hours=4)).isoformat(),
                "scheduled_end": (timezone.now() + timedelta(hours=13)).isoformat(),
                "timezone": "UTC",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_extend_rejects_when_total_duration_exceeds_eight_hours(self):
        meeting = VideoMeeting.objects.create(
            organizer=self.internal_user,
            case=self.case,
            title="Near max duration interview",
            scheduled_start=timezone.now() + timedelta(hours=1),
            scheduled_end=timezone.now() + timedelta(hours=8, minutes=30),
            timezone="UTC",
        )
        meeting.participants.create(user=self.internal_user, role="host")
        meeting.participants.create(user=self.candidate, role="candidate")

        response = self.client.post(
            reverse("video-meeting-extend", kwargs={"pk": meeting.pk}),
            data={"minutes": 60},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_meeting_events_endpoint_returns_recent_events(self):
        meeting = VideoMeeting.objects.create(
            organizer=self.internal_user,
            case=self.case,
            title="Event timeline interview",
            scheduled_start=timezone.now() + timedelta(hours=1),
            scheduled_end=timezone.now() + timedelta(hours=2),
            timezone="UTC",
        )
        meeting.participants.create(user=self.internal_user, role="host")
        meeting.participants.create(user=self.candidate, role="candidate")

        self.client.post(reverse("video-meeting-start", kwargs={"pk": meeting.pk}), data={}, format="json")
        self.client.post(reverse("video-meeting-complete", kwargs={"pk": meeting.pk}), data={}, format="json")

        response = self.client.get(reverse("video-meeting-events", kwargs={"pk": meeting.pk}))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        actions = [item["action"] for item in response.data]
        self.assertIn(VideoMeetingEvent.ACTION_STARTED, actions)
        self.assertIn(VideoMeetingEvent.ACTION_COMPLETED, actions)

    def test_meeting_events_endpoint_can_include_series_events(self):
        base_start = timezone.now() + timedelta(hours=3)
        response = self.client.post(
            reverse("video-meeting-schedule-series"),
            data={
                "title": "Series timeline",
                "description": "Series for timeline check.",
                "case": str(self.case.id),
                "scheduled_start": base_start.isoformat(),
                "scheduled_end": (base_start + timedelta(hours=1)).isoformat(),
                "timezone": "UTC",
                "recurrence": "daily",
                "occurrences": 2,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        anchor_id = response.data["results"][0]["id"]

        self.client.post(
            reverse("video-meeting-cancel-series", kwargs={"pk": anchor_id}),
            data={"scope": "all", "reason": "Cancelled for timeline test."},
            format="json",
        )

        events_response = self.client.get(
            reverse("video-meeting-events", kwargs={"pk": anchor_id}),
            data={"series": "1"},
        )
        self.assertEqual(events_response.status_code, status.HTTP_200_OK)
        cancelled_all_events = [
            event
            for event in events_response.data
            if event["action"] == VideoMeetingEvent.ACTION_CANCELLED and event["scope"] == VideoMeetingEvent.SCOPE_ALL
        ]
        self.assertGreaterEqual(len(cancelled_all_events), 1)

    def test_complete_requires_meeting_to_be_in_progress(self):
        meeting = VideoMeeting.objects.create(
            organizer=self.internal_user,
            case=self.case,
            title="Cannot complete scheduled",
            scheduled_start=timezone.now() + timedelta(hours=1),
            scheduled_end=timezone.now() + timedelta(hours=2),
            timezone="UTC",
        )
        meeting.participants.create(user=self.internal_user, role="host")
        meeting.participants.create(user=self.candidate, role="candidate")

        response = self.client.post(
            reverse("video-meeting-complete", kwargs={"pk": meeting.pk}),
            data={},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        meeting.refresh_from_db()
        self.assertEqual(meeting.status, VideoMeeting.STATUS_SCHEDULED)

    def test_cancel_rejects_completed_meeting(self):
        meeting = VideoMeeting.objects.create(
            organizer=self.internal_user,
            case=self.case,
            title="Cannot cancel completed",
            scheduled_start=timezone.now() - timedelta(minutes=5),
            scheduled_end=timezone.now() + timedelta(minutes=30),
            timezone="UTC",
        )
        meeting.participants.create(user=self.internal_user, role="host")
        meeting.participants.create(user=self.candidate, role="candidate")

        start_response = self.client.post(reverse("video-meeting-start", kwargs={"pk": meeting.pk}), data={}, format="json")
        self.assertEqual(start_response.status_code, status.HTTP_200_OK)
        complete_response = self.client.post(reverse("video-meeting-complete", kwargs={"pk": meeting.pk}), data={}, format="json")
        self.assertEqual(complete_response.status_code, status.HTTP_200_OK)

        cancel_response = self.client.post(
            reverse("video-meeting-cancel", kwargs={"pk": meeting.pk}),
            data={"reason": "Too late"},
            format="json",
        )
        self.assertEqual(cancel_response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_reschedule_rejects_non_scheduled_meeting(self):
        meeting = VideoMeeting.objects.create(
            organizer=self.internal_user,
            case=self.case,
            title="Cannot reschedule ongoing",
            status=VideoMeeting.STATUS_ONGOING,
            scheduled_start=timezone.now() - timedelta(minutes=10),
            scheduled_end=timezone.now() + timedelta(minutes=20),
            timezone="UTC",
        )
        meeting.participants.create(user=self.internal_user, role="host")
        meeting.participants.create(user=self.candidate, role="candidate")

        response = self.client.post(
            reverse("video-meeting-reschedule", kwargs={"pk": meeting.pk}),
            data={
                "scheduled_start": (timezone.now() + timedelta(hours=1)).isoformat(),
                "scheduled_end": (timezone.now() + timedelta(hours=2)).isoformat(),
                "timezone": "UTC",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_reschedule_resets_all_reminder_retry_state(self):
        meeting = VideoMeeting.objects.create(
            organizer=self.internal_user,
            case=self.case,
            title="Reset reminder state on reschedule",
            status=VideoMeeting.STATUS_SCHEDULED,
            scheduled_start=timezone.now() + timedelta(hours=1),
            scheduled_end=timezone.now() + timedelta(hours=2),
            timezone="UTC",
            reminder_before_sent_at=timezone.now(),
            reminder_before_failure_count=2,
            reminder_before_last_failure_at=timezone.now(),
            reminder_before_next_retry_at=timezone.now() + timedelta(minutes=5),
            reminder_start_sent_at=timezone.now(),
            reminder_start_failure_count=1,
            reminder_start_last_failure_at=timezone.now(),
            reminder_start_next_retry_at=timezone.now() + timedelta(minutes=5),
            reminder_time_up_sent_at=timezone.now(),
            reminder_time_up_failure_count=1,
            reminder_time_up_last_failure_at=timezone.now(),
            reminder_time_up_next_retry_at=timezone.now() + timedelta(minutes=5),
        )
        meeting.participants.create(user=self.internal_user, role="host")
        meeting.participants.create(user=self.candidate, role="candidate")

        response = self.client.post(
            reverse("video-meeting-reschedule", kwargs={"pk": meeting.pk}),
            data={
                "scheduled_start": (timezone.now() + timedelta(hours=3)).isoformat(),
                "scheduled_end": (timezone.now() + timedelta(hours=4)).isoformat(),
                "timezone": "UTC",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        meeting.refresh_from_db()
        self.assertIsNone(meeting.reminder_before_sent_at)
        self.assertEqual(meeting.reminder_before_failure_count, 0)
        self.assertIsNone(meeting.reminder_before_last_failure_at)
        self.assertIsNone(meeting.reminder_before_next_retry_at)
        self.assertIsNone(meeting.reminder_start_sent_at)
        self.assertEqual(meeting.reminder_start_failure_count, 0)
        self.assertIsNone(meeting.reminder_start_last_failure_at)
        self.assertIsNone(meeting.reminder_start_next_retry_at)
        self.assertIsNone(meeting.reminder_time_up_sent_at)
        self.assertEqual(meeting.reminder_time_up_failure_count, 0)
        self.assertIsNone(meeting.reminder_time_up_last_failure_at)
        self.assertIsNone(meeting.reminder_time_up_next_retry_at)

    def test_reschedule_series_resets_all_reminder_retry_state(self):
        base_start = timezone.now() + timedelta(hours=2)
        response = self.client.post(
            reverse("video-meeting-schedule-series"),
            data={
                "title": "Series reminder reset",
                "description": "Series reset checks.",
                "case": str(self.case.id),
                "scheduled_start": base_start.isoformat(),
                "scheduled_end": (base_start + timedelta(hours=1)).isoformat(),
                "timezone": "UTC",
                "recurrence": "daily",
                "occurrences": 2,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        anchor_id = response.data["results"][0]["id"]

        meetings = list(VideoMeeting.objects.filter(title="Series reminder reset").order_by("scheduled_start"))
        self.assertEqual(len(meetings), 2)
        for item in meetings:
            item.reminder_before_sent_at = timezone.now()
            item.reminder_before_failure_count = 1
            item.reminder_before_last_failure_at = timezone.now()
            item.reminder_before_next_retry_at = timezone.now() + timedelta(minutes=2)
            item.reminder_start_sent_at = timezone.now()
            item.reminder_start_failure_count = 1
            item.reminder_start_last_failure_at = timezone.now()
            item.reminder_start_next_retry_at = timezone.now() + timedelta(minutes=2)
            item.reminder_time_up_sent_at = timezone.now()
            item.reminder_time_up_failure_count = 1
            item.reminder_time_up_last_failure_at = timezone.now()
            item.reminder_time_up_next_retry_at = timezone.now() + timedelta(minutes=2)
            item.save(
                update_fields=[
                    "reminder_before_sent_at",
                    "reminder_before_failure_count",
                    "reminder_before_last_failure_at",
                    "reminder_before_next_retry_at",
                    "reminder_start_sent_at",
                    "reminder_start_failure_count",
                    "reminder_start_last_failure_at",
                    "reminder_start_next_retry_at",
                    "reminder_time_up_sent_at",
                    "reminder_time_up_failure_count",
                    "reminder_time_up_last_failure_at",
                    "reminder_time_up_next_retry_at",
                    "updated_at",
                ]
            )

        new_anchor_start = base_start + timedelta(days=1, minutes=20)
        reschedule_response = self.client.post(
            reverse("video-meeting-reschedule-series", kwargs={"pk": anchor_id}),
            data={
                "scheduled_start": new_anchor_start.isoformat(),
                "scheduled_end": (new_anchor_start + timedelta(hours=1)).isoformat(),
                "timezone": "UTC",
                "scope": "all",
            },
            format="json",
        )
        self.assertEqual(reschedule_response.status_code, status.HTTP_200_OK)

        for item in VideoMeeting.objects.filter(title="Series reminder reset"):
            self.assertIsNone(item.reminder_before_sent_at)
            self.assertEqual(item.reminder_before_failure_count, 0)
            self.assertIsNone(item.reminder_before_last_failure_at)
            self.assertIsNone(item.reminder_before_next_retry_at)
            self.assertIsNone(item.reminder_start_sent_at)
            self.assertEqual(item.reminder_start_failure_count, 0)
            self.assertIsNone(item.reminder_start_last_failure_at)
            self.assertIsNone(item.reminder_start_next_retry_at)
            self.assertIsNone(item.reminder_time_up_sent_at)
            self.assertEqual(item.reminder_time_up_failure_count, 0)
            self.assertIsNone(item.reminder_time_up_last_failure_at)
            self.assertIsNone(item.reminder_time_up_next_retry_at)

    def test_reminder_health_requires_admin_user(self):
        self.client.force_authenticate(self.candidate)
        response = self.client.get(reverse("video-meeting-reminder-health"))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("Only admin users", str(response.data.get("error", "")))

        self.client.force_authenticate(self.internal_user)
        response = self.client.get(reverse("video-meeting-reminder-health"))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("Only admin users", str(response.data.get("error", "")))

        self.client.force_authenticate(self.admin_user)
        response = self.client.get(reverse("video-meeting-reminder-health"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    @override_settings(VIDEO_CALLS_REMINDER_RETRY_MAX_ATTEMPTS=3)
    def test_reminder_health_returns_retry_counts(self):
        self.client.force_authenticate(self.admin_user)
        now = timezone.now()

        VideoMeeting.objects.create(
            organizer=self.internal_user,
            case=self.case,
            title="Soon pending",
            status=VideoMeeting.STATUS_SCHEDULED,
            scheduled_start=now + timedelta(minutes=10),
            scheduled_end=now + timedelta(minutes=40),
            timezone="UTC",
            reminder_before_failure_count=1,
            reminder_before_next_retry_at=now - timedelta(minutes=1),
        )
        VideoMeeting.objects.create(
            organizer=self.internal_user,
            case=self.case,
            title="Soon exhausted",
            status=VideoMeeting.STATUS_SCHEDULED,
            scheduled_start=now + timedelta(minutes=20),
            scheduled_end=now + timedelta(minutes=50),
            timezone="UTC",
            reminder_before_failure_count=3,
        )
        VideoMeeting.objects.create(
            organizer=self.internal_user,
            case=self.case,
            title="Start pending",
            status=VideoMeeting.STATUS_ONGOING,
            scheduled_start=now - timedelta(minutes=5),
            scheduled_end=now + timedelta(minutes=25),
            timezone="UTC",
            reminder_start_failure_count=2,
            reminder_start_next_retry_at=now - timedelta(seconds=30),
        )
        VideoMeeting.objects.create(
            organizer=self.internal_user,
            case=self.case,
            title="Start exhausted",
            status=VideoMeeting.STATUS_ONGOING,
            scheduled_start=now - timedelta(minutes=10),
            scheduled_end=now + timedelta(minutes=10),
            timezone="UTC",
            reminder_start_failure_count=3,
        )
        VideoMeeting.objects.create(
            organizer=self.internal_user,
            case=self.case,
            title="Time up pending",
            status=VideoMeeting.STATUS_COMPLETED,
            scheduled_start=now - timedelta(hours=1),
            scheduled_end=now - timedelta(minutes=20),
            timezone="UTC",
            reminder_time_up_failure_count=1,
            reminder_time_up_next_retry_at=now - timedelta(minutes=2),
        )
        VideoMeeting.objects.create(
            organizer=self.internal_user,
            case=self.case,
            title="Time up exhausted",
            status=VideoMeeting.STATUS_COMPLETED,
            scheduled_start=now - timedelta(hours=2),
            scheduled_end=now - timedelta(hours=1, minutes=30),
            timezone="UTC",
            reminder_time_up_failure_count=3,
        )

        response = self.client.get(reverse("video-meeting-reminder-health"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["soon_retry_pending"], 1)
        self.assertEqual(response.data["soon_retry_exhausted"], 1)
        self.assertEqual(response.data["start_now_retry_pending"], 1)
        self.assertEqual(response.data["start_now_retry_exhausted"], 1)
        self.assertEqual(response.data["time_up_retry_pending"], 1)
        self.assertEqual(response.data["time_up_retry_exhausted"], 1)

    @override_settings(VIDEO_CALLS_REMINDER_RETRY_MAX_ATTEMPTS=5)
    def test_reminder_health_contract_payload_contains_required_fields(self):
        self.client.force_authenticate(self.admin_user)
        response = self.client.get(reverse("video-meeting-reminder-health"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        expected_keys = {
            "generated_at",
            "max_retries",
            "soon_retry_pending",
            "soon_retry_exhausted",
            "start_now_retry_pending",
            "start_now_retry_exhausted",
            "time_up_retry_pending",
            "time_up_retry_exhausted",
        }
        self.assertEqual(set(response.data.keys()), expected_keys)
        self.assertEqual(response.data["max_retries"], 5)
        self.assertIsNotNone(datetime.fromisoformat(response.data["generated_at"]))

        for key in expected_keys - {"generated_at", "max_retries"}:
            self.assertIsInstance(response.data[key], int)
            self.assertGreaterEqual(response.data[key], 0)

    @override_settings(VIDEO_CALLS_REMINDER_RETRY_MAX_ATTEMPTS=0)
    def test_reminder_health_enforces_retry_floor_when_setting_invalid(self):
        self.client.force_authenticate(self.admin_user)
        now = timezone.now()
        VideoMeeting.objects.create(
            organizer=self.internal_user,
            case=self.case,
            title="Soon exhausted via floor",
            status=VideoMeeting.STATUS_SCHEDULED,
            scheduled_start=now + timedelta(minutes=15),
            scheduled_end=now + timedelta(minutes=45),
            timezone="UTC",
            reminder_before_failure_count=1,
            reminder_before_next_retry_at=now - timedelta(minutes=1),
        )
        VideoMeeting.objects.create(
            organizer=self.internal_user,
            case=self.case,
            title="Start exhausted via floor",
            status=VideoMeeting.STATUS_ONGOING,
            scheduled_start=now - timedelta(minutes=5),
            scheduled_end=now + timedelta(minutes=20),
            timezone="UTC",
            reminder_start_failure_count=1,
            reminder_start_next_retry_at=now - timedelta(minutes=1),
        )
        VideoMeeting.objects.create(
            organizer=self.internal_user,
            case=self.case,
            title="Time up exhausted via floor",
            status=VideoMeeting.STATUS_COMPLETED,
            scheduled_start=now - timedelta(hours=1),
            scheduled_end=now - timedelta(minutes=10),
            timezone="UTC",
            reminder_time_up_failure_count=1,
            reminder_time_up_next_retry_at=now - timedelta(minutes=1),
        )

        response = self.client.get(reverse("video-meeting-reminder-health"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["max_retries"], 1)
        self.assertEqual(response.data["soon_retry_pending"], 0)
        self.assertEqual(response.data["soon_retry_exhausted"], 1)
        self.assertEqual(response.data["start_now_retry_pending"], 0)
        self.assertEqual(response.data["start_now_retry_exhausted"], 1)
        self.assertEqual(response.data["time_up_retry_pending"], 0)
        self.assertEqual(response.data["time_up_retry_exhausted"], 1)

    def test_joinability_respects_configured_join_grace_minutes(self):
        meeting = VideoMeeting.objects.create(
            organizer=self.internal_user,
            case=self.case,
            title="Grace window check",
            status=VideoMeeting.STATUS_ONGOING,
            scheduled_start=timezone.now() - timedelta(hours=1),
            scheduled_end=timezone.now() - timedelta(minutes=10),
            timezone="UTC",
        )

        with override_settings(VIDEO_CALLS_JOIN_GRACE_MINUTES=5):
            self.assertFalse(meeting.is_joinable)

        with override_settings(VIDEO_CALLS_JOIN_GRACE_MINUTES=15):
            self.assertTrue(meeting.is_joinable)

    def test_meeting_participant_unique_constraint(self):
        meeting = VideoMeeting.objects.create(
            organizer=self.internal_user,
            case=self.case,
            title="Unique participant check",
            scheduled_start=timezone.now() + timedelta(hours=1),
            scheduled_end=timezone.now() + timedelta(hours=2),
            timezone="UTC",
        )
        VideoMeetingParticipant.objects.create(
            meeting=meeting,
            user=self.candidate,
            role=VideoMeetingParticipant.ROLE_CANDIDATE,
        )
        with self.assertRaises(IntegrityError):
            VideoMeetingParticipant.objects.create(
                meeting=meeting,
                user=self.candidate,
                role=VideoMeetingParticipant.ROLE_OBSERVER,
            )

    def test_reminder_task_skips_start_notification_if_status_transition_fails(self):
        meeting = VideoMeeting.objects.create(
            organizer=self.internal_user,
            case=self.case,
            title="Start transition failure",
            scheduled_start=timezone.now(),
            scheduled_end=timezone.now() + timedelta(minutes=30),
            timezone="UTC",
        )
        meeting.participants.create(user=self.internal_user, role="host")
        meeting.participants.create(user=self.candidate, role="candidate")

        with patch.object(VideoMeeting, "mark_ongoing", side_effect=ValidationError("transition blocked")):
            with patch("apps.video_calls.tasks.notify_meeting_start_now") as notify_mock:
                stats = process_video_meeting_reminders()

        self.assertEqual(stats["start_now"], 0)
        notify_mock.assert_not_called()

    def test_reminder_task_skips_time_up_notification_if_completion_transition_fails(self):
        meeting = VideoMeeting.objects.create(
            organizer=self.internal_user,
            case=self.case,
            title="Completion transition failure",
            status=VideoMeeting.STATUS_ONGOING,
            scheduled_start=timezone.now() - timedelta(hours=1),
            scheduled_end=timezone.now() - timedelta(minutes=1),
            timezone="UTC",
        )
        meeting.participants.create(user=self.internal_user, role="host")
        meeting.participants.create(user=self.candidate, role="candidate")

        with patch.object(VideoMeeting, "mark_completed", side_effect=ValidationError("completion blocked")):
            with patch("apps.video_calls.tasks.notify_meeting_time_up") as notify_mock:
                stats = process_video_meeting_reminders()

        meeting.refresh_from_db()
        self.assertEqual(meeting.status, VideoMeeting.STATUS_ONGOING)
        self.assertEqual(stats["completed"], 0)
        notify_mock.assert_not_called()



