from django.contrib import admin

from .models import BackgroundCheck, BackgroundCheckEvent


@admin.register(BackgroundCheck)
class BackgroundCheckAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "case",
        "check_type",
        "provider_key",
        "status",
        "score",
        "risk_level",
        "recommendation",
        "submitted_at",
        "completed_at",
    )
    list_filter = ("check_type", "provider_key", "status", "risk_level", "recommendation")
    search_fields = ("case__case_id", "case__applicant__email", "external_reference")
    readonly_fields = ("id", "created_at", "updated_at", "submitted_at", "completed_at", "last_polled_at")
    list_select_related = ("case", "submitted_by")


@admin.register(BackgroundCheckEvent)
class BackgroundCheckEventAdmin(admin.ModelAdmin):
    list_display = ("id", "background_check", "event_type", "status_before", "status_after", "created_at")
    list_filter = ("event_type", "status_before", "status_after", "created_at")
    search_fields = ("background_check__case__case_id", "background_check__external_reference")
    readonly_fields = ("id", "created_at")
    list_select_related = ("background_check",)

