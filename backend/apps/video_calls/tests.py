from datetime import timedelta

from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.applications.models import VettingCase
from apps.authentication.models import User
from apps.video_calls.models import VideoMeeting, VideoMeetingEvent
from apps.video_calls.tasks import process_video_meeting_reminders


class VideoMeetingApiTests(APITestCase):
    def setUp(self):
        self.hr_user = User.objects.create_user(
            email="hr-video-tests@example.com",
            password="SecurePass123!",
            first_name="HR",
            last_name="Manager",
            user_type="hr_manager",
        )
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
        self.client.force_authenticate(self.hr_user)

    def test_hr_can_schedule_video_meeting(self):
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
        self.assertEqual(meeting.organizer, self.hr_user)
        self.assertTrue(meeting.participants.filter(user=self.candidate).exists())
        self.assertEqual(meeting.reminder_before_minutes, 25)
        self.assertTrue(
            meeting.events.filter(action=VideoMeetingEvent.ACTION_CREATED, scope=VideoMeetingEvent.SCOPE_SINGLE).exists()
        )

    def test_hr_can_schedule_meeting_with_participant_emails(self):
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

    def test_hr_can_schedule_daily_series(self):
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

    def test_hr_can_reschedule_future_series_occurrences(self):
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

    def test_hr_can_cancel_all_series_occurrences(self):
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
        LIVEKIT_API_SECRET="test-secret",
        LIVEKIT_URL="wss://livekit.example.test",
        LIVEKIT_TOKEN_TTL_SECONDS=600,
    )
    def test_participant_can_fetch_join_token(self):
        meeting = VideoMeeting.objects.create(
            organizer=self.hr_user,
            case=self.case,
            title="Live interview",
            scheduled_start=timezone.now() - timedelta(minutes=1),
            scheduled_end=timezone.now() + timedelta(minutes=30),
            timezone="UTC",
        )
        meeting.participants.create(user=self.hr_user, role="host")
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
            organizer=self.hr_user,
            case=self.case,
            title="Live interview",
            scheduled_start=timezone.now() - timedelta(minutes=1),
            scheduled_end=timezone.now() + timedelta(minutes=30),
            timezone="UTC",
        )
        meeting.participants.create(user=self.hr_user, role="host")
        meeting.participants.create(user=self.candidate, role="candidate")

        self.client.force_authenticate(self.candidate)
        response = self.client.get(reverse("video-meeting-join-token", kwargs={"pk": meeting.pk}))
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)

    def test_reminder_task_completes_past_meetings(self):
        meeting = VideoMeeting.objects.create(
            organizer=self.hr_user,
            case=self.case,
            title="Expired interview",
            scheduled_start=timezone.now() - timedelta(hours=2),
            scheduled_end=timezone.now() - timedelta(minutes=1),
            timezone="UTC",
        )
        meeting.participants.create(user=self.hr_user, role="host")
        meeting.participants.create(user=self.candidate, role="candidate")

        result = process_video_meeting_reminders()
        meeting.refresh_from_db()

        self.assertEqual(meeting.status, VideoMeeting.STATUS_COMPLETED)
        self.assertGreaterEqual(result["completed"], 1)

    def test_calendar_ics_endpoint_returns_file(self):
        meeting = VideoMeeting.objects.create(
            organizer=self.hr_user,
            case=self.case,
            title="Calendar Interview",
            scheduled_start=timezone.now() + timedelta(minutes=30),
            scheduled_end=timezone.now() + timedelta(minutes=90),
            timezone="UTC",
        )
        meeting.participants.create(user=self.hr_user, role="host")
        meeting.participants.create(user=self.candidate, role="candidate")

        response = self.client.get(reverse("video-meeting-calendar-ics", kwargs={"pk": meeting.pk}))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("text/calendar", response["Content-Type"])
        self.assertIn("BEGIN:VCALENDAR", response.content.decode("utf-8"))
        self.assertIn("SUMMARY:Calendar Interview", response.content.decode("utf-8"))

    def test_reminder_task_uses_per_meeting_lead_minutes(self):
        starts_in_ten = VideoMeeting.objects.create(
            organizer=self.hr_user,
            case=self.case,
            title="Ten minute meeting",
            scheduled_start=timezone.now() + timedelta(minutes=10),
            scheduled_end=timezone.now() + timedelta(minutes=40),
            timezone="UTC",
            reminder_before_minutes=5,
        )
        starts_in_ten.participants.create(user=self.hr_user, role="host")
        starts_in_ten.participants.create(user=self.candidate, role="candidate")

        starts_in_four = VideoMeeting.objects.create(
            organizer=self.hr_user,
            case=self.case,
            title="Four minute meeting",
            scheduled_start=timezone.now() + timedelta(minutes=4),
            scheduled_end=timezone.now() + timedelta(minutes=34),
            timezone="UTC",
            reminder_before_minutes=5,
        )
        starts_in_four.participants.create(user=self.hr_user, role="host")
        starts_in_four.participants.create(user=self.candidate, role="candidate")

        result = process_video_meeting_reminders()
        starts_in_ten.refresh_from_db()
        starts_in_four.refresh_from_db()

        self.assertEqual(result["soon"], 1)
        self.assertIsNone(starts_in_ten.reminder_before_sent_at)
        self.assertIsNotNone(starts_in_four.reminder_before_sent_at)

    def test_reschedule_rejects_duration_over_eight_hours(self):
        meeting = VideoMeeting.objects.create(
            organizer=self.hr_user,
            case=self.case,
            title="Long interview",
            scheduled_start=timezone.now() + timedelta(hours=2),
            scheduled_end=timezone.now() + timedelta(hours=3),
            timezone="UTC",
        )
        meeting.participants.create(user=self.hr_user, role="host")
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
            organizer=self.hr_user,
            case=self.case,
            title="Near max duration interview",
            scheduled_start=timezone.now() + timedelta(hours=1),
            scheduled_end=timezone.now() + timedelta(hours=8, minutes=30),
            timezone="UTC",
        )
        meeting.participants.create(user=self.hr_user, role="host")
        meeting.participants.create(user=self.candidate, role="candidate")

        response = self.client.post(
            reverse("video-meeting-extend", kwargs={"pk": meeting.pk}),
            data={"minutes": 60},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_meeting_events_endpoint_returns_recent_events(self):
        meeting = VideoMeeting.objects.create(
            organizer=self.hr_user,
            case=self.case,
            title="Event timeline interview",
            scheduled_start=timezone.now() + timedelta(hours=1),
            scheduled_end=timezone.now() + timedelta(hours=2),
            timezone="UTC",
        )
        meeting.participants.create(user=self.hr_user, role="host")
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
