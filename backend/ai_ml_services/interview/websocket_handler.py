"""Websocket interview flow utilities shared by Django-side realtime handlers."""

import asyncio
import json
import logging
from typing import Any, Dict, Optional, Protocol
from datetime import datetime
import httpx

from django.conf import settings

from .heygen_service import HeyGenAvatarService
from .interview_engine import EnhancedInterviewEngine
from .nonverbal_analyzer import NonVerbalAnalyzer

logger = logging.getLogger(__name__)


class WebSocketProtocol(Protocol):
    """Framework-agnostic websocket protocol."""

    async def accept(self) -> None:
        ...

    async def send_json(self, data: dict) -> None:
        ...

    async def receive(self) -> dict:
        ...

    async def close(self) -> None:
        ...


def _django_api_url() -> str:
    return getattr(settings, "DJANGO_API_URL", "http://localhost:8000")


def _session_api_url(session_id: str, suffix: str = "") -> str:
    base = _django_api_url().rstrip("/")
    suffix = suffix.strip("/")
    session_url = f"{base}/api/interviews/sessions/{session_id}/"
    return f"{session_url}{suffix}/" if suffix else session_url


def _service_headers() -> Dict[str, str]:
    token = getattr(settings, "SERVICE_TOKEN", "")
    if not token:
        return {}
    return {
        "Authorization": f"Bearer {token}",
        "X-Service-Token": token,
    }


class InterviewConnectionManager:
    """
    Manage active interview WebSocket connections
    Handles multiple concurrent interviews
    """

    def __init__(self):
        self.active_connections: Dict[str, WebSocketProtocol] = {}
        self.heygen_services: Dict[str, HeyGenAvatarService] = {}
        self.interview_engines: Dict[str, EnhancedInterviewEngine] = {}
        self.analyzers: Dict[str, NonVerbalAnalyzer] = {}

    async def connect(self, session_id: str, websocket: WebSocketProtocol):
        """Accept WebSocket connection and initialize services"""
        await websocket.accept()
        self.active_connections[session_id] = websocket

        # Initialize HeyGen service for this session
        self.heygen_services[session_id] = HeyGenAvatarService()

        # Initialize non-verbal analyzer
        self.analyzers[session_id] = NonVerbalAnalyzer()

        logger.info(f"Client connected: {session_id}")

    def disconnect(self, session_id: str):
        """Remove connection and cleanup resources"""
        if session_id in self.active_connections:
            del self.active_connections[session_id]

        if session_id in self.heygen_services:
            del self.heygen_services[session_id]

        if session_id in self.interview_engines:
            del self.interview_engines[session_id]

        if session_id in self.analyzers:
            del self.analyzers[session_id]

        logger.info(f"Client disconnected: {session_id}")

    async def send_message(self, session_id: str, message: dict):
        """Send JSON message to specific client"""
        if session_id in self.active_connections:
            try:
                await self.active_connections[session_id].send_json(message)
            except Exception as e:
                logger.error(f"Error sending message to {session_id}: {e}")

    def get_heygen_service(self, session_id: str) -> Optional[HeyGenAvatarService]:
        """Get HeyGen service for specific session"""
        return self.heygen_services.get(session_id)

    def get_interview_engine(self, session_id: str) -> Optional[EnhancedInterviewEngine]:
        """Get interview engine for specific session"""
        return self.interview_engines.get(session_id)

    def set_interview_engine(self, session_id: str, engine: EnhancedInterviewEngine):
        """Set interview engine for specific session"""
        self.interview_engines[session_id] = engine

    def get_analyzer(self, session_id: str) -> Optional[NonVerbalAnalyzer]:
        """Get non-verbal analyzer for specific session"""
        return self.analyzers.get(session_id)


# Global connection manager
manager = InterviewConnectionManager()


async def fetch_session_data(session_id: str) -> dict:
    """
    Fetch interview session data from Django API
    """
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                _session_api_url(session_id),
                headers=_service_headers(),
            )

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to fetch session data: {response.status_code}")
                return None

    except Exception as e:
        logger.error(f"Error fetching session data: {e}")
        return None


async def save_exchange_to_django(session_id: str, exchange_data: dict) -> dict:
    """
    Save interview exchange to Django database
    """
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                _session_api_url(session_id, "save-exchange"),
                json=exchange_data,
                headers=_service_headers(),
            )

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to save exchange: {response.status_code}")
                return None

    except Exception as e:
        logger.error(f"Error saving exchange: {e}")
        return None


async def update_exchange_in_django(session_id: str, update_data: dict) -> dict:
    """
    Update interview exchange in Django database
    """
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                _session_api_url(session_id, "update-exchange"),
                json=update_data,
                headers=_service_headers(),
            )

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to update exchange: {response.status_code}")
                return None

    except Exception as e:
        logger.error(f"Error updating exchange: {e}")
        return None


async def complete_interview_in_django(session_id: str) -> bool:
    """
    Mark interview as complete in Django
    """
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                _session_api_url(session_id, "complete"),
                headers=_service_headers(),
            )

            return response.status_code == 200

    except Exception as e:
        logger.error(f"Error completing interview: {e}")
        return False


async def handle_applicant_response(
        message: dict,
        session_id: str,
        websocket: WebSocketProtocol
):
    """
    Process applicant's response and generate next question

    Args:
        message: Message from client containing transcript and video info
        session_id: Interview session ID
        websocket: WebSocket connection
    """
    # Get services for this session
    heygen = manager.get_heygen_service(session_id)
    engine = manager.get_interview_engine(session_id)
    analyzer = manager.get_analyzer(session_id)

    if not all([heygen, engine, analyzer]):
        logger.error(f"Services not initialized for session {session_id}")
        await websocket.send_json({
            'type': 'error',
            'message': 'Session services not initialized'
        })
        return

    try:
        # Extract data from message
        transcript = message.get('transcript', '')
        video_path = message.get('video_path', '')
        audio_data = message.get('audio_data')

        logger.info(f"Processing response for session {session_id}")

        # 1. Transcribe audio if transcript not provided
        if not transcript and audio_data:
            try:
                from ai_ml_services.video.transcription import transcribe_audio

                transcript = await transcribe_audio(audio_data)
                logger.info(f"Transcribed: {transcript[:100]}...")
            except Exception:
                transcript = ""
                logger.warning("Audio transcription service unavailable; continuing without transcript.")

        # 2. Analyze non-verbal behavior from video
        nonverbal_data = {}
        if video_path:
            logger.info(f"Analyzing video: {video_path}")
            nonverbal_data = await analyzer.analyze_video_async(video_path)

        # 3. Update exchange in Django with response
        update_data = {
            'transcript': transcript,
            'video_url': video_path,
            'sentiment': nonverbal_data.get('average_emotion', 'neutral'),
            'confidence_level': nonverbal_data.get('confidence_score', 50),
            'nonverbal_data': nonverbal_data
        }

        exchange_result = await update_exchange_in_django(session_id, update_data)

        if not exchange_result:
            await websocket.send_json({
                'type': 'error',
                'message': 'Failed to save response'
            })
            return

        # 4. Analyze response for flag resolution
        current_flag_id = exchange_result.get('current_flag_id')
        if current_flag_id:
            resolution = engine.analyze_response_for_flag_resolution(
                transcript=transcript,
                flag_id=current_flag_id,
                nonverbal_data=nonverbal_data
            )

            if resolution.get('resolved'):
                await websocket.send_json({
                    'type': 'flag_resolution',
                    'data': resolution
                })
                logger.info(f"Flag {current_flag_id} resolved")

        # 5. Update conversation history in engine
        engine.update_conversation_history(
            question=exchange_result.get('question_text', ''),
            answer=transcript,
            nonverbal=nonverbal_data
        )

        # 6. Generate next question
        next_question = engine.generate_next_question()

        # 7. Check if interview should continue
        if next_question is None:
            # Interview complete
            logger.info(f"Interview {session_id} complete")

            # Avatar says goodbye
            await heygen.stream_avatar_speech(
                text="Thank you for your responses. The interview is now complete. Your answers will be reviewed by our team.",
                websocket=websocket,
                emotion="Friendly"
            )

            await websocket.send_json({
                'type': 'interview_complete',
                'total_questions': exchange_result.get('question_number', 0)
            })

            # Trigger Django to complete interview and generate report
            await complete_interview_in_django(session_id)

            return

        # 8. Save next question to Django
        question_data = {
            'sequence_number': exchange_result.get('question_number', 0) + 1,
            'question_text': next_question['question'],
            'question_intent': next_question.get('intent', '')
        }

        await save_exchange_to_django(session_id, question_data)

        # 9. Avatar asks next question
        logger.info(f"Asking next question: {next_question['question'][:100]}...")

        await heygen.stream_avatar_speech(
            text=next_question['question'],
            websocket=websocket,
            emotion="Serious"
        )

        # 10. Notify client of next question
        await websocket.send_json({
            'type': 'next_question',
            'question': next_question['question'],
            'question_number': question_data['sequence_number'],
            'intent': next_question.get('intent', ''),
            'reasoning': next_question.get('reasoning', ''),
            'target_flag_id': next_question.get('target_flag_id')
        })

        logger.info(f"Next question sent successfully")

    except Exception as e:
        logger.error(f"Error handling applicant response: {e}", exc_info=True)
        await websocket.send_json({
            'type': 'error',
            'message': f'Error processing response: {str(e)}'
        })


async def handle_video_chunk(message: dict, session_id: str):
    """
    Handle streaming video chunks for real-time analysis

    Args:
        message: Message containing video chunk data
        session_id: Interview session ID
    """
    try:
        chunk_data = message.get('chunk')
        chunk_index = message.get('index', 0)

        # Store chunk for later processing
        # In production, you might stream this directly to CV pipeline
        logger.debug(f"Received video chunk {chunk_index} for session {session_id}")

        # TODO: Implement real-time video analysis if needed

    except Exception as e:
        logger.error(f"Error handling video chunk: {e}")


async def handle_ice_candidate(message: dict, session_id: str):
    """
    Handle WebRTC ICE candidate for HeyGen connection

    Args:
        message: Message containing ICE candidate
        session_id: Interview session ID
    """
    try:
        heygen = manager.get_heygen_service(session_id)
        if heygen:
            candidate = message.get('candidate')
            await heygen.send_ice_candidate(candidate)
            logger.debug(f"ICE candidate forwarded for session {session_id}")

    except Exception as e:
        logger.error(f"Error handling ICE candidate: {e}")


async def initialize_interview_session(
        session_id: str,
        websocket: WebSocketProtocol
) -> bool:
    """
    Initialize interview session with HeyGen and load session data

    Args:
        session_id: Interview session ID
        websocket: WebSocket connection

    Returns:
        bool: True if initialization successful
    """
    try:
        heygen = manager.get_heygen_service(session_id)

        # 1. Initialize HeyGen session
        logger.info(f"Creating HeyGen session for {session_id}")
        await heygen.create_streaming_session()

        # 2. Send session info to client
        await websocket.send_json({
            'type': 'session_initialized',
            'session_id': session_id,
            'heygen_session': heygen.session_id
        })

        # 3. Fetch session data from Django
        logger.info(f"Fetching session data from Django")
        session_data = await fetch_session_data(session_id)

        if not session_data:
            raise Exception("Failed to fetch session data from Django")

        # 4. Initialize interview engine with session data
        logger.info(f"Initializing interview engine")
        engine = EnhancedInterviewEngine(session_data)
        manager.set_interview_engine(session_id, engine)

        # 5. Generate first question
        logger.info(f"Generating first question")
        first_question = engine.generate_next_question()

        if not first_question:
            raise Exception("Failed to generate first question")

        # 6. Save first question to Django
        question_data = {
            'sequence_number': 1,
            'question_text': first_question['question'],
            'question_intent': first_question.get('intent', '')
        }

        await save_exchange_to_django(session_id, question_data)

        # 7. Avatar speaks first question
        logger.info(f"Avatar speaking first question: {first_question['question'][:100]}...")

        await heygen.stream_avatar_speech(
            text=first_question['question'],
            websocket=websocket,
            emotion="Serious"
        )

        # 8. Notify client
        await websocket.send_json({
            'type': 'question_asked',
            'question': first_question['question'],
            'question_number': 1,
            'intent': first_question.get('intent', '')
        })

        logger.info(f"Interview session {session_id} initialized successfully")
        return True

    except Exception as e:
        logger.error(f"Error initializing interview session: {e}", exc_info=True)
        await websocket.send_json({
            'type': 'error',
            'message': f'Failed to initialize interview: {str(e)}'
        })
        return False


async def handle_websocket_message(
        message_data: dict,
        session_id: str,
        websocket: WebSocketProtocol
):
    """
    Route incoming WebSocket messages to appropriate handlers

    Args:
        message_data: Parsed JSON message
        session_id: Interview session ID
        websocket: WebSocket connection
    """

    message_type = message_data.get('type')

    logger.debug(f"Handling message type: {message_type} for session {session_id}")

    if message_type == 'response_complete':
        await handle_applicant_response(message_data, session_id, websocket)

    elif message_type == 'video_chunk':
        await handle_video_chunk(message_data, session_id)

    elif message_type == 'ice_candidate':
        await handle_ice_candidate(message_data, session_id)

    elif message_type == 'ping':
        # Heartbeat
        await websocket.send_json({'type': 'pong'})

    else:
        logger.warning(f"Unknown message type: {message_type}")
        await websocket.send_json({
            'type': 'error',
            'message': f'Unknown message type: {message_type}'
        })


# Export manager and handlers
__all__ = [
    'manager',
    'InterviewConnectionManager',
    'handle_applicant_response',
    'initialize_interview_session',
    'handle_websocket_message'
]

