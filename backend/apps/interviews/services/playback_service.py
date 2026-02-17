# ============================================================================
# PART 5: INTERVIEW PLAYBACK SYSTEM
# ============================================================================

# backend/apps/interviews/playback_service.py
from django.db.models import Prefetch
from apps.interviews.models import DynamicInterviewSession, InterviewExchange


class InterviewPlaybackService:
    """
    Service to generate playback data for interview review
    """

    @staticmethod
    def get_playback_data(session_id):
        """
        Get complete playback data for an interview session
        Returns timeline with video URLs, transcripts, and analysis
        """

        session = DynamicInterviewSession.objects.prefetch_related(
            Prefetch(
                'exchanges',
                queryset=InterviewExchange.objects.select_related('nonverbal_analysis').order_by('sequence_number')
            ),
            'interrogation_flags'
        ).get(session_id=session_id)

        # Build timeline
        timeline = []
        cumulative_time = 0

        for exchange in session.exchanges.all():
            # Calculate timestamps
            start_time = cumulative_time
            end_time = cumulative_time + exchange.response_duration

            # Build exchange data
            exchange_data = {
                'sequence': exchange.sequence_number,
                'start_time': start_time,
                'end_time': end_time,
                'duration': exchange.response_duration,
                'question': {
                    'text': exchange.question_text,
                    'intent': exchange.question_intent,
                    'asked_at': exchange.question_generated_at.isoformat()
                },
                'response': {
                    'transcript': exchange.transcript,
                    'video_url': exchange.video_url,
                    'answered_at': exchange.answered_at.isoformat() if exchange.answered_at else None
                },
                'analysis': {
                    'sentiment': exchange.sentiment,
                    'confidence_level': exchange.confidence_level,
                    'quality_score': exchange.response_quality_score,
                    'relevance_score': exchange.relevance_score,
                    'key_points': exchange.key_points_extracted,
                    'inconsistencies': exchange.inconsistencies_detected
                }
            }

            # Add non-verbal analysis if available
            if hasattr(exchange, 'nonverbal_analysis'):
                nonverbal = exchange.nonverbal_analysis
                exchange_data['nonverbal'] = {
                    'deception_score': nonverbal.deception_score,
                    'confidence_score': nonverbal.confidence_score,
                    'stress_level': nonverbal.stress_level,
                    'eye_contact_percentage': nonverbal.eye_contact_percentage,
                    'fidgeting_detected': nonverbal.fidgeting_detected,
                    'behavioral_red_flags': nonverbal.behavioral_red_flags,
                    'emotion': nonverbal.average_emotion
                }

            # Mark critical moments
            exchange_data['is_critical'] = InterviewPlaybackService._is_critical_moment(exchange)

            timeline.append(exchange_data)
            cumulative_time = end_time

        # Generate highlights
        highlights = InterviewPlaybackService._generate_highlights(timeline)

        # Compile playback package
        playback_data = {
            'session': {
                'id': session.session_id,
                'applicant': session.application.applicant.full_name,
                'status': session.status,
                'started_at': session.started_at.isoformat(),
                'completed_at': session.completed_at.isoformat() if session.completed_at else None,
                'total_duration': session.duration_seconds,
                'overall_score': session.overall_score,
                'confidence_score': session.confidence_score,
                'consistency_score': session.consistency_score,
                'recommendation': session.recommendations
            },
            'timeline': timeline,
            'highlights': highlights,
            'flags': [
                {
                    'type': flag.flag_type,
                    'severity': flag.severity,
                    'context': flag.context,
                    'status': flag.status,
                    'resolution_summary': flag.resolution_summary
                }
                for flag in session.interrogation_flags.all()
            ],
            'summary': session.interview_summary,
            'red_flags': session.red_flags
        }

        return playback_data

    @staticmethod
    def _is_critical_moment(exchange):
        """Determine if this exchange is a critical moment"""

        critical_indicators = []

        # High deception
        if hasattr(exchange, 'nonverbal_analysis'):
            if exchange.nonverbal_analysis.deception_score > 70:
                critical_indicators.append('high_deception')

        # Poor quality response
        if exchange.response_quality_score and exchange.response_quality_score < 40:
            critical_indicators.append('poor_quality')

        # Inconsistencies detected
        if exchange.inconsistencies_detected and len(exchange.inconsistencies_detected) > 0:
            critical_indicators.append('inconsistencies')

        # Multiple behavioral red flags
        if hasattr(exchange, 'nonverbal_analysis'):
            if len(exchange.nonverbal_analysis.behavioral_red_flags) >= 3:
                critical_indicators.append('behavioral_red_flags')

        return {
            'is_critical': len(critical_indicators) > 0,
            'reasons': critical_indicators
        }

    @staticmethod
    def _generate_highlights(timeline):
        """Generate key highlights/bookmarks for quick review"""

        highlights = []

        for exchange_data in timeline:
            # Add to highlights if critical
            if exchange_data['is_critical']['is_critical']:
                highlights.append({
                    'time': exchange_data['start_time'],
                    'title': f"Q{exchange_data['sequence']}: Critical Moment",
                    'description': ', '.join(exchange_data['is_critical']['reasons']).replace('_', ' ').title(),
                    'severity': 'high',
                    'exchange_id': exchange_data['sequence']
                })

            # Add high deception moments
            if 'nonverbal' in exchange_data and exchange_data['nonverbal']['deception_score'] > 80:
                highlights.append({
                    'time': exchange_data['start_time'],
                    'title': f"Q{exchange_data['sequence']}: High Deception",
                    'description': f"Deception score: {exchange_data['nonverbal']['deception_score']}%",
                    'severity': 'critical',
                    'exchange_id': exchange_data['sequence']
                })

            # Add inconsistencies
            if exchange_data['analysis']['inconsistencies']:
                for inconsistency in exchange_data['analysis']['inconsistencies']:
                    highlights.append({
                        'time': exchange_data['start_time'],
                        'title': f"Q{exchange_data['sequence']}: Inconsistency Detected",
                        'description': inconsistency.get('issue', 'Inconsistency found'),
                        'severity': inconsistency.get('severity', 'medium'),
                        'exchange_id': exchange_data['sequence']
                    })

        return sorted(highlights, key=lambda x: x['time'])


# API Endpoints
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

playback_router = APIRouter(prefix="/api/playback", tags=["playback"])

@playback_router.get("/{session_id}")
async def get_interview_playback(session_id: str):
    """Get complete playback data for interview review"""

    try:
        playback_data = InterviewPlaybackService.get_playback_data(session_id)
        return JSONResponse(playback_data)
    except DynamicInterviewSession.DoesNotExist:
        raise HTTPException(status_code=404, detail="Interview session not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@playback_router.get("/{session_id}/video/{exchange_id}")
async def get_exchange_video_url(session_id: str, exchange_id: int):
    """Get pre-signed URL for specific exchange video"""

    try:
        exchange = InterviewExchange.objects.get(
            session__session_id=session_id,
            sequence_number=exchange_id
        )

        # Generate pre-signed URL (valid for 1 hour)
        from documents.services import DocumentService
        doc_service = DocumentService()
        video_url = doc_service.get_presigned_url(exchange.video_url, expiration=3600)

        return JSONResponse({
            'video_url': video_url,
            'duration': exchange.response_duration,
            'transcript': exchange.transcript
        })
    except InterviewExchange.DoesNotExist:
        raise HTTPException(status_code=404, detail="Exchange not found")
