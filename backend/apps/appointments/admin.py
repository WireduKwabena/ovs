from django.contrib import admin

from .models import AppointmentRecord, AppointmentStageAction, ApprovalStage, ApprovalStageTemplate


class ApprovalStageInline(admin.TabularInline):
    model = ApprovalStage
    extra = 1


@admin.register(ApprovalStage)
class ApprovalStageAdmin(admin.ModelAdmin):
    list_display = ("template", "order", "name", "required_role", "maps_to_status", "is_required")
    list_filter = ("required_role", "maps_to_status", "is_required")
    search_fields = ("name", "template__name", "required_role")
    autocomplete_fields = ("template",)


@admin.register(ApprovalStageTemplate)
class ApprovalStageTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "exercise_type", "created_by", "created_at")
    list_filter = ("exercise_type",)
    search_fields = ("name", "exercise_type")
    autocomplete_fields = ("created_by",)
    inlines = [ApprovalStageInline]


@admin.register(AppointmentRecord)
class AppointmentRecordAdmin(admin.ModelAdmin):
    list_display = (
        "position",
        "nominee",
        "status",
        "nomination_date",
        "appointment_date",
        "is_public",
        "updated_at",
    )
    list_filter = ("status", "is_public")
    search_fields = ("position__title", "nominee__full_name", "nominated_by_display", "gazette_number")
    autocomplete_fields = (
        "position",
        "nominee",
        "appointment_exercise",
        "nominated_by_user",
        "vetting_case",
        "final_decision_by_user",
    )


@admin.register(AppointmentStageAction)
class AppointmentStageActionAdmin(admin.ModelAdmin):
    list_display = ("appointment", "action", "actor", "previous_status", "new_status", "acted_at")
    list_filter = ("action", "new_status", "actor_role")
    search_fields = ("appointment__id", "actor__email", "reason_note")
    autocomplete_fields = ("appointment", "stage", "actor")
