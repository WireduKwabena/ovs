"""
Celery Configuration
====================
Celery app initialization and task discovery.

Academic Note:
--------------
Distributed task queue for:
1. Async AI/ML processing (video analysis, OCR, etc.)
2. Scheduled tasks (cleanup, report generation)
3. Background jobs (email sending)

This prevents blocking the main web server for long-running tasks.
"""

import os

from celery import Celery, signals
from celery.schedules import crontab

# Set default Django settings
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

app = Celery("vetting_system")

# Load config from Django settings
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-discover tasks in all installed apps
app.autodiscover_tasks()

# Periodic Tasks Configuration
app.conf.beat_schedule = {
    "video-calls-reminder-loop": {
        "task": "apps.video_calls.tasks.process_video_meeting_reminders",
        "schedule": crontab(minute="*"),
    },
    "daily-data-retention-purge": {
        # Run at 02:00 UTC every day to purge expired PII, biometric, and audit data.
        "task": "apps.core.tasks.run_data_retention_purge",
        "schedule": crontab(hour=2, minute=0),
    },
}

# Task routing (optional - for multiple workers)
app.conf.task_routes = {
    "apps.invitations.tasks.send_invitation_task": {"queue": "notifications"},
}

# Task priorities
app.conf.task_default_priority = 5
app.conf.task_queue_max_priority = 10

_REQUEST_ID_HEADER = "x-request-id"


@signals.before_task_publish.connect
def propagate_request_id_on_publish(headers=None, **kwargs):
    """Inject the current request ID into outgoing task headers."""
    try:
        from apps.core.middleware import get_current_request_id
        request_id = get_current_request_id()
        if request_id and isinstance(headers, dict):
            headers[_REQUEST_ID_HEADER] = request_id
    except Exception:
        pass


@signals.task_prerun.connect
def restore_request_id_on_worker(task=None, **kwargs):
    """Restore the request ID from task headers into the worker's context."""
    try:
        from apps.core.middleware import set_current_request_id
        request_id = (getattr(task.request, "headers", None) or {}).get(_REQUEST_ID_HEADER, "")
        if request_id:
            set_current_request_id(request_id)
    except Exception:
        pass


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Debug task for testing Celery."""
    print(f"Request: {self.request!r}")
