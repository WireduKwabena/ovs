"""Lightweight analytics logging helpers."""

from __future__ import annotations

import logging
from typing import Dict

from apps.interviews.models import InterviewSession

logger = logging.getLogger(__name__)


def build_interview_metrics(session: InterviewSession) -> Dict:
    """Build a compact metrics payload for one interview session."""
    return {
        "session_id": session.session_id,
        "status": session.status,
        "duration_seconds": session.duration_seconds,
        "questions_asked": session.total_questions_asked,
        "overall_score": session.overall_score,
        "confidence_score": session.confidence_score,
        "flags_resolved": session.flags_resolved_count,
        "flags_unresolved": session.flags_unresolved_count,
    }


def log_interview_metrics(session: InterviewSession) -> Dict:
    """Emit structured interview metrics to app logs."""
    metrics = build_interview_metrics(session)
    logger.info("Interview metrics: %s", metrics)
    return metrics

