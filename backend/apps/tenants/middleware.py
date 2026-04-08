from django_tenants.middleware.main import TenantMainMiddleware
from django.db import connection
from django.urls import set_urlconf, clear_url_caches
from django.conf import settings

class TenantMiddleware(TenantMainMiddleware):
    '''
    Extended tenant middleware that supports both subdomain routing and
    X-Organization-Slug header routing (for mobile clients and local dev).

    Resolution order:
      1. Subdomain (vvu.iconnect.app) — via TenantMainMiddleware
      2. X-Organization-Slug header — for mobile / direct API calls
      3. Public schema fallback — unauthenticated/admin endpoints
    '''

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

        # Try X-Organization-Slug header
        slug = request.headers.get('X-Organization-Slug')
        if slug:
            
            Organization = get_tenant_model()
            # from apps.tenants.models import Organization
            try:
                organization = Organization.objects.get(code=slug, is_active=True)
                request.tenant = organization
                connection.set_tenant(organization)
                request.urlconf = settings.ROOT_URLCONF 
                set_urlconf(request.urlconf) # Explicitly set for the current thread
                clear_url_caches() 
                return
            except Organization.DoesNotExist:
                pass
        # 4. Fallback: If we reach here and no tenant is set, ensure Public URLConf
        if not hasattr(request, 'tenant') or request.tenant.schema_name == get_public_schema_name():
            request.urlconf = settings.PUBLIC_SCHEMA_URLCONF

        # Fall back to public schema (for /admin/, /api/health/, etc.)
        # from django_tenants.utils import get_public_schema_name
        from apps.tenants.models import Organization
        try:
            public = Organization.objects.get(schema_name=get_public_schema_name())
            request.tenant = public
            connection.set_tenant(public)
        except Organization.DoesNotExist:
            # No public tenant row yet (first migration) — set schema directly
            connection.set_schema_to_public()


class TenantHeaderFallbackMiddleware:
    '''Kept for backwards compatibility — logic is now in TenantMiddleware.'''

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

