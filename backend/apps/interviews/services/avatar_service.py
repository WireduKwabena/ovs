# backend/apps/interviews/avatar_service.py
import json
from datetime import timezone

import aiohttp
from django.conf import settings
import requests
import asyncio
from fastapi import WebSocket

from apps.interviews.models import DynamicInterviewSession, NonVerbalAnalysis, InterviewExchange
from apps.interviews.services import EnhancedInterviewEngine


class AIAvatarService:
    """Integration with avatar generation services"""

    def __init__(self, provider='heygen'):  # or 'synthesia', 'd-id'
        self.provider = provider
        self.api_key = settings.AVATAR_API_KEY
        self.avatar_id = settings.AVATAR_ID  # Pre-created avatar

    async def stream_avatar_response(self, text, websocket: WebSocket):
        """Generate and stream avatar video in real-time"""

        if self.provider == 'heygen':
            await self._stream_heygen(text, websocket)
        elif self.provider == 'd-id':
            await self._stream_did(text, websocket)

    async def _stream_heygen(self, text, websocket):
        """Stream using HeyGen API"""

        # Step 1: Generate TTS audio
        tts_response = requests.post(
            'https://api.heygen.com/v1/tts',
            headers={'Authorization': f'Bearer {self.api_key}'},
            json={
                'text': text,
                'voice_id': settings.AVATAR_VOICE_ID,
                'emotion': 'professional'
            }
        )
        audio_url = tts_response.json()['audio_url']

        # Step 2: Generate lip-synced video
        video_response = requests.post(
            'https://api.heygen.com/v1/avatar/stream',
            headers={'Authorization': f'Bearer {self.api_key}'},
            json={
                'avatar_id': self.avatar_id,
                'audio_url': audio_url,
                'streaming': True
            },
        )


        # Step 3: Stream video chunks via WebSocket
        stream_url = video_response.json()['stream_url']

        async with aiohttp.ClientSession() as session:
            async with session.get(stream_url) as resp:
                async for chunk in resp.content.iter_chunked(8192):
                    await websocket.send_bytes(chunk)

        await websocket.send_json({'type': 'stream_complete'})

    async def _stream_did(self, text, websocket):
        """Stream using D-ID API"""

        response = requests.post(
            'https://api.d-id.com/talks/streams',
            headers={
                'Authorization': f'Basic {self.api_key}',
                'Content-Type': 'application/json'
            },
            json={
                'source_url': settings.AVATAR_IMAGE_URL,
                'script': {
                    'type': 'text',
                    'input': text,
                    'provider': {
                        'type': 'microsoft',
                        'voice_id': 'en-US-JennyNeural'
                    }
                },
                'config': {
                    'stitch': True,
                    'fluent': True
                }
            }
        )

        stream_data = response.json()
        session_id = stream_data['id']
        ice_servers = stream_data['ice_servers']
        offer_sdp = stream_data['offer']['sdp']

        # WebRTC signaling for real-time streaming
        await websocket.send_json({
            'type': 'webrtc_offer',
            'sdp': offer_sdp,
            'ice_servers': ice_servers,
            'session_id': session_id
        })

# FastAPI WebSocket endpoint
@app.websocket("/ws/interview/{session_id}")
async def interview_websocket(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for real-time interview streaming"""

    await websocket.accept()

    session = DynamicInterviewSession.objects.get(session_id=session_id)
    avatar_service = AIAvatarService()
    engine = EnhancedInterviewEngine(session)
    nonverbal_analyzer = NonVerbalAnalyzer()

    try:
        while True:
            # Receive video frame from applicant
            data = await websocket.receive()

            if data['type'] == 'websocket.receive':
                message = json.loads(data['text']) if 'text' in data else None

                if message and message['type'] == 'video_chunk':
                    # Save video chunk for non-verbal analysis
                    video_chunk = message['data']
                    # Process in background task
                    asyncio.create_task(
                        process_video_chunk(session.id, video_chunk)
                    )

                elif message and message['type'] == 'audio_complete':
                    # Applicant finished speaking
                    audio_data = message['audio']

                    # 1. Transcribe speech
                    transcript = await transcribe_audio_async(audio_data)

                    # 2. Analyze non-verbal behavior
                    video_path = message['video_path']
                    nonverbal_data = nonverbal_analyzer.analyze_video_stream(video_path)

                    # 3. Save exchange
                    exchange = InterviewExchange.objects.create(
                        session=session,
                        sequence_number=session.current_question_number,
                        transcript=transcript,
                        video_url=video_path,
                        sentiment=nonverbal_data['average_emotion'],
                        confidence_level=nonverbal_data['confidence_score']
                    )

                    # 4. Save non-verbal analysis
                    NonVerbalAnalysis.objects.create(
                        exchange=exchange,
                        facial_expressions=nonverbal_data.get('facial_expressions', {}),
                        average_emotion=nonverbal_data['average_emotion'],
                        eye_contact_percentage=nonverbal_data['eye_contact_percentage'],
                        deception_score=nonverbal_data['deception_score'],
                        confidence_score=nonverbal_data['confidence_score'],
                        stress_level=nonverbal_data.get('stress_level', 0),
                        behavioral_red_flags=nonverbal_data['behavioral_red_flags']
                    )

                    # 5. Update conversation history
                    session.conversation_history.append({
                        'question': session.last_question,
                        'answer': transcript,
                        'nonverbal': nonverbal_data
                    })
                    session.save()

                    # 6. Check if this resolves any flags
                    if hasattr(session, 'current_flag_id'):
                        resolution = engine.analyze_response_for_flag_resolution(
                            transcript,
                            session.current_flag_id,
                            nonverbal_data
                        )

                        await websocket.send_json({
                            'type': 'flag_resolution',
                            'data': resolution
                        })

                    # 7. Generate next question
                    next_question = engine.generate_next_question()

                    if next_question is None:
                        # Interview complete
                        session.status = 'completed'
                        session.completed_at = timezone.now()
                        session.save()

                        await websocket.send_json({
                            'type': 'interview_complete',
                            'message': 'All interrogation flags have been addressed.'
                        })
                        break

                    # 8. Stream avatar speaking the next question
                    session.last_question = next_question['question']
                    session.current_flag_id = next_question.get('target_flag_id')
                    session.current_question_number += 1
                    session.save()

                    # Send question text first
                    await websocket.send_json({
                        'type': 'next_question',
                        'question': next_question['question'],
                        'question_number': session.current_question_number,
                        'intent': next_question['intent']
                    })

                    # Stream avatar video
                    await avatar_service.stream_avatar_response(
                        next_question['question'],
                        websocket
                    )

    except Exception as e:
        print(f"WebSocket error: {e}")
        await websocket.send_json({
            'type': 'error',
            'message': str(e)
        })
    finally:
        await websocket.close()