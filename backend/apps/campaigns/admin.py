from django.contrib import admin

from .models import CampaignRubricVersion, VettingCampaign


@admin.register(VettingCampaign)
class VettingCampaignAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "status", "initiated_by", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("name", "description", "initiated_by__email")


@admin.register(CampaignRubricVersion)
class CampaignRubricVersionAdmin(admin.ModelAdmin):
    list_display = ("id", "campaign", "version", "name", "is_active", "created_at")
    list_filter = ("is_active", "created_at")
    search_fields = ("campaign__name", "name")
