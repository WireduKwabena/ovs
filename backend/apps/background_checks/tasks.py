from datetime import timedelta

from django.conf import settings
from django.db.models import Q
from django.utils import timezone
from celery import shared_task

from .models import BackgroundCheck
from .services import refresh_background_check


@shared_task(bind=True, max_retries=2)
def refresh_background_check_task(self, check_id):
    try:
        check = BackgroundCheck.objects.get(id=check_id)
    except BackgroundCheck.DoesNotExist:
        return {"status": "missing", "check_id": check_id}

    try:
        refreshed = refresh_background_check(check)
        return {"status": refreshed.status, "check_id": str(refreshed.id)}
    except Exception as exc:
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))
        return {"status": "failed", "check_id": check_id, "error": str(exc)}


@shared_task
def sweep_background_checks_task(limit=50):
    now = timezone.now()
    max_age_hours = max(1, int(getattr(settings, "BACKGROUND_CHECK_SWEEP_MAX_AGE_HOURS", 48)))
    min_poll_interval_minutes = max(1, int(getattr(settings, "BACKGROUND_CHECK_SWEEP_MIN_POLL_INTERVAL_MINUTES", 15)))

    oldest_allowed = now - timedelta(hours=max_age_hours)
    poll_cutoff = now - timedelta(minutes=min_poll_interval_minutes)

    pending = (
        BackgroundCheck.objects.filter(status__in=["submitted", "in_progress"]) 
        .filter(submitted_at__gte=oldest_allowed)
        .filter(Q(last_polled_at__isnull=True) | Q(last_polled_at__lte=poll_cutoff))
        .order_by("last_polled_at", "submitted_at")[:limit]
    )
    refreshed = 0
    for check in pending:
        try:
            refresh_background_check(check)
            refreshed += 1
        except Exception:
            continue
    return {
        "refreshed": refreshed,
        "limit": limit,
        "max_age_hours": max_age_hours,
        "min_poll_interval_minutes": min_poll_interval_minutes,
    }
