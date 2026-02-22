"""Adaptive HeyGen avatar helpers for interview flows."""

from __future__ import annotations

import logging
from typing import Any

from .heygen_service import HeyGenAvatarService

logger = logging.getLogger(__name__)


class EmotionalAvatarService(HeyGenAvatarService):
    """HeyGen wrapper that adapts tone based on interview risk context."""

    def determine_emotion_from_context(
        self,
        *,
        deception_score: float,
        inconsistencies_count: int,
        question_intent: str,
        previous_responses_quality: list[float] | None = None,
    ) -> str:
        previous_responses_quality = previous_responses_quality or []

        if deception_score > 70 or inconsistencies_count > 3:
            return "Serious"
        if deception_score > 50:
            return "Serious"
        if deception_score > 30 or inconsistencies_count > 1:
            return "Serious"
        if question_intent in {"clarify_gap", "verify_information", "resolve_flag"}:
            return "Serious"
        if previous_responses_quality and all(score > 75 for score in previous_responses_quality[-3:]):
            return "Friendly"
        return "Serious"

    @staticmethod
    def _calculate_speech_rate(deception_score: float) -> float:
        if deception_score > 70:
            return 0.85
        if deception_score > 50:
            return 0.90
        if deception_score > 30:
            return 0.95
        return 1.0

    async def stream_adaptive_response(
        self,
        *,
        text: str,
        websocket: Any,
        interview_context: dict[str, Any] | None = None,
    ) -> None:
        context = interview_context or {}
        deception_score = float(context.get("deception_score", 0))
        inconsistencies_count = int(context.get("inconsistencies_count", 0))
        question_intent = str(context.get("question_intent", "general"))
        previous_responses = context.get("previous_responses") or []

        emotion = self.determine_emotion_from_context(
            deception_score=deception_score,
            inconsistencies_count=inconsistencies_count,
            question_intent=question_intent,
            previous_responses_quality=previous_responses,
        )
        rate = self._calculate_speech_rate(deception_score)

        await self.stream_avatar_speech(
            text=text,
            websocket=websocket,
            emotion=emotion,
            rate=rate,
        )
        logger.info(
            "Avatar emotion=%s rate=%.2f deception=%.2f inconsistencies=%d",
            emotion,
            rate,
            deception_score,
            inconsistencies_count,
        )


__all__ = ["EmotionalAvatarService"]
