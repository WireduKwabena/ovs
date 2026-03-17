"""Core Celery tasks — system-level background jobs."""

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="apps.core.tasks.run_data_retention_purge", ignore_result=True)
def run_data_retention_purge():
    """
    Nightly task: enforce data retention policies by purging expired records.

    Delegates to the purge_expired_data management command handlers to keep
    the deletion logic in one place and testable outside of Celery.
    """
    from apps.core.management.commands.purge_expired_data import (
        _purge_audit_logs,
        _purge_background_checks,
        _purge_biometric,
        _purge_pii,
    )

    total = 0
    for handler in (_purge_pii, _purge_biometric, _purge_background_checks, _purge_audit_logs):
        try:
            total += handler(dry_run=False)
        except Exception as exc:
            logger.error("Data retention purge handler %s failed: %s", handler.__name__, exc, exc_info=True)

    logger.info("Data retention purge complete. %d record(s) removed.", total)
    return {"purged": total}
