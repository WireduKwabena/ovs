from typing import Any

from rest_framework import serializers

from .models import InterviewFeedback, InterviewQuestion, InterviewResponse, InterviewSession, VideoAnalysis


class InterviewQuestionSerializer(serializers.ModelSerializer):
    question_type_display = serializers.CharField(source="get_question_type_display", read_only=True)
    difficulty_display = serializers.CharField(source="get_difficulty_display", read_only=True)

    class Meta:
        model = InterviewQuestion
        fields = [
            "id",
            "question_text",
            "question_type",
            "question_type_display",
            "difficulty",
            "difficulty_display",
            "targets_flag_type",
            "evaluation_rubric",
            "expected_keywords",
            "times_used",
            "average_response_quality",
            "is_active",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "times_used", "average_response_quality", "created_at", "updated_at"]


class VideoAnalysisSerializer(serializers.ModelSerializer):
    class Meta:
        model = VideoAnalysis
        fields = [
            "id",
            "response",
            "face_detected",
            "face_detection_confidence",
            "eye_contact_percentage",
            "gaze_direction_changes",
            "dominant_emotion",
            "emotion_distribution",
            "confidence_level",
            "stress_level",
            "head_movement_count",
            "fidgeting_detected",
            "behavioral_indicators",
            "raw_analysis_data",
            "frames_analyzed",
            "analysis_duration_seconds",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class InterviewResponseSerializer(serializers.ModelSerializer):
    question_text = serializers.CharField(source="question.question_text", read_only=True)
    video_analysis = VideoAnalysisSerializer(read_only=True)

    class Meta:
        model = InterviewResponse
        fields = [
            "id",
            "session",
            "question",
            "question_text",
            "target_flag",
            "sequence_number",
            "video_file",
            "video_url",
            "audio_file",
            "transcript",
            "transcript_confidence",
            "sentiment",
            "sentiment_score",
            "response_quality_score",
            "relevance_score",
            "completeness_score",
            "coherence_score",
            "llm_evaluation",
            "key_points_extracted",
            "concerns_detected",
            "response_duration_seconds",
            "answered_at",
            "processed_at",
            "video_analysis",
        ]
        read_only_fields = [
            "id",
            "question_text",
            "transcript_confidence",
            "sentiment_score",
            "response_quality_score",
            "relevance_score",
            "completeness_score",
            "coherence_score",
            "processed_at",
            "video_analysis",
        ]


class InterviewSessionSerializer(serializers.ModelSerializer):
    case_id = serializers.CharField(source="case.case_id", read_only=True)
    responses = InterviewResponseSerializer(many=True, read_only=True)
    interrogation_flags = serializers.SerializerMethodField()

    def get_interrogation_flags(self, obj) -> list[dict[str, Any]]:
        return list(
            obj.case.interrogation_flags.values(
                "id",
                "description",
                "severity",
                "status",
            )
        )

    class Meta:
        model = InterviewSession
        fields = [
            "id",
            "session_id",
            "case",
            "case_id",
            "status",
            "use_dynamic_questions",
            "max_questions",
            "current_question_number",
            "total_questions_asked",
            "overall_score",
            "communication_score",
            "consistency_score",
            "confidence_score",
            "interview_summary",
            "key_findings",
            "red_flags_detected",
            "flags_addressed",
            "flags_resolved_count",
            "flags_unresolved_count",
            "conversation_history",
            "interrogation_flags",
            "created_at",
            "started_at",
            "completed_at",
            "duration_seconds",
            "responses",
        ]
        read_only_fields = [
            "id",
            "session_id",
            "current_question_number",
            "total_questions_asked",
            "overall_score",
            "communication_score",
            "consistency_score",
            "confidence_score",
            "flags_resolved_count",
            "flags_unresolved_count",
            "interrogation_flags",
            "created_at",
            "started_at",
            "completed_at",
            "duration_seconds",
            "responses",
        ]


class InterviewFeedbackSerializer(serializers.ModelSerializer):
    class Meta:
        model = InterviewFeedback
        fields = [
            "id",
            "session",
            "reviewer",
            "rating",
            "communication_rating",
            "clarity_rating",
            "consistency_rating",
            "strengths",
            "weaknesses",
            "general_comments",
            "recommendation",
            "decision_rationale",
            "agrees_with_ai",
            "ai_override_reason",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class InterviewActionErrorSerializer(serializers.Serializer):
    error = serializers.CharField()


class InterviewPlaybackResponseSerializer(serializers.Serializer):
    session = serializers.DictField()
    timeline = serializers.ListField(child=serializers.DictField())
    highlights = serializers.ListField(child=serializers.DictField())
    flags = serializers.ListField(child=serializers.DictField())


class InterviewAnalyticsDashboardQuerySerializer(serializers.Serializer):
    days = serializers.IntegerField(required=False, default=30, min_value=1, max_value=365)


class InterviewAnalyticsDashboardResponseSerializer(serializers.Serializer):
    metrics = serializers.DictField()
    trends = serializers.DictField()
    flags = serializers.ListField(child=serializers.DictField())
    behavioral = serializers.DictField()
    quality = serializers.DictField()


class InterviewCompareRequestSerializer(serializers.Serializer):
    session_ids = serializers.ListField(child=serializers.CharField(), allow_empty=False)


class InterviewCompareResponseSerializer(serializers.Serializer):
    sessions = serializers.ListField(child=serializers.DictField())
    recommendation = serializers.DictField()


class InterviewGenerateFlagsRequestSerializer(serializers.Serializer):
    case = serializers.CharField()
    persist = serializers.BooleanField(required=False, default=False)
    replace_pending = serializers.BooleanField(required=False, default=False)


class InterviewGenerateFlagsResponseSerializer(serializers.Serializer):
    case_id = serializers.CharField()
    generated_count = serializers.IntegerField()
    created_count = serializers.IntegerField()
    created_flag_ids = serializers.ListField(child=serializers.IntegerField())
    flags = serializers.ListField(child=serializers.DictField())
