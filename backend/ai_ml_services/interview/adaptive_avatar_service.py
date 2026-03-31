"""Adaptive avatar helpers for interview flows using LiveKit + Tavus.

Replaces the legacy EmotionalAvatarService (HeyGen) with Tavus persona
configuration. Instead of manipulating voice emotion via an API call, the
interviewer's tone is shaped by:
  1. The Tavus persona's base personality (configured at conversation creation).
  2. The conversational context injected into the Anthropic system prompt
     (handled by AnthropicInterviewEngine).

This module retains the same public interface so existing call-sites continue
to work without modification.
"""

from __future__ import annotations

import logging
from typing import Any

from .livekit_tavus_service import LiveKitTavusService, WebSocketProtocol

logger = logging.getLogger(__name__)


def _interview_tone_from_context(
    *,
    deception_score: float,
    inconsistencies_count: int,
    question_intent: str,
    previous_responses_quality: list[float] | None = None,
) -> str:
    """
    Map interview context to a tone descriptor passed to the Anthropic system
    prompt.  Returns 'formal_firm', 'formal_neutral', or 'formal_encouraging'.
    """
    previous_responses_quality = previous_responses_quality or []

    if deception_score > 70 or inconsistencies_count > 3:
        return "formal_firm"
    if deception_score > 30 or inconsistencies_count > 1:
        return "formal_neutral"
    if question_intent in {"clarify_gap", "verify_information", "resolve_flag"}:
        return "formal_neutral"
    if previous_responses_quality and all(s > 75 for s in previous_responses_quality[-3:]):
        return "formal_encouraging"
    return "formal_neutral"


def _speech_rate_hint(deception_score: float) -> str:
    """Return a natural-language pacing hint injected into the Claude prompt."""
    if deception_score > 70:
        return "Speak slowly and deliberately, allowing pauses after key questions."
    if deception_score > 30:
        return "Maintain a measured, unhurried pace."
    return "Speak at a natural, conversational pace."


class AdaptiveAvatarService(LiveKitTavusService):
    """
    LiveKitTavusService subclass that adapts the interviewer's tone based on
    real-time interview context.

    The 'emotion' adjustment from the old HeyGen implementation is replaced by
    enriching the Anthropic system prompt with contextual tone instructions.
    The Tavus avatar then naturally reflects the tone through its response.
    """

    def determine_tone_from_context(
        self,
        *,
        deception_score: float,
        inconsistencies_count: int,
        question_intent: str,
        previous_responses_quality: list[float] | None = None,
    ) -> str:
        return _interview_tone_from_context(
            deception_score=deception_score,
            inconsistencies_count=inconsistencies_count,
            question_intent=question_intent,
            previous_responses_quality=previous_responses_quality,
        )

    async def deliver_adaptive_response(
        self,
        *,
        text: str,
        websocket: WebSocketProtocol,
        interview_context: dict[str, Any] | None = None,
    ) -> None:
        context = interview_context or {}
        deception_score = float(context.get("deception_score", 0))
        inconsistencies_count = int(context.get("inconsistencies_count", 0))
        question_intent = str(context.get("question_intent", "general"))
        previous_responses = context.get("previous_responses") or []

        tone = self.determine_tone_from_context(
            deception_score=deception_score,
            inconsistencies_count=inconsistencies_count,
            question_intent=question_intent,
            previous_responses_quality=previous_responses,
        )
        pacing = _speech_rate_hint(deception_score)

        # Deliver the text to the frontend (Tavus handles actual TTS in the room)
        await websocket.send_json(
            {
                "type": "avatar_speaking",
                "text": text,
                "tone": tone,
                "pacing_hint": pacing,
                "conversation_id": self.conversation_id,
                "transport": "tavus_livekit",
            }
        )

        logger.info(
            "Adaptive delivery — tone=%s deception=%.1f inconsistencies=%d",
            tone,
            deception_score,
            inconsistencies_count,
        )


__all__ = ["AdaptiveAvatarService"]
