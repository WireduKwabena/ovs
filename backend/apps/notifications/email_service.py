"""Backward-compatible import wrapper for interview alert logic.

Use `apps.notifications.interview_alerts` as the canonical module.
"""

from apps.notifications.interview_alerts import (  # noqa: F401
    InterviewAlertService,
    calculate_avg_deception,
    get_hr_manager_emails,
    send_behavioral_alert,
    send_completion_summary,
    send_critical_flags_alert,
    send_high_deception_alert,
    send_poor_response_alert,
)

__all__ = [
    "InterviewAlertService",
    "send_high_deception_alert",
    "send_critical_flags_alert",
    "send_poor_response_alert",
    "send_behavioral_alert",
    "send_completion_summary",
    "get_hr_manager_emails",
    "calculate_avg_deception",
]
