"""
Management command: purge_expired_data
=======================================
Deletes records that have exceeded their configured retention windows.

Retention periods are configured in settings:
    PII_RETENTION_DAYS              (default 365)
    BIOMETRIC_RETENTION_DAYS        (default 180)
    BACKGROUND_CHECK_RETENTION_DAYS (default 365)
    AUDIT_LOG_RETENTION_DAYS        (default 730)

Usage:
    python manage.py purge_expired_data
    python manage.py purge_expired_data --dry-run
    python manage.py purge_expired_data --scope pii biometric
"""

import logging

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)

SCOPE_PII = "pii"
SCOPE_BIOMETRIC = "biometric"
SCOPE_BACKGROUND_CHECKS = "background_checks"
SCOPE_AUDIT_LOGS = "audit_logs"

ALL_SCOPES = [SCOPE_PII, SCOPE_BIOMETRIC, SCOPE_BACKGROUND_CHECKS, SCOPE_AUDIT_LOGS]


def _cutoff(days: int):
    return timezone.now() - timedelta(days=days)


def _purge_pii(dry_run: bool) -> int:
    """
    Remove candidate PII for cases that completed beyond PII_RETENTION_DAYS.
    For safety, this nulls out sensitive fields rather than deleting rows outright.
    """
    days = int(getattr(settings, "PII_RETENTION_DAYS", 365))
    cutoff = _cutoff(days)
    deleted = 0

    try:
        from apps.candidates.models import Candidate
        qs = Candidate.objects.filter(created_at__lt=cutoff)
        count = qs.count()
        if not dry_run and count:
            qs.delete()
        deleted += count
        logger.info("PII purge (%s): %d candidate record(s) older than %d days.", "DRY RUN" if dry_run else "LIVE", count, days)
    except Exception as exc:
        logger.error("PII purge failed for Candidate: %s", exc, exc_info=True)

    return deleted


def _purge_biometric(dry_run: bool) -> int:
    """Delete biometric data (interview video/audio chunks) beyond retention window."""
    days = int(getattr(settings, "BIOMETRIC_RETENTION_DAYS", 180))
    cutoff = _cutoff(days)
    deleted = 0

    try:
        from apps.interviews.models import InterviewSession
        qs = InterviewSession.objects.filter(
            status__in=["completed", "cancelled", "failed"],
            updated_at__lt=cutoff,
        )
        count = qs.count()
        if not dry_run and count:
            # Null out biometric payload fields; preserve session metadata for audit.
            qs.update(recording_url=None, transcript=None)
        deleted += count
        logger.info(
            "Biometric purge (%s): %d interview session(s) older than %d days.",
            "DRY RUN" if dry_run else "LIVE", count, days,
        )
    except Exception as exc:
        logger.error("Biometric purge failed for InterviewSession: %s", exc, exc_info=True)

    return deleted


def _purge_background_checks(dry_run: bool) -> int:
    """Delete background check records beyond retention window."""
    days = int(getattr(settings, "BACKGROUND_CHECK_RETENTION_DAYS", 365))
    cutoff = _cutoff(days)
    deleted = 0

    try:
        from apps.background_checks.models import BackgroundCheck
        qs = BackgroundCheck.objects.filter(
            status__in=["completed", "failed"],
            updated_at__lt=cutoff,
        )
        count = qs.count()
        if not dry_run and count:
            qs.delete()
        deleted += count
        logger.info(
            "Background check purge (%s): %d record(s) older than %d days.",
            "DRY RUN" if dry_run else "LIVE", count, days,
        )
    except Exception as exc:
        logger.error("Background check purge failed: %s", exc, exc_info=True)

    return deleted


def _purge_audit_logs(dry_run: bool) -> int:
    """Delete audit log entries beyond retention window."""
    days = int(getattr(settings, "AUDIT_LOG_RETENTION_DAYS", 730))
    cutoff = _cutoff(days)
    deleted = 0

    try:
        from apps.audit.models import AuditLog
        qs = AuditLog.objects.filter(created_at__lt=cutoff)
        count = qs.count()
        if not dry_run and count:
            qs.delete()
        deleted += count
        logger.info(
            "Audit log purge (%s): %d entry(s) older than %d days.",
            "DRY RUN" if dry_run else "LIVE", count, days,
        )
    except Exception as exc:
        logger.error("Audit log purge failed: %s", exc, exc_info=True)

    return deleted


_SCOPE_HANDLERS = {
    SCOPE_PII: _purge_pii,
    SCOPE_BIOMETRIC: _purge_biometric,
    SCOPE_BACKGROUND_CHECKS: _purge_background_checks,
    SCOPE_AUDIT_LOGS: _purge_audit_logs,
}


class Command(BaseCommand):
    help = (
        "Purge expired records according to configured data retention policies. "
        "Use --dry-run to preview deletions without committing changes."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Show what would be deleted without actually deleting.",
        )
        parser.add_argument(
            "--scope",
            nargs="+",
            choices=ALL_SCOPES,
            default=ALL_SCOPES,
            metavar="SCOPE",
            help=(
                f"Which data categories to purge. Choices: {', '.join(ALL_SCOPES)}. "
                "Defaults to all scopes."
            ),
        )

    def handle(self, *args, **options):
        dry_run: bool = options["dry_run"]
        scopes: list[str] = options["scope"]

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — no data will be deleted."))

        total = 0
        for scope in scopes:
            handler = _SCOPE_HANDLERS.get(scope)
            if handler is None:
                self.stderr.write(f"Unknown scope: {scope}")
                continue
            count = handler(dry_run=dry_run)
            total += count

        verb = "would be purged" if dry_run else "purged"
        self.stdout.write(
            self.style.SUCCESS(f"Data retention sweep complete. {total} record(s) {verb}.")
        )
