"""
Management command: seed_demo_notifications

Creates realistic in-app notifications for demo accounts so the
Notifications page is populated during a walkthrough.

Usage:
    python manage.py seed_demo_notifications
    python manage.py seed_demo_notifications --email admin@example.com
    python manage.py seed_demo_notifications --clear
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from apps.users.models import User
from apps.notifications.models import Notification


DEMO_NOTIFICATIONS = [
    {
        "subject": "Vetting case assigned to you",
        "message": (
            "A new vetting case has been assigned to you for review. "
            "Please open the case and begin the initial document verification."
        ),
        "notification_type": "in_app",
        "status": "sent",
        "priority": "high",
        "metadata": {
            "event_type": "case_assigned",
            "case_id": "DEMO-CASE-001",
        },
    },
    {
        "subject": "AI analysis complete",
        "message": (
            "The AI vetting analysis for case DEMO-CASE-001 is complete. "
            "Recommendation: manual review required. Confidence score: 72%."
        ),
        "notification_type": "in_app",
        "status": "sent",
        "priority": "normal",
        "metadata": {
            "event_type": "ai_analysis_complete",
            "case_id": "DEMO-CASE-001",
            "recommendation": "recommend_manual_review",
            "score": "72",
        },
    },
    {
        "subject": "Committee review scheduled",
        "message": (
            "A committee review session has been scheduled for nominee "
            "John Addo on Thursday at 10:00 AM. Please confirm your attendance."
        ),
        "notification_type": "in_app",
        "status": "read",
        "priority": "normal",
        "metadata": {
            "event_type": "committee_review_scheduled",
        },
    },
    {
        "subject": "Document verification failed",
        "message": (
            "The national ID document submitted for case DEMO-CASE-002 "
            "failed authenticity verification. A fraud flag has been raised for manual review."
        ),
        "notification_type": "in_app",
        "status": "sent",
        "priority": "urgent",
        "metadata": {
            "event_type": "document_verification_failed",
            "case_id": "DEMO-CASE-002",
            "document_type": "national_id",
            "document_status": "failed",
        },
    },
    {
        "subject": "Appointment approved",
        "message": (
            "The appointment for Justice Kwame Asante to the position of "
            "Director of Public Prosecutions has been approved and signed off."
        ),
        "notification_type": "in_app",
        "status": "read",
        "priority": "normal",
        "metadata": {
            "event_type": "appointment_approved",
            "new_status": "appointed",
        },
    },
    {
        "subject": "New organization registered",
        "message": (
            "A new organization 'Ghana Audit Service' has registered on the platform "
            "and is pending onboarding review."
        ),
        "notification_type": "in_app",
        "status": "sent",
        "priority": "low",
        "metadata": {
            "event_type": "org_registered",
        },
    },
    {
        "subject": "Interview session ready",
        "message": (
            "The AI interview session for candidate Abena Mensah is ready to begin. "
            "Click below to join the vetting interview."
        ),
        "notification_type": "in_app",
        "status": "sent",
        "priority": "high",
        "metadata": {
            "event_type": "interview_ready",
            "case_id": "DEMO-CASE-003",
        },
    },
    {
        "subject": "Gazette published",
        "message": (
            "The appointment gazette for Q1 2026 has been published. "
            "3 new appointments are now publicly visible on the transparency portal."
        ),
        "notification_type": "in_app",
        "status": "read",
        "priority": "normal",
        "metadata": {
            "event_type": "gazette_published",
        },
    },
]


class Command(BaseCommand):
    help = "Seed demo in-app notifications for demo accounts"

    def add_arguments(self, parser):
        parser.add_argument(
            "--email",
            type=str,
            default=None,
            help="Target a specific user by email (default: all staff users)",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete all existing demo notifications before seeding",
        )

    def handle(self, *args, **options):
        email = options["email"]
        clear = options["clear"]

        if email:
            try:
                users = [User.objects.get(email=email)]
            except User.DoesNotExist:
                raise CommandError(f"No user found with email: {email}")
        else:
            users = list(
                User.objects.filter(is_active=True, is_staff=False).exclude(
                    email__endswith="@example.com"
                )[:20]
            )
            if not users:
                users = list(User.objects.filter(is_active=True)[:5])

        if not users:
            self.stdout.write(self.style.WARNING("No users found. Skipping."))
            return

        if clear:
            deleted, _ = Notification.objects.filter(
                metadata__has_key="case_id"
            ).filter(
                subject__in=[n["subject"] for n in DEMO_NOTIFICATIONS]
            ).delete()
            self.stdout.write(self.style.WARNING(f"Cleared {deleted} existing demo notifications."))

        created_count = 0
        now = timezone.now()

        for user in users:
            for i, demo in enumerate(DEMO_NOTIFICATIONS):
                # Stagger timestamps so the list looks natural
                offset_minutes = i * 47 + 3
                created_at = now - timezone.timedelta(minutes=offset_minutes)

                notif = Notification(
                    recipient=user,
                    subject=demo["subject"],
                    message=demo["message"],
                    notification_type=demo["notification_type"],
                    status=demo["status"],
                    priority=demo["priority"],
                    metadata=demo["metadata"],
                    is_archived=False,
                    sent_at=created_at if demo["status"] in ("sent", "read") else None,
                    read_at=created_at + timezone.timedelta(minutes=5) if demo["status"] == "read" else None,
                )
                notif.save()
                # Override auto_now_add so timestamps look staggered
                Notification.objects.filter(pk=notif.pk).update(created_at=created_at)
                created_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Created {created_count} demo notifications for {len(users)} user(s)."
            )
        )
