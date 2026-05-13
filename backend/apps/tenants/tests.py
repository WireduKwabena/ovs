from types import SimpleNamespace
from unittest.mock import ANY, patch

from django.test import RequestFactory, SimpleTestCase

from apps.tenants.middleware import TenantMiddleware


class TenantMiddlewareRoutingTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = TenantMiddleware(lambda request: None)

    def test_routes_by_active_organization_id_when_slug_is_missing(self):
        request = self.factory.get(
            "/api/auth/profile/?active_organization_id=org-2",
            HTTP_X_ACTIVE_ORGANIZATION_ID="org-2",
        )
        organization = SimpleNamespace(id="org-2", code="org-two", schema_name="org_two")

        with patch.object(
            self.middleware,
            "_resolve_organization_from_slug",
            return_value=None,
        ) as resolve_from_slug, patch.object(
            self.middleware,
            "_resolve_organization_from_id",
            return_value=organization,
        ) as resolve_from_org_id, patch.object(
            self.middleware,
            "_attach_organization",
        ) as attach_org:
            self.middleware.process_request(request)

        resolve_from_slug.assert_called_once_with(ANY, None)
        resolve_from_org_id.assert_called_once_with(ANY, "org-2")
        attach_org.assert_called_once_with(request, organization)

    def test_slug_header_takes_precedence_over_active_organization_id(self):
        request = self.factory.get(
            "/api/auth/profile/?active_organization_id=org-2",
            HTTP_X_ORGANIZATION_SLUG="org-one",
            HTTP_X_ACTIVE_ORGANIZATION_ID="org-2",
        )
        organization = SimpleNamespace(id="org-1", code="org-one", schema_name="org_one")

        with patch.object(
            self.middleware,
            "_resolve_organization_from_slug",
            return_value=organization,
        ) as resolve_from_slug, patch.object(
            self.middleware,
            "_resolve_organization_from_id",
        ) as resolve_from_org_id, patch.object(
            self.middleware,
            "_attach_organization",
        ) as attach_org:
            self.middleware.process_request(request)

        resolve_from_slug.assert_called_once_with(ANY, "org-one")
        resolve_from_org_id.assert_not_called()
        attach_org.assert_called_once_with(request, organization)
