from django.contrib import admin

from .models import Invitation


@admin.register(Invitation)
class InvitationAdmin(admin.ModelAdmin):
    list_display = ("id", "enrollment", "channel", "status", "send_to", "expires_at", "sent_at")
    list_filter = ("channel", "status", "created_at")
    search_fields = ("send_to", "enrollment__candidate__email", "enrollment__campaign__name")
