# backend/apps/interviews/analytics_service.py
from django.db.models import Avg, Count, Q, F, Sum
from datetime import datetime, timedelta
from apps.interviews.models import (
    DynamicInterviewSession, 
    InterviewExchange,
    InterrogationFlag,
    NonVerbalAnalysis
)

class InterviewAnalytics:
    """Comprehensive analytics for AI interviews"""
    
    @staticmethod
    def get_dashboard_metrics(days=30):
        """Get high-level dashboard metrics"""
        
        start_date = datetime.now() - timedelta(days=days)
        
        sessions = DynamicInterviewSession.objects.filter(
            created_at__gte=start_date
        )
        
        # Core metrics
        total_interviews = sessions.count()
        completed_interviews = sessions.filter(status='completed').count()
        completion_rate = (completed_interviews / total_interviews * 100) if total_interviews > 0 else 0
        
        # Average metrics
        avg_duration = sessions.filter(
            status='completed'
        ).aggregate(
            avg_duration=Avg('duration_seconds')
        )['avg_duration'] or 0
        
        avg_questions = sessions.filter(
            status='completed'
        ).aggregate(
            avg_questions=Avg('current_question_number')
        )['avg_questions'] or 0
        
        # Scoring metrics
        avg_overall_score = sessions.filter(
            overall_score__isnull=False
        ).aggregate(
            avg_score=Avg('overall_score')
        )['avg_score'] or 0
        
        avg_deception = NonVerbalAnalysis.objects.filter(
            exchange__session__created_at__gte=start_date
        ).aggregate(
            avg_deception=Avg('deception_score')
        )['avg_deception'] or 0
        
        # Flag resolution
        total_flags = InterrogationFlag.objects.filter(
            session__created_at__gte=start_date
        ).count()
        
        resolved_flags = InterrogationFlag.objects.filter(
            session__created_at__gte=start_date,
            status='resolved'
        ).count()
        
        flag_resolution_rate = (resolved_flags / total_flags * 100) if total_flags > 0 else 0
        
        # Cost calculation
        total_minutes = sessions.aggregate(
            total_minutes=Sum(F('duration_seconds') / 60)
        )['total_minutes'] or 0
        
        estimated_cost = total_minutes * 0.50  # $0.50 per minute HeyGen
        
        return {
            'overview': {
                'total_interviews': total_interviews,
                'completed_interviews': completed_interviews,
                'completion_rate': round(completion_rate, 1),
                'in_progress': sessions.filter(status='in_progress').count(),
                'abandoned': sessions.filter(status='abandoned').count()
            },
            'performance': {
                'avg_duration_minutes': round(avg_duration / 60, 1),
                'avg_questions_asked': round(avg_questions, 1),
                'avg_overall_score': round(avg_overall_score, 1),
                'avg_deception_score': round(avg_deception, 1)
            },
            'flags': {
                'total_flags': total_flags,
                'resolved_flags': resolved_flags,
                'resolution_rate': round(flag_resolution_rate, 1),
                'critical_flags': InterrogationFlag.objects.filter(
                    session__created_at__gte=start_date,
                    severity='critical'
                ).count()
            },
            'cost': {
                'total_minutes': round(total_minutes, 1),
                'estimated_cost': round(estimated_cost, 2),
                'cost_per_interview': round(estimated_cost / total_interviews, 2) if total_interviews > 0 else 0
            }
        }
    
    @staticmethod
    def get_trend_data(days=30):
        """Get time-series data for charts"""
        
        start_date = datetime.now() - timedelta(days=days)
        
        # Daily interview counts
        daily_interviews = DynamicInterviewSession.objects.filter(
            created_at__gte=start_date
        ).extra(
            select={'day': 'DATE(created_at)'}
        ).values('day').annotate(
            count=Count('id'),
            completed=Count('id', filter=Q(status='completed')),
            avg_score=Avg('overall_score')
        ).order_by('day')
        
        # Format for chart
        trend_data = {
            'dates': [item['day'].strftime('%Y-%m-%d') for item in daily_interviews],
            'interviews': [item['count'] for item in daily_interviews],
            'completed': [item['completed'] for item in daily_interviews],
            'avg_scores': [round(item['avg_score'], 1) if item['avg_score'] else 0 for item in daily_interviews]
        }
        
        return trend_data
    
    @staticmethod
    def get_flag_breakdown():
        """Get breakdown of interrogation flags"""
        
        flags_by_type = InterrogationFlag.objects.values(
            'flag_type'
        ).annotate(
            count=Count('id'),
            resolved=Count('id', filter=Q(status='resolved')),
            critical=Count('id', filter=Q(severity='critical'))
        ).order_by('-count')
        
        return list(flags_by_type)
    
    @staticmethod
    def get_deception_analysis():
        """Analyze deception patterns"""
        
        # Deception score distribution
        deception_ranges = {
            'low': NonVerbalAnalysis.objects.filter(deception_score__lt=30).count(),
            'medium': NonVerbalAnalysis.objects.filter(
                deception_score__gte=30,
                deception_score__lt=70
            ).count(),
            'high': NonVerbalAnalysis.objects.filter(deception_score__gte=70).count()
        }
        
        # Common behavioral red flags
        red_flags = NonVerbalAnalysis.objects.exclude(
            behavioral_red_flags=[]
        ).values_list('behavioral_red_flags', flat=True)
        
        from collections import Counter
        flag_counter = Counter()
        for flags_list in red_flags:
            flag_counter.update(flags_list)
        
        return {
            'distribution': deception_ranges,
            'common_red_flags': dict(flag_counter.most_common(10))
        }
    
    @staticmethod
    def get_interview_quality_metrics():
        """Get quality metrics for interviews"""
        
        exchanges = InterviewExchange.objects.filter(
            response_quality_score__isnull=False
        )
        
        return {
            'avg_response_quality': round(
                exchanges.aggregate(Avg('response_quality_score'))['response_quality_score__avg'] or 0,
                1
            ),
            'avg_relevance': round(
                exchanges.aggregate(Avg('relevance_score'))['relevance_score__avg'] or 0,
                1
            ),
            'avg_confidence': round(
                exchanges.aggregate(Avg('confidence_level'))['confidence_level__avg'] or 0,
                1
            )
        }


# API endpoint for dashboard
from fastapi import APIRouter
from fastapi.responses import JSONResponse

analytics_router = APIRouter(prefix="/api/analytics", tags=["analytics"])

@analytics_router.get("/dashboard")
async def get_analytics_dashboard(days: int = 30):
    """Get comprehensive analytics dashboard data"""

    return JSONResponse({
        'metrics': InterviewAnalytics.get_dashboard_metrics(days),
        'trends': InterviewAnalytics.get_trend_data(days),
        'flags': InterviewAnalytics.get_flag_breakdown(),
        'deception': InterviewAnalytics.get_deception_analysis(),
        'quality': InterviewAnalytics.get_interview_quality_metrics()
    })

@analytics_router.get("/interview/{session_id}")
async def get_interview_details(session_id: str):
    """Get detailed analytics for specific interview"""

    session = DynamicInterviewSession.objects.get(session_id=session_id)
    exchanges = session.exchanges.all()

    return JSONResponse({
        'session': {
            'id': session.session_id,
            'status': session.status,
            'duration': session.duration_seconds,
            'overall_score': session.overall_score,
            'questions_asked': session.current_question_number
        },
        'exchanges': [
            {
                'question': ex.question_text,
                'transcript': ex.transcript,
                'quality_score': ex.response_quality_score,
                'deception_score': ex.nonverbal_analysis.deception_score if hasattr(ex, 'nonverbal_analysis') else None,
                'sentiment': ex.sentiment
            }
            for ex in exchanges
        ],
        'flags': [
            {
                'type': flag.flag_type,
                'severity': flag.severity,
                'context': flag.context,
                'status': flag.status
            }
            for flag in session.interrogation_flags.all()
        ]
    })