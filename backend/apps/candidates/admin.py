from django.contrib import admin

from .models import Candidate, CandidateEnrollment


@admin.register(Candidate)
class CandidateAdmin(admin.ModelAdmin):
    list_display = ("id", "email", "first_name", "last_name", "preferred_channel", "created_at")
    list_filter = ("preferred_channel", "created_at")
    search_fields = ("email", "first_name", "last_name")


@admin.register(CandidateEnrollment)
class CandidateEnrollmentAdmin(admin.ModelAdmin):
    list_display = ("id", "campaign", "candidate", "status", "invited_at", "completed_at")
    list_filter = ("status", "created_at")
    search_fields = ("campaign__name", "candidate__email")
