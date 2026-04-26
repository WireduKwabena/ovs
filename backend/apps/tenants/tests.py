from types import SimpleNamespace
from unittest.mock import patch

from django.test import RequestFactory, SimpleTestCase

from apps.tenants.middleware import TenantMiddleware


class TenantMiddlewareRoutingTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = TenantMiddleware(lambda request: None)
        self.middleware.TENANT_NOT_FOUND_EXCEPTION = Exception

    def test_routes_by_active_organization_id_when_slug_is_missing(self):
        request = self.factory.get(
            "/api/auth/profile/?active_organization_id=org-2",
            HTTP_X_ACTIVE_ORGANIZATION_ID="org-2",
        )
        organization = SimpleNamespace(schema_name="org_two")
        organization_model = object()

        with patch(
            "django_tenants.middleware.main.TenantMainMiddleware.process_request",
            side_effect=Exception("tenant not found"),
        ), patch(
            "django_tenants.utils.get_tenant_model",
            return_value=organization_model,
        ), patch(
            "django_tenants.utils.get_public_schema_name",
            return_value="public",
        ), patch.object(
            self.middleware,
            "_resolve_tenant_from_slug",
            return_value=None,
        ) as resolve_from_slug, patch.object(
            self.middleware,
            "_resolve_tenant_from_organization_id",
            return_value=organization,
        ) as resolve_from_org_id, patch.object(
            self.middleware,
            "_activate_tenant",
        ) as activate_tenant:
            self.middleware.process_request(request)

        resolve_from_slug.assert_called_once_with(organization_model, None)
        resolve_from_org_id.assert_called_once_with(organization_model, "org-2")
        activate_tenant.assert_called_once_with(request, organization)

    def test_slug_header_takes_precedence_over_active_organization_id(self):
        request = self.factory.get(
            "/api/auth/profile/?active_organization_id=org-2",
            HTTP_X_ORGANIZATION_SLUG="org-one",
            HTTP_X_ACTIVE_ORGANIZATION_ID="org-2",
        )
        organization = SimpleNamespace(schema_name="org_one")
        organization_model = object()

        with patch(
            "django_tenants.middleware.main.TenantMainMiddleware.process_request",
            side_effect=Exception("tenant not found"),
        ), patch(
            "django_tenants.utils.get_tenant_model",
            return_value=organization_model,
        ), patch(
            "django_tenants.utils.get_public_schema_name",
            return_value="public",
        ), patch.object(
            self.middleware,
            "_resolve_tenant_from_slug",
            return_value=organization,
        ) as resolve_from_slug, patch.object(
            self.middleware,
            "_resolve_tenant_from_organization_id",
        ) as resolve_from_org_id, patch.object(
            self.middleware,
            "_activate_tenant",
        ) as activate_tenant:
            self.middleware.process_request(request)

        resolve_from_slug.assert_called_once_with(organization_model, "org-one")
        resolve_from_org_id.assert_not_called()
        activate_tenant.assert_called_once_with(request, organization)
