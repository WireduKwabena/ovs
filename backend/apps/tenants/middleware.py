from django_tenants.middleware.main import TenantMainMiddleware
from django.db import connection


class TenantMiddleware(TenantMainMiddleware):
    '''
    Extended tenant middleware that supports both subdomain routing and
    X-Institution-Slug header routing (for mobile clients and local dev).

    Resolution order:
      1. Subdomain (vvu.iconnect.app) — via TenantMainMiddleware
      2. X-Institution-Slug header — for mobile / direct API calls
      3. Public schema fallback — unauthenticated/admin endpoints
    '''

    def process_request(self, request):
        # Try subdomain resolution first
        try:
            super().process_request(request)
            return  # Subdomain resolved — done
        except self.TENANT_NOT_FOUND_EXCEPTION:
            pass  # No domain record — try header fallback

        # Try X-Institution-Slug header
        slug = request.headers.get('X-Institution-Slug')
        if slug:
            from apps.tenants.models import Client
            try:
                institution = Client.objects.get(slug=slug, is_active=True)
                request.tenant = institution
                connection.set_tenant(institution)
                return
            except Client.DoesNotExist:
                pass

        # Fall back to public schema (for /admin/, /api/health/, etc.)
        from django_tenants.utils import get_public_schema_name
        from apps.tenants.models import Client
        try:
            public = Client.objects.get(schema_name=get_public_schema_name())
            request.tenant = public
            connection.set_tenant(public)
        except Client.DoesNotExist:
            # No public tenant row yet (first migration) — set schema directly
            connection.set_schema_to_public()


class TenantHeaderFallbackMiddleware:
    '''Kept for backwards compatibility — logic is now in TenantMiddleware.'''

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

