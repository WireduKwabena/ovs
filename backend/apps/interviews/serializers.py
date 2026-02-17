from rest_framework import serializers
from .models import DynamicInterviewSession, InterviewExchange, InterrogationFlag, NonVerbalAnalysis

class NonVerbalAnalysisSerializer(serializers.ModelSerializer):
    class Meta:
        model = NonVerbalAnalysis
        fields = '__all__'

class InterrogationFlagSerializer(serializers.ModelSerializer):
    class Meta:
        model = InterrogationFlag
        fields = '__all__'

class InterviewExchangeSerializer(serializers.ModelSerializer):
    nonverbal_analysis = NonVerbalAnalysisSerializer(read_only=True)

    class Meta:
        model = InterviewExchange
        fields = '__all__'

class DynamicInterviewSessionSerializer(serializers.ModelSerializer):
    exchanges = InterviewExchangeSerializer(many=True, read_only=True)
    interrogation_flags = InterrogationFlagSerializer(many=True, read_only=True)
    applicant_full_name = serializers.CharField(source='applicant.full_name', read_only=True)
    interviewer_username = serializers.CharField(source='interviewer.username', read_only=True)

    class Meta:
        model = DynamicInterviewSession
        fields = '__all__'
        read_only_fields = ('session_id', 'started_at', 'completed_at', 'duration_seconds', 'overall_score', 'confidence_score', 'consistency_score', 'completeness_score', 'recommendations', 'interview_summary', 'red_flags', 'current_question_number', 'conversation_history')
