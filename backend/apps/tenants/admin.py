from django.contrib import admin
from apps.tenants.models import Organization


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "schema_name", "is_active", "tier")