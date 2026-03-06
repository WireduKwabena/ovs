from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from apps.applications.models import VettingCase
from apps.authentication.models import User
from apps.interviews.models import InterviewSession
from apps.notifications.interview_alerts import (
    send_completion_summary,
    send_high_deception_alert,
)
from apps.notifications.models import Notification
from apps.notifications.services import NotificationService


class NotificationApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="notify-user@example.com",
            password="Pass1234!",
            first_name="Notify",
            last_name="User",
            user_type="applicant",
        )
        self.other_user = User.objects.create_user(
            email="notify-other@example.com",
            password="Pass1234!",
            first_name="Notify",
            last_name="Other",
            user_type="applicant",
        )

        self.unread = Notification.objects.create(
            recipient=self.user,
            subject="Unread",
            message="Unread notification",
            notification_type="in_app",
            status="sent",
            priority="normal",
        )
        self.read = Notification.objects.create(
            recipient=self.user,
            subject="Read",
            message="Read notification",
            notification_type="email",
            status="read",
            priority="low",
            email_to=self.user.email,
        )
        self.other_users_notification = Notification.objects.create(
            recipient=self.other_user,
            subject="Other user notification",
            message="Should not be visible",
            notification_type="in_app",
            status="sent",
            priority="normal",
        )

        self.client.force_authenticate(self.user)

    def test_list_returns_only_current_user_notifications(self):
        response = self.client.get("/api/notifications/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        subjects = {item["subject"] for item in response.data["results"]}
        self.assertIn("Unread", subjects)
        self.assertNotIn("Read", subjects)
        self.assertNotIn("Other user notification", subjects)

    def test_list_archived_filter_returns_only_archived_notifications(self):
        self.unread.archive()

        response = self.client.get("/api/notifications/?archived=only")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["subject"], "Unread")
        self.assertTrue(response.data["results"][0]["is_archived"])

    def test_list_archived_scope_contract_active_archived_and_all(self):
        self.unread.archive()

        active_response = self.client.get("/api/notifications/?channel=all&archived=active")
        archived_response = self.client.get("/api/notifications/?channel=all&archived=archived")
        all_response = self.client.get("/api/notifications/?channel=all&archived=all")

        self.assertEqual(active_response.status_code, status.HTTP_200_OK)
        self.assertEqual(archived_response.status_code, status.HTTP_200_OK)
        self.assertEqual(all_response.status_code, status.HTTP_200_OK)

        active_subjects = {item["subject"] for item in active_response.data["results"]}
        archived_subjects = {item["subject"] for item in archived_response.data["results"]}
        all_subjects = {item["subject"] for item in all_response.data["results"]}

        self.assertEqual(active_subjects, {"Read"})
        self.assertEqual(archived_subjects, {"Unread"})
        self.assertEqual(all_subjects, {"Unread", "Read"})

    def test_list_archived_invalid_value_defaults_to_active(self):
        self.unread.archive()

        response = self.client.get("/api/notifications/?channel=all&archived=unexpected-value")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        subjects = {item["subject"] for item in response.data["results"]}
        self.assertEqual(subjects, {"Read"})

    def test_list_channel_all_returns_all_delivery_types_for_current_user(self):
        response = self.client.get("/api/notifications/?channel=all")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 2)
        subjects = {item["subject"] for item in response.data["results"]}
        self.assertIn("Unread", subjects)
        self.assertIn("Read", subjects)
        self.assertNotIn("Other user notification", subjects)

    def test_unread_count_excludes_read_notifications(self):
        response = self.client.get("/api/notifications/unread-count/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["unread_count"], 1)

    def test_mark_as_read_marks_selected_notifications(self):
        response = self.client.post(
            "/api/notifications/mark-as-read/",
            {"notification_ids": [self.unread.id]},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.unread.refresh_from_db()
        self.assertEqual(self.unread.status, "read")
        self.assertIsNotNone(self.unread.read_at)

    def test_mark_as_read_without_payload_returns_bad_request(self):
        response = self.client.post("/api/notifications/mark-as-read/", {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)

    def test_mark_all_as_read_marks_only_current_user_notifications(self):
        response = self.client.post("/api/notifications/mark-all-as-read/", {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.unread.refresh_from_db()
        self.read.refresh_from_db()
        self.other_users_notification.refresh_from_db()
        self.assertEqual(self.unread.status, "read")
        self.assertEqual(self.read.status, "read")
        self.assertEqual(self.other_users_notification.status, "sent")

    def test_archive_soft_archives_owned_notification(self):
        response = self.client.delete(f"/api/notifications/{self.unread.id}/archive/")

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.unread.refresh_from_db()
        self.assertTrue(self.unread.is_archived)
        self.assertIsNotNone(self.unread.archived_at)

    def test_cannot_archive_other_users_notification(self):
        response = self.client.delete(
            f"/api/notifications/{self.other_users_notification.id}/archive/"
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(Notification.objects.filter(id=self.other_users_notification.id).exists())

    def test_restore_unarchives_owned_notification(self):
        self.unread.archive()

        response = self.client.post(f"/api/notifications/{self.unread.id}/restore/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.unread.refresh_from_db()
        self.assertFalse(self.unread.is_archived)
        self.assertIsNone(self.unread.archived_at)

    def test_cannot_restore_other_users_notification(self):
        self.other_users_notification.archive()

        response = self.client.post(f"/api/notifications/{self.other_users_notification.id}/restore/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class NotificationServiceTests(TestCase):
    def setUp(self):
        self.hr = User.objects.create_user(
            email="notify-hr@example.com",
            password="Pass1234!",
            first_name="Notify",
            last_name="HR",
            user_type="hr_manager",
            is_staff=True,
        )
        self.applicant = User.objects.create_user(
            email="notify-applicant@example.com",
            password="Pass1234!",
            first_name="Notify",
            last_name="Applicant",
            user_type="applicant",
            phone_number="+15550123456",
        )
        self.case = VettingCase.objects.create(
            applicant=self.applicant,
            assigned_to=self.hr,
            position_applied="Security Analyst",
            department="Risk",
            priority="medium",
            status="under_review",
        )

    @patch("apps.notifications.services.render_to_string", return_value="<p>Hello</p>")
    @patch("apps.notifications.services.send_mail", return_value=1)
    def test_send_application_submitted_creates_in_app_and_email_notifications(
        self,
        _send_mail,
        _render_to_string,
    ):
        result = NotificationService.send_application_submitted(self.case)

        self.assertTrue(result)
        notifications = Notification.objects.filter(
            recipient=self.applicant,
            related_case=self.case,
        )
        self.assertEqual(notifications.count(), 2)
        self.assertEqual(
            set(notifications.values_list("notification_type", flat=True)),
            {"in_app", "email"},
        )

        email_notification = notifications.get(notification_type="email")
        self.assertEqual(email_notification.status, "sent")
        self.assertEqual(email_notification.email_to, self.applicant.email)
        self.assertEqual(email_notification.metadata.get("event_type"), "application_submitted")

    @patch("apps.notifications.services.send_mail", side_effect=RuntimeError("smtp down"))
    def test_send_email_notification_marks_failed_when_mail_raises(self, _send_mail):
        notification = NotificationService._send_email_notification(
            recipient=self.applicant,
            subject="Subject",
            fallback_message="Body",
        )

        self.assertIsNotNone(notification)
        self.assertEqual(notification.status, "failed")
        self.assertEqual(notification.retry_count, 1)
        self.assertIn("smtp down", notification.failure_reason)

    def test_send_email_notification_returns_none_without_email(self):
        result = NotificationService._send_email_notification(
            recipient=SimpleNamespace(email=""),
            subject="Subject",
            fallback_message="Body",
        )

        self.assertIsNone(result)
        self.assertEqual(Notification.objects.count(), 0)

    @patch("apps.notifications.services.render_to_string", return_value="<p>Rejected</p>")
    @patch("apps.notifications.services.send_mail", return_value=1)
    def test_send_rejection_notification_creates_high_priority_records(
        self,
        _send_mail,
        _render_to_string,
    ):
        result = NotificationService.send_rejection_notification(
            self.case,
            reason="Document mismatch",
        )

        self.assertTrue(result)
        notifications = Notification.objects.filter(
            recipient=self.applicant,
            related_case=self.case,
            metadata__event_type="rejection",
        )
        self.assertEqual(notifications.count(), 2)
        self.assertTrue(all(n.priority == "high" for n in notifications))

    def test_send_admin_notification_returns_none_when_admin_missing(self):
        result = NotificationService.send_admin_notification(
            None,
            notification_type="processing_error",
            title="Error",
            message="Something failed",
        )

        self.assertIsNone(result)

    @patch("apps.notifications.services.logger.exception")
    @patch("apps.notifications.services.send_mail", return_value=1)
    def test_send_approval_notification_uses_existing_template(
        self,
        _send_mail,
        mock_logger_exception,
    ):
        result = NotificationService.send_approval_notification(self.case)

        self.assertTrue(result)
        email_notification = Notification.objects.get(
            recipient=self.applicant,
            related_case=self.case,
            notification_type="email",
            metadata__event_type="approval",
        )
        self.assertEqual(email_notification.status, "sent")
        mock_logger_exception.assert_not_called()

    @patch("apps.notifications.services.send_mail", return_value=1)
    def test_send_admin_notification_wraps_non_dict_metadata(self, _send_mail):
        result = NotificationService.send_admin_notification(
            self.hr,
            notification_type="processing_error",
            title="Error",
            message="Something failed",
            metadata=["first", {"code": 500}],
        )

        self.assertTrue(result)
        notifications = Notification.objects.filter(
            recipient=self.hr,
            metadata__event_type="processing_error",
        )
        self.assertEqual(notifications.count(), 2)
        for notification in notifications:
            self.assertEqual(notification.metadata.get("value"), ["first", {"code": 500}])

    @patch("apps.notifications.services.send_mail", return_value=1)
    def test_send_admin_notification_sanitizes_non_serializable_metadata(self, _send_mail):
        class NonSerializable:
            def __str__(self):
                return "nons"

        result = NotificationService.send_admin_notification(
            self.hr,
            notification_type="processing_error",
            title="Error",
            message="Something failed",
            metadata={"raw": NonSerializable(), "nested": [NonSerializable()]},
        )

        self.assertTrue(result)
        notifications = Notification.objects.filter(
            recipient=self.hr,
            metadata__event_type="processing_error",
        )
        self.assertEqual(notifications.count(), 2)
        for notification in notifications:
            self.assertEqual(notification.metadata.get("raw"), "nons")
            self.assertEqual(notification.metadata.get("nested"), ["nons"])

    @patch("apps.notifications.services.send_mail", return_value=1)
    def test_send_interview_scheduled_creates_candidate_notifications(
        self,
        _send_mail,
    ):
        session = InterviewSession.objects.create(case=self.case, status="created")
        Notification.objects.filter(
            recipient=self.applicant,
            related_case=self.case,
            metadata__event_type="interview_scheduled",
        ).delete()

        result = NotificationService.send_interview_scheduled(session)

        self.assertTrue(result)
        notifications = Notification.objects.filter(
            recipient=self.applicant,
            related_case=self.case,
            metadata__event_type="interview_scheduled",
        )
        self.assertEqual(notifications.count(), 2)
        self.assertEqual(
            set(notifications.values_list("notification_type", flat=True)),
            {"in_app", "email"},
        )
        in_app_notification = notifications.get(notification_type="in_app")
        self.assertEqual(in_app_notification.related_interview_id, session.id)
        self.assertEqual(
            in_app_notification.metadata.get("interview_url"),
            f"/interview/interrogation/{self.case.case_id}",
        )
        self.assertEqual(
            in_app_notification.metadata.get("case_url"),
            f"/applications/{self.case.case_id}",
        )
        self.assertTrue(in_app_notification.metadata.get("idempotency_key"))

    @patch("apps.notifications.services.send_mail", return_value=1)
    def test_send_interview_scheduled_is_idempotent_for_retries(
        self,
        _send_mail,
    ):
        session = InterviewSession.objects.create(case=self.case, status="created")
        Notification.objects.filter(
            recipient=self.applicant,
            related_case=self.case,
            metadata__event_type="interview_scheduled",
        ).delete()

        first_result = NotificationService.send_interview_scheduled(session)
        second_result = NotificationService.send_interview_scheduled(session)

        self.assertTrue(first_result)
        self.assertTrue(second_result)

        notifications = Notification.objects.filter(
            recipient=self.applicant,
            related_case=self.case,
            metadata__event_type="interview_scheduled",
        )
        self.assertEqual(notifications.count(), 2)
        self.assertEqual(
            set(notifications.values_list("notification_type", flat=True)),
            {"in_app", "email"},
        )

    @override_settings(NOTIFICATIONS_SMS_ENABLED=True)
    @patch("apps.notifications.services.NotificationService._send_sms_notification", return_value=True)
    @patch("apps.notifications.services.send_mail", return_value=1)
    def test_send_interview_scheduled_creates_sms_notification_when_enabled(
        self,
        _send_mail,
        _send_sms,
    ):
        session = InterviewSession.objects.create(case=self.case, status="created")
        Notification.objects.filter(
            recipient=self.applicant,
            related_case=self.case,
            metadata__event_type="interview_scheduled",
        ).delete()

        result = NotificationService.send_interview_scheduled(session)

        self.assertTrue(result)
        notifications = Notification.objects.filter(
            recipient=self.applicant,
            related_case=self.case,
            metadata__event_type="interview_scheduled",
        )
        self.assertEqual(notifications.count(), 3)
        self.assertEqual(
            set(notifications.values_list("notification_type", flat=True)),
            {"in_app", "email", "sms"},
        )
        sms_notification = notifications.get(notification_type="sms")
        self.assertEqual(sms_notification.status, "sent")

    @override_settings(NOTIFICATIONS_SMS_ENABLED=False)
    @patch("apps.notifications.services.NotificationService._send_sms_notification", return_value=True)
    @patch("apps.notifications.services.send_mail", return_value=1)
    def test_send_interview_scheduled_does_not_create_sms_when_disabled(
        self,
        _send_mail,
        _send_sms,
    ):
        session = InterviewSession.objects.create(case=self.case, status="created")
        Notification.objects.filter(
            recipient=self.applicant,
            related_case=self.case,
            metadata__event_type="interview_scheduled",
        ).delete()

        result = NotificationService.send_interview_scheduled(session)

        self.assertTrue(result)
        notifications = Notification.objects.filter(
            recipient=self.applicant,
            related_case=self.case,
            metadata__event_type="interview_scheduled",
        )
        self.assertEqual(notifications.count(), 2)
        self.assertFalse(notifications.filter(notification_type="sms").exists())


class InterviewAlertTaskTests(TestCase):
    def test_send_completion_summary_returns_clean_error_for_missing_session(self):
        result = send_completion_summary.run(session_id=999999)

        self.assertFalse(result["success"])
        self.assertIn("not found", result["error"].lower())

    def test_send_high_deception_alert_returns_clean_error_for_missing_session(self):
        result = send_high_deception_alert.run(session_id=999999, exchange_id=12345)

        self.assertFalse(result["success"])
        self.assertIn("not found", result["error"].lower())
