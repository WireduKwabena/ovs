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
    pending = BackgroundCheck.objects.filter(status__in=["submitted", "in_progress"]).order_by("submitted_at")[:limit]
    refreshed = 0
    for check in pending:
        try:
            refresh_background_check(check)
            refreshed += 1
        except Exception:
            continue
    return {"refreshed": refreshed, "limit": limit}
