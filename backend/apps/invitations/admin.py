from django.contrib import admin

from .models import CandidateAccessPass, CandidateAccessSession, Invitation


@admin.register(Invitation)
class InvitationAdmin(admin.ModelAdmin):
    list_display = ("id", "enrollment", "channel", "status", "send_to", "expires_at", "sent_at")
    list_filter = ("channel", "status", "created_at")
    search_fields = ("send_to", "enrollment__candidate__email", "enrollment__campaign__name")


@admin.register(CandidateAccessPass)
class CandidateAccessPassAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "enrollment",
        "pass_type",
        "status",
        "use_count",
        "max_uses",
        "expires_at",
        "created_at",
    )
    list_filter = ("pass_type", "status", "created_at")
    search_fields = ("enrollment__candidate__email", "enrollment__campaign__name", "token_hint")


@admin.register(CandidateAccessSession)
class CandidateAccessSessionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "session_key",
        "enrollment",
        "status",
        "issued_at",
        "expires_at",
        "last_seen_at",
    )
    list_filter = ("status", "issued_at")
    search_fields = ("enrollment__candidate__email", "enrollment__campaign__name", "session_key")
