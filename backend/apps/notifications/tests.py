from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from apps.applications.models import VettingCase
from apps.authentication.models import User
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
        self.assertEqual(len(response.data["results"]), 2)
        subjects = {item["subject"] for item in response.data["results"]}
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

    def test_archive_removes_owned_notification(self):
        response = self.client.delete(f"/api/notifications/{self.unread.id}/archive/")

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Notification.objects.filter(id=self.unread.id).exists())

    def test_cannot_archive_other_users_notification(self):
        response = self.client.delete(
            f"/api/notifications/{self.other_users_notification.id}/archive/"
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(Notification.objects.filter(id=self.other_users_notification.id).exists())


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


class InterviewAlertTaskTests(TestCase):
    def test_send_completion_summary_returns_clean_error_for_missing_session(self):
        result = send_completion_summary.run(session_id=999999)

        self.assertFalse(result["success"])
        self.assertIn("not found", result["error"].lower())

    def test_send_high_deception_alert_returns_clean_error_for_missing_session(self):
        result = send_high_deception_alert.run(session_id=999999, exchange_id=12345)

        self.assertFalse(result["success"])
        self.assertIn("not found", result["error"].lower())
