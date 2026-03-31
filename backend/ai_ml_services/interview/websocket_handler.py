"""WebSocket interview flow utilities for the LiveKit + Tavus + Anthropic stack.

Replaces the former HeyGen-based handler. Key differences:
  - Avatar video/audio is handled by Tavus inside the LiveKit room autonomously.
  - Question generation uses AnthropicInterviewEngine (Claude) instead of
    hardcoded heuristics.
  - ICE candidate forwarding is no longer needed — LiveKit manages WebRTC.
  - `deliver_avatar_output` sends a JSON signal; Tavus speaks the text in-room.
"""

from __future__ import annotations

import logging
from typing import Dict, Optional, Protocol

import httpx

from django.conf import settings

from .livekit_tavus_service import LiveKitTavusService
from .anthropic_interview_engine import AnthropicInterviewEngine
from .nonverbal_analyzer import NonVerbalAnalyzer

logger = logging.getLogger(__name__)


class WebSocketProtocol(Protocol):
    async def accept(self) -> None: ...
    async def send_json(self, data: dict) -> None: ...
    async def receive(self) -> dict: ...
    async def close(self) -> None: ...


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _django_api_url() -> str:
    return getattr(settings, "DJANGO_API_URL", "http://localhost:8000")


def _session_api_url(session_id: str, suffix: str = "") -> str:
    base = _django_api_url().rstrip("/")
    suffix = suffix.strip("/")
    url = f"{base}/api/interviews/sessions/{session_id}/"
    return f"{url}{suffix}/" if suffix else url


def _service_headers() -> Dict[str, str]:
    token = getattr(settings, "SERVICE_TOKEN", "")
    if not token:
        return {}
    return {"Authorization": f"Bearer {token}", "X-Service-Token": token}


async def _safe_send_json(websocket: WebSocketProtocol, payload: dict) -> None:
    try:
        await websocket.send_json(payload)
    except (RuntimeError, ConnectionError, OSError, ValueError, TypeError) as exc:
        logger.warning("Failed to send websocket payload: %s", exc)


async def _deliver_avatar_output(
    *,
    service: LiveKitTavusService,
    websocket: WebSocketProtocol,
    text: str,
) -> None:
    """Signal the frontend that the avatar is speaking text.

    Tavus handles actual TTS/video inside the LiveKit room. This message lets
    the frontend display a transcript overlay and update UI state.
    """
    await service.deliver_interviewer_text(text=text, websocket=websocket)


# ---------------------------------------------------------------------------
# Connection manager
# ---------------------------------------------------------------------------

class InterviewConnectionManager:
    """Track active interview WebSocket connections and per-session services."""

    def __init__(self):
        self.active_connections: Dict[str, WebSocketProtocol] = {}
        self.livekit_sessions: Dict[str, LiveKitTavusService] = {}
        self.interview_engines: Dict[str, AnthropicInterviewEngine] = {}
        self.analyzers: Dict[str, NonVerbalAnalyzer] = {}

    async def connect(self, session_id: str, websocket: WebSocketProtocol) -> None:
        await websocket.accept()
        self.active_connections[session_id] = websocket
        self.livekit_sessions[session_id] = LiveKitTavusService(session_id)
        self.analyzers[session_id] = NonVerbalAnalyzer()
        logger.info("Client connected: %s", session_id)

    def disconnect(self, session_id: str) -> None:
        self.active_connections.pop(session_id, None)
        self.livekit_sessions.pop(session_id, None)
        self.interview_engines.pop(session_id, None)
        self.analyzers.pop(session_id, None)
        logger.info("Client disconnected: %s", session_id)

    async def send_message(self, session_id: str, message: dict) -> None:
        ws = self.active_connections.get(session_id)
        if ws:
            try:
                await ws.send_json(message)
            except (RuntimeError, ConnectionError, OSError, ValueError, TypeError) as exc:
                logger.error("Error sending to %s: %s", session_id, exc)

    def get_livekit_service(self, session_id: str) -> Optional[LiveKitTavusService]:
        return self.livekit_sessions.get(session_id)

    def get_interview_engine(self, session_id: str) -> Optional[AnthropicInterviewEngine]:
        return self.interview_engines.get(session_id)

    def set_interview_engine(self, session_id: str, engine: AnthropicInterviewEngine) -> None:
        self.interview_engines[session_id] = engine

    def get_analyzer(self, session_id: str) -> Optional[NonVerbalAnalyzer]:
        return self.analyzers.get(session_id)


manager = InterviewConnectionManager()


# ---------------------------------------------------------------------------
# Django API helpers
# ---------------------------------------------------------------------------

async def fetch_session_data(session_id: str) -> dict:
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(_session_api_url(session_id), headers=_service_headers())
            if response.status_code == 200:
                return response.json()
            logger.error("Failed to fetch session data: %s", response.status_code)
            return None
    except (httpx.RequestError, httpx.HTTPError, ValueError, TypeError) as exc:
        logger.error("Error fetching session data: %s", exc)
        return None


async def save_exchange_to_django(session_id: str, exchange_data: dict) -> dict:
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                _session_api_url(session_id, "save-exchange"),
                json=exchange_data,
                headers=_service_headers(),
            )
            if response.status_code == 200:
                return response.json()
            logger.error("Failed to save exchange: %s", response.status_code)
            return None
    except (httpx.RequestError, httpx.HTTPError, ValueError, TypeError) as exc:
        logger.error("Error saving exchange: %s", exc)
        return None


async def update_exchange_in_django(session_id: str, update_data: dict) -> dict:
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                _session_api_url(session_id, "update-exchange"),
                json=update_data,
                headers=_service_headers(),
            )
            if response.status_code == 200:
                return response.json()
            logger.error("Failed to update exchange: %s", response.status_code)
            return None
    except (httpx.RequestError, httpx.HTTPError, ValueError, TypeError) as exc:
        logger.error("Error updating exchange: %s", exc)
        return None


async def complete_interview_in_django(session_id: str) -> bool:
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                _session_api_url(session_id, "complete"), headers=_service_headers()
            )
            return response.status_code == 200
    except (httpx.RequestError, httpx.HTTPError, ValueError, TypeError) as exc:
        logger.error("Error completing interview: %s", exc)
        return False


# ---------------------------------------------------------------------------
# Message handlers
# ---------------------------------------------------------------------------

async def handle_applicant_response(
    message: dict,
    session_id: str,
    websocket: WebSocketProtocol,
) -> None:
    service = manager.get_livekit_service(session_id)
    engine = manager.get_interview_engine(session_id)
    analyzer = manager.get_analyzer(session_id)

    if not all([service, engine, analyzer]):
        logger.error("Services not initialised for session %s", session_id)
        await _safe_send_json(websocket, {"type": "error", "message": "Session services not initialised"})
        return

    try:
        transcript = message.get("transcript", "")
        video_path = message.get("video_path", "")
        audio_data = message.get("audio_data")

        # Transcribe audio if transcript not provided
        if not transcript and audio_data:
            try:
                from ai_ml_services.video.transcription import transcribe_audio
                transcript = await transcribe_audio(audio_data)
            except (ImportError, RuntimeError, ValueError, TypeError):
                transcript = ""
                logger.warning("Audio transcription unavailable; continuing without transcript.")

        # Non-verbal analysis
        nonverbal_data = {}
        if video_path:
            nonverbal_data = await analyzer.analyze_video_async(video_path)

        # Persist response
        update_data = {
            "transcript": transcript,
            "video_url": video_path,
            "sentiment": nonverbal_data.get("average_emotion", "neutral"),
            "confidence_level": nonverbal_data.get("confidence_score", 50),
            "nonverbal_data": nonverbal_data,
        }
        exchange_result = await update_exchange_in_django(session_id, update_data)
        if not exchange_result:
            await _safe_send_json(websocket, {"type": "error", "message": "Failed to save response"})
            return

        # Flag resolution check
        current_flag_id = exchange_result.get("current_flag_id")
        if current_flag_id:
            resolution = engine.analyze_response_for_flag_resolution(
                transcript=transcript,
                flag_id=current_flag_id,
                nonverbal_data=nonverbal_data,
            )
            if resolution.get("resolved"):
                await _safe_send_json(websocket, {"type": "flag_resolution", "data": resolution})

        # Update engine history
        engine.update_conversation_history(
            question=exchange_result.get("question_text", ""),
            answer=transcript,
            nonverbal=nonverbal_data,
        )

        # Generate next question
        next_question = engine.generate_next_question()

        if next_question is None:
            # Interview complete
            farewell = (
                "Thank you for your responses. The interview is now complete. "
                "Your answers will be reviewed by our team."
            )
            await _deliver_avatar_output(service=service, websocket=websocket, text=farewell)
            await _safe_send_json(
                websocket,
                {"type": "interview_complete", "total_questions": exchange_result.get("question_number", 0)},
            )
            await complete_interview_in_django(session_id)
            return

        # Persist next question
        question_data = {
            "sequence_number": exchange_result.get("question_number", 0) + 1,
            "question_text": next_question["question"],
            "question_intent": next_question.get("intent", ""),
        }
        await save_exchange_to_django(session_id, question_data)

        # Avatar delivers next question
        await _deliver_avatar_output(service=service, websocket=websocket, text=next_question["question"])
        await _safe_send_json(
            websocket,
            {
                "type": "next_question",
                "question": next_question["question"],
                "question_number": question_data["sequence_number"],
                "intent": next_question.get("intent", ""),
                "reasoning": next_question.get("reasoning", ""),
                "target_flag_id": next_question.get("target_flag_id"),
            },
        )

    except (RuntimeError, ValueError, TypeError, KeyError, httpx.HTTPError) as exc:
        logger.error("Error handling applicant response: %s", exc, exc_info=True)
        await _safe_send_json(websocket, {"type": "error", "message": f"Error processing response: {exc}"})
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected error handling applicant response: %s", exc)
        await _safe_send_json(websocket, {"type": "error", "message": "Unexpected error processing response."})


async def handle_video_chunk(message: dict, session_id: str) -> None:
    try:
        chunk_index = message.get("index", 0)
        chunk_size = message.get("chunk_size")
        logger.debug(
            "Received video chunk %s for session %s (size=%s)", chunk_index, session_id, chunk_size
        )
    except (AttributeError, TypeError, ValueError) as exc:
        logger.error("Error handling video chunk: %s", exc)


async def initialize_interview_session(session_id: str, websocket: WebSocketProtocol) -> bool:
    try:
        service = manager.get_livekit_service(session_id)

        # Provision LiveKit + Tavus session
        session_info = await service.create_session()

        await _safe_send_json(
            websocket,
            {
                "type": "session_initialized",
                "session_id": session_id,
                "livekit_url": session_info.get("livekit_url", ""),
                "livekit_token": session_info.get("livekit_token", ""),
                "room_name": session_info.get("room_name", ""),
                "conversation_url": session_info.get("conversation_url", ""),
                "conversation_id": session_info.get("conversation_id", ""),
                "avatar_transport": "tavus_livekit",
            },
        )

        # Load session data and initialise the Anthropic engine
        session_data = await fetch_session_data(session_id)
        if not session_data:
            raise RuntimeError("Failed to fetch session data from Django")

        engine = AnthropicInterviewEngine(session_data)
        manager.set_interview_engine(session_id, engine)

        # Generate and deliver first question
        first_question = engine.generate_next_question()
        if not first_question:
            raise RuntimeError("Failed to generate first question")

        question_data = {
            "sequence_number": 1,
            "question_text": first_question["question"],
            "question_intent": first_question.get("intent", ""),
        }
        await save_exchange_to_django(session_id, question_data)
        await _deliver_avatar_output(service=service, websocket=websocket, text=first_question["question"])
        await _safe_send_json(
            websocket,
            {
                "type": "question_asked",
                "question": first_question["question"],
                "question_number": 1,
                "intent": first_question.get("intent", ""),
            },
        )

        logger.info("Interview session %s initialised successfully", session_id)
        return True

    except (RuntimeError, ValueError, TypeError, KeyError, httpx.HTTPError) as exc:
        logger.error("Error initialising interview session: %s", exc, exc_info=True)
        await _safe_send_json(websocket, {"type": "error", "message": f"Failed to initialise interview: {exc}"})
        return False
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected error initialising interview session: %s", exc)
        await _safe_send_json(websocket, {"type": "error", "message": "Failed to initialise interview due to unexpected error."})
        return False


async def handle_websocket_message(
    message_data: dict,
    session_id: str,
    websocket: WebSocketProtocol,
) -> None:
    message_type = message_data.get("type")
    logger.debug("Handling message type: %s for session %s", message_type, session_id)

    if message_type == "response_complete":
        await handle_applicant_response(message_data, session_id, websocket)
    elif message_type == "video_chunk":
        await handle_video_chunk(message_data, session_id)
    elif message_type == "ping":
        await _safe_send_json(websocket, {"type": "pong"})
    else:
        logger.warning("Unknown message type: %s", message_type)
        await _safe_send_json(
            websocket, {"type": "error", "message": f"Unknown message type: {message_type}"}
        )


__all__ = [
    "manager",
    "InterviewConnectionManager",
    "handle_applicant_response",
    "initialize_interview_session",
    "handle_websocket_message",
]
