from django_tenants.middleware.main import TenantMainMiddleware
from django.db import connection
from django.urls import set_urlconf, clear_url_caches
from django.conf import settings


class TenantMiddleware(TenantMainMiddleware):
    """
    Extended tenant middleware that supports both subdomain routing and
    request-scoped tenant routing for mobile clients and local dev.

    Resolution order:
      1. Subdomain (vvu.iconnect.app) — via TenantMainMiddleware
      2. X-Organization-Slug header — for mobile / direct API calls
      3. X-Active-Organization-ID header / active_organization_id query param
      4. Public schema fallback — unauthenticated/admin endpoints
    """

    def _activate_tenant(self, request, organization):
        request.tenant = organization
        connection.set_tenant(organization)
        request.urlconf = settings.ROOT_URLCONF
        set_urlconf(request.urlconf)
        clear_url_caches()

    def _resolve_tenant_from_slug(self, organization_model, slug):
        normalized_slug = str(slug or "").strip()
        if not normalized_slug:
            return None
        return organization_model.objects.filter(code=normalized_slug, is_active=True).first()

    def _resolve_tenant_from_organization_id(self, organization_model, organization_id):
        normalized_id = str(organization_id or "").strip()
        if not normalized_id:
            return None
        return organization_model.objects.filter(id=normalized_id, is_active=True).first()

    def process_request(self, request):
        from django_tenants.utils import get_tenant_model, get_public_schema_name

        # Try subdomain resolution first
        try:
            super().process_request(request)
        except self.TENANT_NOT_FOUND_EXCEPTION:
            pass  # No domain record — try header fallback

        # If subdomain resolved to a real (non-public) tenant, we're done.
        # If it fell back to the public schema (e.g. localhost), still try the
        # X-Organization-Slug header so direct API calls can specify a tenant.
        if (
            hasattr(request, 'tenant')
            and request.tenant.schema_name != get_public_schema_name()
        ):
            return

        Organization = get_tenant_model()

        organization = self._resolve_tenant_from_slug(
            Organization,
            request.headers.get("X-Organization-Slug"),
        )
        if organization is None:
            organization = self._resolve_tenant_from_organization_id(
                Organization,
                request.headers.get("X-Active-Organization-ID") or request.GET.get("active_organization_id"),
            )
        if organization is not None:
            self._activate_tenant(request, organization)
            return

        # 4. Fallback: If we reach here and no tenant is set, ensure Public URLConf
        if not hasattr(request, "tenant") or request.tenant.schema_name == get_public_schema_name():
            request.urlconf = settings.PUBLIC_SCHEMA_URLCONF

        # Fall back to public schema (for /admin/, /api/health/, etc.)
        from apps.tenants.models import Organization
        try:
            public = Organization.objects.get(schema_name=get_public_schema_name())
            request.tenant = public
            connection.set_tenant(public)
        except Organization.DoesNotExist:
            # No public tenant row yet (first migration) — set schema directly
            connection.set_schema_to_public()


class TenantHeaderFallbackMiddleware:
    """Kept for backwards compatibility — logic is now in TenantMiddleware."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

