# backend/apps/interviews/tasks.py
import json
from datetime import timezone

from celery import shared_task
from google.cloud import speech_v1
import openai
from .models import InterviewExchange, DynamicInterviewSession
from .ai_engine import DynamicInterviewEngine


@shared_task
def transcribe_and_analyze(exchange_id):
    """Transcribe video and analyze response in real-time"""

    exchange = InterviewExchange.objects.get(id=exchange_id)
    session = exchange.session

    try:
        # 1. Extract audio from video
        audio_path = extract_audio(exchange.video_url)

        # 2. Transcribe (Google Speech-to-Text)
        transcript, confidence = transcribe_audio_google(audio_path)

        # 3. Analyze response with AI
        engine = DynamicInterviewEngine(session)
        analysis = engine.analyze_response(transcript, exchange.question_intent)

        # 4. Update exchange
        exchange.transcript = transcript
        exchange.confidence_level = confidence
        exchange.sentiment = analysis['sentiment']
        exchange.key_points_extracted = analysis['key_points']
        exchange.inconsistencies_detected = analysis['inconsistencies']
        exchange.response_quality_score = analysis['quality_score']
        exchange.relevance_score = analysis['relevance_score']
        exchange.answered_at = timezone.now()
        exchange.save()

        return {
            'transcript': transcript,
            'analysis': analysis
        }

    except Exception as e:
        return {
            'error': str(e),
            'transcript': '',
            'analysis': {}
        }


def transcribe_audio_google(audio_path):
    """Transcribe using Google Speech-to-Text"""
    client = speech_v1.SpeechClient()

    with open(audio_path, 'rb') as audio_file:
        content = audio_file.read()

    audio = speech_v1.RecognitionAudio(content=content)
    config = speech_v1.RecognitionConfig(
        encoding=speech_v1.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=44100,
        language_code='en-US',
        enable_automatic_punctuation=True,
        model='video'
    )

    response = client.recognize(config=config, audio=audio)

    transcript = ''
    total_confidence = 0

    for result in response.results:
        transcript += result.alternatives[0].transcript + ' '
        total_confidence += result.alternatives[0].confidence

    avg_confidence = total_confidence / len(response.results) if response.results else 0

    return transcript.strip(), avg_confidence * 100


@shared_task
def generate_final_report(session_id):
    """Generate comprehensive interview report after completion"""

    session = DynamicInterviewSession.objects.get(id=session_id)
    exchanges = session.exchanges.all().order_by('sequence_number')

    # Compile conversation
    full_conversation = []
    for exchange in exchanges:
        full_conversation.append({
            'question': exchange.question_text,
            'answer': exchange.transcript,
            'quality_score': exchange.response_quality_score,
            'sentiment': exchange.sentiment,
            'key_points': exchange.key_points_extracted
        })

    # Generate comprehensive analysis
    prompt = f"""You are an expert HR analyst. Analyze this complete interview:

INTERVIEW TRANSCRIPT:
{json.dumps(full_conversation, indent=2)}

APPLICANT CONTEXT:
{json.dumps(session.applicant_context, indent=2)}

INCONSISTENCIES DETECTED:
{json.dumps(session.inconsistencies_found, indent=2)}

Provide a comprehensive evaluation:

1. OVERALL ASSESSMENT (score 0-100)
2. KEY STRENGTHS (3-5 points)
3. AREAS OF CONCERN (if any)
4. CONSISTENCY ANALYSIS
5. COMPLETENESS (did they provide sufficient information?)
6. RED FLAGS (if any)
7. RECOMMENDATION (Strongly Recommend / Recommend / Neutral / Not Recommend / Reject)
8. SUMMARY (2-3 paragraphs)

Return as JSON:
{{
    "overall_score": 0-100,
    "confidence_score": 0-100,
    "consistency_score": 0-100,
    "completeness_score": 0-100,
    "strengths": ["strength1", "strength2"],
    "concerns": ["concern1", "concern2"],
    "red_flags": ["flag1", "flag2"],
    "recommendation": "Strongly Recommend/Recommend/Neutral/Not Recommend/Reject",
    "summary": "Detailed summary text",
    "interviewer_notes": "Notes for HR team"
}}
"""

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are an expert HR analyst."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=1500
        )

        report = json.loads(response.choices[0].message.content)

        # Update session
        session.overall_score = report['overall_score']
        session.confidence_score = report['confidence_score']
        session.consistency_score = report['consistency_score']
        session.completeness_score = report['completeness_score']
        session.interview_summary = report['summary']
        session.red_flags = report['red_flags']
        session.recommendations = report['recommendation']
        session.save()

        # Send notification
        from apps.notifications.services import NotificationService
        NotificationService.send_interview_complete(session)

        return report

    except Exception as e:
        print(f"Error generating report: {e}")
        return None