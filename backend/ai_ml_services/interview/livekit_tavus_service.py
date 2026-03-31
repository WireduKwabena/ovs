"""LiveKit + Tavus streaming avatar integration for interview sessions.

Replaces the legacy HeyGen streaming service. Architecture:
  - LiveKit  — WebRTC room for real-time video/audio transport
  - Tavus    — AI video avatar persona that joins the LiveKit room
  - Anthropic — Claude generates interview questions (see anthropic_interview_engine.py)

The service manages per-session state (room name, Tavus conversation id) and
provides async helpers used by the WebSocket handler.
"""

from __future__ import annotations

import logging
from typing import Optional, Protocol

from django.conf import settings

logger = logging.getLogger(__name__)


class WebSocketProtocol(Protocol):
    async def send_bytes(self, data: bytes) -> None: ...
    async def send_json(self, data: dict) -> None: ...


class LiveKitTavusService:
    """Per-session service that owns the LiveKit room and Tavus conversation."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.room_name: str = f"interview-{session_id}"
        self.conversation_id: Optional[str] = None
        self.conversation_url: Optional[str] = None
        self._livekit_url: str = str(getattr(settings, "LIVEKIT_URL", "")).strip()

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    async def create_session(
        self,
        *,
        case_title: str = "",
        flags_summary: str = "",
        callback_url: str = "",
    ) -> dict:
        """
        Provision a LiveKit room token + Tavus conversation.

        This is the async counterpart of `build_interview_session_payload` in
        livekit_sdk.py — called from the WebSocket handler when server-driven
        initialisation is needed rather than the REST endpoint.
        """
        from apps.interviews.services.livekit_sdk import (
            _create_livekit_token,
            create_tavus_conversation,
        )

        livekit_token = _create_livekit_token(
            room_name=self.room_name,
            participant_identity=f"candidate-{self.session_id}",
            participant_name="Candidate",
        )

        context_parts = [
            "You are a professional government vetting interviewer conducting a formal assessment.",
            "Maintain a serious, respectful tone. Ask one question at a time.",
        ]
        if case_title:
            context_parts.append(f"This interview is for the position: {case_title}.")
        if flags_summary:
            context_parts.append(f"Key areas requiring clarification: {flags_summary}.")

        greeting = (
            "Good day. I am your interviewer for today's vetting session. "
            "When you are ready, please introduce yourself."
        )

        tavus_data = create_tavus_conversation(
            session_id=self.session_id,
            conversational_context=" ".join(context_parts),
            custom_greeting=greeting,
            callback_url=callback_url,
        )
        self.conversation_id = tavus_data.get("conversation_id", "")
        self.conversation_url = tavus_data.get("conversation_url", "")

        logger.info(
            "LiveKit+Tavus session ready — room=%s tavus=%s",
            self.room_name,
            self.conversation_id,
        )
        return {
            "livekit_url": self._livekit_url,
            "livekit_token": livekit_token,
            "room_name": self.room_name,
            "conversation_id": self.conversation_id,
            "conversation_url": self.conversation_url,
        }

    async def close_session(self) -> None:
        """End the Tavus conversation and release resources."""
        if not self.conversation_id:
            return
        try:
            from apps.interviews.services.livekit_sdk import end_tavus_conversation
            end_tavus_conversation(self.conversation_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Error closing Tavus conversation %s: %s", self.conversation_id, exc
            )
        finally:
            logger.info("Tavus session closed: %s", self.conversation_id)
            self.conversation_id = None
            self.conversation_url = None

    # ------------------------------------------------------------------
    # Avatar speech delivery
    # ------------------------------------------------------------------

    async def deliver_interviewer_text(
        self,
        *,
        text: str,
        websocket: WebSocketProtocol,
    ) -> None:
        """
        Notify the frontend that the avatar is speaking `text`.

        In the LiveKit + Tavus model, Tavus handles the actual avatar video/audio
        autonomously in the room. We send a WebSocket signal so the frontend can
        display the transcript and manage UI state.
        """
        await websocket.send_json(
            {
                "type": "avatar_speaking",
                "text": text,
                "conversation_id": self.conversation_id,
                "transport": "tavus_livekit",
            }
        )
