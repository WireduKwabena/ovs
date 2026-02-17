# backend/apps/interviews/analytics.py
from apps.interviews.services import analytics_service


class InterviewAnalytics:
    @staticmethod
    def log_interview_metrics(session):
        metrics = {
            'session_id': session.session_id,
            'duration': session.duration_seconds,
            'questions_asked': session.current_question_number,
            'flags_resolved': session.interrogation_flags.filter(status='resolved').count(),
            'heygen_cost': calculate_heygen_cost(session),
            'completion_rate': 1.0 if session.status == 'completed' else 0.0
        }
        
        # Log to your analytics system
        analytics_service.track('interview_completed', metrics)