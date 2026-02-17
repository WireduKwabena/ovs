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

from celery import Celery

# Set default Django settings
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

app = Celery("vetting_system")

# Load config from Django settings
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-discover tasks in all installed apps
app.autodiscover_tasks()

# Periodic Tasks Configuration
app.conf.beat_schedule = {}

# Task routing (optional - for multiple workers)
app.conf.task_routes = {
    "apps.invitations.tasks.send_invitation_task": {"queue": "notifications"},
}

# Task priorities
app.conf.task_default_priority = 5
app.conf.task_queue_max_priority = 10

@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Debug task for testing Celery."""
    print(f"Request: {self.request!r}")
