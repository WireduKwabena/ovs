from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "action",
        "entity_type",
        "entity_id",
        "user",
        "admin_user",
        "ip_address",
        "created_at",
    )
    list_filter = ("action", "entity_type", "created_at")
    search_fields = (
        "entity_type",
        "entity_id",
        "user__email",
        "admin_user__email",
        "ip_address",
    )
    readonly_fields = ("id", "created_at", "changes", "user_agent")
    list_select_related = ("user", "admin_user")
