from django.contrib import admin

from .models import PersonnelRecord


@admin.register(PersonnelRecord)
class PersonnelRecordAdmin(admin.ModelAdmin):
    list_display = (
        "full_name",
        "nationality",
        "is_active_officeholder",
        "is_public",
        "updated_at",
    )
    list_filter = ("nationality", "is_active_officeholder", "is_public")
    search_fields = ("full_name", "contact_email", "contact_phone")
    autocomplete_fields = ("linked_candidate",)
