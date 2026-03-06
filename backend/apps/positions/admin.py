from django.contrib import admin

from .models import GovernmentPosition


@admin.register(GovernmentPosition)
class GovernmentPositionAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "institution",
        "branch",
        "is_vacant",
        "is_public",
        "confirmation_required",
        "updated_at",
    )
    list_filter = ("branch", "is_vacant", "is_public", "confirmation_required")
    search_fields = ("title", "institution", "appointment_authority")
    autocomplete_fields = ("current_holder", "rubric")
