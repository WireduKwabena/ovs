from django.contrib import admin

from .models import InterviewFeedback, InterviewQuestion, InterviewResponse, InterviewSession, VideoAnalysis


@admin.register(InterviewSession)
class InterviewSessionAdmin(admin.ModelAdmin):
    list_display = (
        "session_id",
        "case",
        "status",
        "overall_score",
        "total_questions_asked",
        "created_at",
    )
    list_filter = ("status", "created_at")
    search_fields = ("session_id", "case__case_id", "case__applicant__email")


@admin.register(InterviewQuestion)
class InterviewQuestionAdmin(admin.ModelAdmin):
    list_display = ("id", "question_type", "difficulty", "is_active", "times_used")
    list_filter = ("question_type", "difficulty", "is_active")
    search_fields = ("question_text",)


@admin.register(InterviewResponse)
class InterviewResponseAdmin(admin.ModelAdmin):
    list_display = ("id", "session", "sequence_number", "sentiment", "response_quality_score", "answered_at")
    list_filter = ("sentiment", "answered_at")
    search_fields = ("session__session_id", "question__question_text", "transcript")


@admin.register(VideoAnalysis)
class VideoAnalysisAdmin(admin.ModelAdmin):
    list_display = ("id", "response", "face_detected", "confidence_level", "stress_level", "created_at")
    list_filter = ("face_detected", "fidgeting_detected", "created_at")
    search_fields = ("response__session__session_id",)


@admin.register(InterviewFeedback)
class InterviewFeedbackAdmin(admin.ModelAdmin):
    list_display = ("id", "session", "reviewer", "rating", "recommendation", "created_at")
    list_filter = ("recommendation", "rating", "created_at")
    search_fields = ("session__session_id", "reviewer__email")
