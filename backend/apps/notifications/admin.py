from django.contrib import admin

from .models import AlertRule, Notification, NotificationTemplate


@admin.register(NotificationTemplate)
class NotificationTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "template_type", "category", "is_active", "updated_at")
    list_filter = ("template_type", "category", "is_active", "updated_at")
    search_fields = ("name", "subject", "body")
    readonly_fields = ("created_at", "updated_at")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "recipient",
        "notification_type",
        "subject",
        "status",
        "priority",
        "sent_at",
        "created_at",
    )
    list_filter = ("notification_type", "status", "priority", "created_at")
    search_fields = (
        "recipient__email",
        "subject",
        "message",
        "related_case__case_id",
        "related_interview__session_id",
    )
    readonly_fields = ("created_at", "sent_at", "read_at", "failed_at")
    list_select_related = ("recipient", "template", "related_case", "related_interview")


@admin.register(AlertRule)
class AlertRuleAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "trigger_type",
        "priority",
        "threshold_value",
        "is_active",
        "times_triggered",
        "last_triggered_at",
    )
    list_filter = ("trigger_type", "priority", "is_active", "updated_at")
    search_fields = ("name", "description")
    readonly_fields = ("times_triggered", "last_triggered_at", "created_at", "updated_at")
    filter_horizontal = ("notify_users",)
    list_select_related = ("notification_template",)
