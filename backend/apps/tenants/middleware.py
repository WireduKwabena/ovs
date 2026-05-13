from django.urls import set_urlconf
from django.conf import settings


class TenantMiddleware:
    """
    Backward-compatible middleware that resolves an organization context from
    request headers in single-schema mode.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        self.process_request(request)
        return self.get_response(request)

    def _attach_organization(self, request, organization):
        request.tenant = organization
        request.urlconf = settings.ROOT_URLCONF
        set_urlconf(request.urlconf)

    def _resolve_organization_from_slug(self, organization_model, slug):
        normalized_slug = str(slug or "").strip()
        if not normalized_slug:
            return None
        return organization_model.objects.filter(code=normalized_slug, is_active=True).first()

    def _resolve_organization_from_id(self, organization_model, organization_id):
        normalized_id = str(organization_id or "").strip()
        if not normalized_id:
            return None
        return organization_model.objects.filter(id=normalized_id, is_active=True).first()

    def process_request(self, request):
        from apps.tenants.models import Organization

        organization = self._resolve_organization_from_slug(
            Organization,
            request.headers.get("X-Organization-Slug"),
        )
        if organization is None:
            organization = self._resolve_organization_from_id(
                Organization,
                request.headers.get("X-Active-Organization-ID") or request.GET.get("active_organization_id"),
            )
        if organization is not None:
            self._attach_organization(request, organization)
            return

        request.tenant = None
        request.urlconf = settings.ROOT_URLCONF
        set_urlconf(request.urlconf)


class TenantHeaderFallbackMiddleware:
    """Kept for backwards compatibility — logic is now in TenantMiddleware."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

