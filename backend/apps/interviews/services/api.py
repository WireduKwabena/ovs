# ============================================================================
# 2. FastAPI WebSocket Endpoint with HeyGen Integration
# ============================================================================

# backend/apps/interviews/api.py
from asyncio.log import logger
from datetime import timezone
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import JSONResponse
import uuid

from apps.interviews.services import HeyGenAvatarService

app = FastAPI()


class InterviewConnectionManager:
    """Manage active interview WebSocket connections"""

    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}
        self.heygen_services: dict[str, HeyGenAvatarService] = {}

    async def connect(self, session_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[session_id] = websocket
        self.heygen_services[session_id] = HeyGenAvatarService()

    def disconnect(self, session_id: str):
        if session_id in self.active_connections:
            del self.active_connections[session_id]
        if session_id in self.heygen_services:
            del self.heygen_services[session_id]

    async def send_message(self, session_id: str, message: dict):
        if session_id in self.active_connections:
            await self.active_connections[session_id].send_json(message)

    def get_heygen_service(self, session_id: str) -> HeyGenAvatarService:
        return self.heygen_services.get(session_id)


manager = InterviewConnectionManager()


@app.websocket("/ws/interview/{session_id}")
async def interview_websocket(websocket: WebSocket, session_id: str):
    """
    Main WebSocket endpoint for AI interrogation with HeyGen avatar
    """
    await manager.connect(session_id, websocket)
    heygen = manager.get_heygen_service(session_id)

    try:
        # Initialize HeyGen session
        await heygen.create_streaming_session()

        # Send session info to client
        await websocket.send_json({
            'type': 'session_initialized',
            'session_id': session_id,
            'heygen_session': heygen.session_id
        })

        # Get interview session from database
        from apps.interviews.models import DynamicInterviewSession
        from .enhanced_engine import EnhancedInterviewEngine
        from .nonverbal_analyzer import NonVerbalAnalyzer

        db_session = DynamicInterviewSession.objects.get(session_id=session_id)
        engine = EnhancedInterviewEngine(db_session)
        analyzer = NonVerbalAnalyzer()

        # Generate and speak first question
        first_question = engine.generate_next_question()

        if first_question:
            # Stream avatar speaking the question
            await heygen.stream_avatar_speech(
                text=first_question['question'],
                websocket=websocket,
                emotion="Serious"
            )

            # Save question to database
            from apps.interviews.models import InterviewExchange
            exchange = InterviewExchange.objects.create(
                session=db_session,
                sequence_number=db_session.current_question_number,
                question_text=first_question['question'],
                question_intent=first_question['intent']
            )

            await websocket.send_json({
                'type': 'question_asked',
                'question': first_question['question'],
                'exchange_id': exchange.id,
                'question_number': db_session.current_question_number
            })

        # Main conversation loop
        while True:
            # Receive message from client
            data = await websocket.receive()

            if 'text' in data:
                message = json.loads(data['text'])

                # Handle different message types
                if message['type'] == 'response_complete':
                    # Applicant finished speaking
                    await handle_applicant_response(
                        message,
                        db_session,
                        engine,
                        analyzer,
                        heygen,
                        websocket
                    )

                elif message['type'] == 'video_chunk':
                    # Store video chunk for analysis
                    await handle_video_chunk(message, db_session)

                elif message['type'] == 'ice_candidate':
                    # Forward ICE candidate to HeyGen
                    await heygen.send_ice_candidate(message['candidate'])

            elif 'bytes' in data:
                # Handle binary data (video/audio)
                await handle_binary_data(data['bytes'], db_session)

    except WebSocketDisconnect:
        logger.info(f"Client disconnected: {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
        await websocket.send_json({
            'type': 'error',
            'message': str(e)
        })
    finally:
        # Cleanup
        await heygen.close_session()
        manager.disconnect(session_id)
        await websocket.close()


async def handle_applicant_response(
    message: dict,
    session,
    engine,
    analyzer,
    heygen: HeyGenAvatarService,
    websocket: WebSocket
):
    """Process applicant's response and generate next question"""

    transcript = message.get('transcript')
    video_path = message.get('video_path')
    audio_data = message.get('audio_data')

    # 1. Transcribe if not provided
    if not transcript and audio_data:
        from apps.interviews.tasks import transcribe_audio_async
        transcript = await transcribe_audio_async(audio_data)

    # 2. Analyze non-verbal behavior
    if video_path:
        nonverbal_data = analyzer.analyze_video_stream(video_path)
    else:
        nonverbal_data = {}

    # 3. Save exchange
    from apps.interviews.models import InterviewExchange, NonVerbalAnalysis

    exchange = InterviewExchange.objects.filter(
        session=session,
        sequence_number=session.current_question_number
    ).first()

    if exchange:
        exchange.transcript = transcript
        exchange.video_url = video_path
        exchange.sentiment = nonverbal_data.get('average_emotion', 'neutral')
        exchange.confidence_level = nonverbal_data.get('confidence_score', 50)
        exchange.save()

        # Save non-verbal analysis
        NonVerbalAnalysis.objects.create(
            exchange=exchange,
            **nonverbal_data
        )

    # 4. Update conversation history
    session.conversation_history.append({
        'question': exchange.question_text,
        'answer': transcript,
        'nonverbal': nonverbal_data
    })
    session.save()

    # 5. Check flag resolution
    if hasattr(session, 'current_flag_id') and session.current_flag_id:
        resolution = engine.analyze_response_for_flag_resolution(
            transcript,
            session.current_flag_id,
            nonverbal_data
        )

        await websocket.send_json({
            'type': 'flag_resolution',
            'data': resolution
        })

    # 6. Generate next question
    next_question = engine.generate_next_question()

    if next_question is None:
        # Interview complete
        session.status = 'completed'
        session.completed_at = timezone.now()
        session.save()

        # Generate final report
        from apps.interviews.tasks import generate_final_report
        generate_final_report.delay(session.id)

        # Avatar says goodbye
        await heygen.stream_avatar_speech(
            text="Thank you. The interview is now complete. Your responses will be reviewed by our team.",
            websocket=websocket,
            emotion="Friendly"
        )

        await websocket.send_json({
            'type': 'interview_complete',
            'total_questions': session.current_question_number
        })

        return

    # 7. Avatar asks next question
    session.current_question_number += 1
    session.current_flag_id = next_question.get('target_flag_id')
    session.save()

    await heygen.stream_avatar_speech(
        text=next_question['question'],
        websocket=websocket,
        emotion="Serious"
    )

    # Create next exchange record
    InterviewExchange.objects.create(
        session=session,
        sequence_number=session.current_question_number,
        question_text=next_question['question'],
        question_intent=next_question['intent']
    )

    # Get next question
    next_question = engine.generate_next_question()

    if next_question:
        # Build interview context for emotion decision
        interview_context = engine.get_interview_context()
        interview_context['question_intent'] = next_question['intent']

        # Stream avatar with adaptive emotion
        await heygen.stream_adaptive_response(
            text=next_question['question'],
            websocket=websocket,
            interview_context=interview_context
        )

        # Notify frontend of emotion used
        # Notify frontend of emotion used
        await websocket.send_json({
            'type': 'avatar_emotion_changed',
            'emotion': interview_context.get('emotion_used'),
            'reason': interview_context.get('emotion_reason')
        })

    await websocket.send_json({
        'type': 'next_question',
        'question': next_question['question'],
        'question_number': session.current_question_number,
        'intent': next_question['intent'],
        'reasoning': next_question.get('reasoning', '')
    })


async def handle_video_chunk(message: dict, session):
    """Handle streaming video chunks for real-time analysis"""
    # Store chunk for later processing
    # In production, you might stream this directly to your CV pipeline
    pass


async def handle_binary_data(data: bytes, session):
    """Handle binary audio/video data"""
    # Save to temp storage for processing
    pass





# ============================================================================
# 3. API Endpoint to Start Interview
# ============================================================================

@app.post("/api/interviews/interrogation/start/")
async def start_interrogation_interview(request_data: dict):
    """
    Initialize AI interrogation interview with HeyGen avatar
    """
    from apps.interviews.models import DynamicInterviewSession, InterrogationFlag
    from .flag_generator import InterrogationFlagGenerator
    from apps.applications import VettingCase

    application_id = request_data.get('application_id')

    try:
        application = VettingCase.objects.get(case_id=application_id)
    except VettingCase.DoesNotExist:
        raise HTTPException(status_code=404, detail="Application not found")

    # Generate interrogation flags from vetting results
    flags_data = InterrogationFlagGenerator.generate_flags_from_vetting(application)

    # Create interview session
    session_id = f"INT-{uuid.uuid4().hex[:10].upper()}"
    session = DynamicInterviewSession.objects.create(
        session_id=session_id,
        application=application,
        status='in_progress',
        applicant_context=_extract_applicant_context(application)
    )

    # Create interrogation flags
    flags = []
    for flag_data in flags_data:
        flag = InterrogationFlag.objects.create(
            session=session,
            **flag_data
        )
        flags.append({
            'id': flag.id,
            'type': flag.flag_type,
            'severity': flag.severity,
            'context': flag.context
        })

    return {
        'success': True,
        'session_id': session_id,
        'interrogation_flags': flags,
        'websocket_url': f'ws://yourserver.com/ws/interview/{session_id}'
    }


def _extract_applicant_context(application):
    """Extract context from application for interview engine"""
    from apps.interviews.context_extractor import ApplicantContextExtractor
    return ApplicantContextExtractor.extract_from_application(application)



