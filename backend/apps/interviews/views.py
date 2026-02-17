# backend/apps/interviews/views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.http import HttpResponse
from datetime import datetime
from .models import DynamicInterviewSession
from .serializers import DynamicInterviewSessionSerializer
from .reports import InterviewReportGenerator
from .services.analytics_service import InterviewAnalytics
import requests

class InterviewViewSet(viewsets.ModelViewSet):
    queryset = DynamicInterviewSession.objects.all()
    serializer_class = DynamicInterviewSessionSerializer

    @action(detail=True, methods=['post'])
    def start_analysis(self, request, pk=None):
        """
        Triggers the analysis of the interview by the AI service.
        """
        session = self.get_object()

        # In a real implementation, this would be an asynchronous task
        # using Celery.
        try:
            # Assuming the AI service is running on localhost:8001
            response = requests.post(
                "http://localhost:8001/analyze-interview/",
                json={"video_path": session.video_url}
            )
            response.raise_for_status()
            analysis_results = response.json()

            # Save the analysis results to the database
            # (This would be done in the Celery task)
            
            return Response(analysis_results)
        except requests.exceptions.RequestException as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def export_csv(self, request):
        """Export CSV report"""
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        sessions = self.get_queryset().filter(status='completed')
        
        if start_date:
            sessions = sessions.filter(created_at__gte=start_date)
        if end_date:
            sessions = sessions.filter(created_at__lte=end_date)
        
        csv_data = InterviewReportGenerator.generate_csv_report(sessions)
        
        response = HttpResponse(csv_data, content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="interview_report_{datetime.now().strftime("%Y%m%d")}.csv"'
        
        return response

    @action(detail=True, methods=['get'])
    def export_pdf(self, request, pk=None):
        """Export PDF report for specific interview"""
        session = self.get_object()
        pdf_data = InterviewReportGenerator.generate_pdf_report(session)
        
        response = HttpResponse(pdf_data, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="interview_{session.session_id}.pdf"'
        
        return response

class AnalyticsViewSet(viewsets.ViewSet):
    """
    API endpoints for interview analytics
    """
    
    @action(detail=False, methods=['get'])
    def dashboard(self, request):
        """Get comprehensive analytics dashboard data"""
        days = int(request.query_params.get('days', 30))
        
        return Response({
            'metrics': InterviewAnalytics.get_dashboard_metrics(days),
            'trends': InterviewAnalytics.get_trend_data(days),
            'flags': InterviewAnalytics.get_flag_breakdown(),
            'deception': InterviewAnalytics.get_deception_analysis(),
            'quality': InterviewAnalytics.get_interview_quality_metrics()
        })

    @action(detail=True, methods=['get'])
    def interview_details(self, request, pk=None):
        """Get detailed analytics for specific interview"""
        # Note: pk here is expected to be session_id based on original code, 
        # but ViewSet usually uses pk as ID. Let's assume pk is session_id for now 
        # or we can look it up by ID if pk is int.
        # Given the original code used session_id string, let's try to support that.
        
        try:
            session = DynamicInterviewSession.objects.get(session_id=pk)
        except DynamicInterviewSession.DoesNotExist:
             try:
                 session = DynamicInterviewSession.objects.get(pk=pk)
             except DynamicInterviewSession.DoesNotExist:
                 return Response({'error': 'Session not found'}, status=status.HTTP_404_NOT_FOUND)

        exchanges = session.exchanges.all()
        
        return Response({
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
