"""Legacy service API compatibility stubs.

This module intentionally avoids hosting a second runtime web framework.
Realtime interview transport is handled by Django Channels consumers in:
`apps.interviews.websocket_handler` and `ai_ml_services.interview.websocket_handler`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from apps.applications.models import VettingCase
from apps.interviews.models import InterviewSession
from apps.interviews.services.flag_generator import InterrogationFlagGenerator


@dataclass(frozen=True)
class StartInterrogationResult:
    success: bool
    session_id: str
    websocket_url: str
    generated_flags: int


def start_interrogation_interview(
    *,
    case: VettingCase,
    websocket_base_url: str = "ws://localhost:8000",
    persist_flags: bool = True,
) -> Dict:
    """
    Create a new interview session and optionally generate interrogation flags.

    This replaces the old FastAPI endpoint function with a Django-native service call.
    """
    if case is None:
        raise ValueError("case is required")

    sync_result = InterrogationFlagGenerator.sync_case_flags(
        case=case,
        persist=persist_flags,
        replace_pending=False,
    )
    session = InterviewSession.objects.create(
        case=case,
        status="created",
        use_dynamic_questions=True,
    )
    websocket_url = f"{websocket_base_url.rstrip('/')}/ws/interview/{session.session_id}/"

    result = StartInterrogationResult(
        success=True,
        session_id=session.session_id,
        websocket_url=websocket_url,
        generated_flags=sync_result["generated_count"],
    )
    return {
        **result.__dict__,
        "flags": sync_result["flags"],
        "created_flag_ids": sync_result["created_flag_ids"],
    }

