from django.contrib import admin
from django_tenants.admin import TenantAdminMixin
from apps.tenants.models import Organization


@admin.register(Organization)
class OrganizationAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display = ("name", "code", "schema_name", "is_active", "tier")