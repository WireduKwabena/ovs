from django.contrib import admin

from .models import Candidate, CandidateEnrollment, CandidateSocialProfile


@admin.register(Candidate)
class CandidateAdmin(admin.ModelAdmin):
    list_display = ("id", "email", "first_name", "last_name", "preferred_channel", "created_at")
    list_filter = ("preferred_channel", "created_at")
    search_fields = ("email", "first_name", "last_name")


@admin.register(CandidateSocialProfile)
class CandidateSocialProfileAdmin(admin.ModelAdmin):
    list_display = ("id", "candidate", "platform", "username", "is_primary", "created_at")
    list_filter = ("platform", "is_primary", "created_at")
    search_fields = ("candidate__email", "username", "url")
    list_select_related = ("candidate",)


@admin.register(CandidateEnrollment)
class CandidateEnrollmentAdmin(admin.ModelAdmin):
    list_display = ("id", "campaign", "candidate", "status", "invited_at", "completed_at")
    list_filter = ("status", "created_at")
    search_fields = ("campaign__name", "candidate__email")
