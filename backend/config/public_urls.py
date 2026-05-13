"""
Public-schema URL configuration (PUBLIC_SCHEMA_URLCONF).

Served when the request hostname does not match any tenant domain.
Only endpoints that must be accessible without a tenant context belong here:

  - Django admin           — superuser / system-admin access
  - Org onboarding         — creates new tenants (no tenant exists yet)
  - System-admin login     — admin users authenticate against the public schema
Everything else (user login, profile, campaigns, interviews …) is served by
ROOT_URLCONF (config/urls.py) and requires a matched tenant domain.
"""

from django.contrib import admin
from django.urls import path, include

try:
    from drf_spectacular.views import (
        SpectacularAPIView,
        SpectacularRedocView,
        SpectacularSwaggerView,
    )
except ModuleNotFoundError:  # pragma: no cover - optional in some setups
    SpectacularAPIView = None
    SpectacularSwaggerView = None
    SpectacularRedocView = None

from apps.authentication import views as auth_views
from apps.users import views as users_views

try:
    from rest_framework_simplejwt.views import TokenRefreshView
except Exception:  # pragma: no cover - optional dependency
    TokenRefreshView = None

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _auth(route, view, name):
    return path(route, view, name=name)


urlpatterns = [
    # Django admin site — system superusers only
    path("admin/", admin.site.urls),

    # ------------------------------------------------------------------
    # Versioned public API  /api/v1/
    # ------------------------------------------------------------------

    # Organization bootstrap — creates the tenant + first org-admin account
    path(
        "api/v1/auth/register/organization-admin/",
        auth_views.OrganizationAdminRegisterView.as_view(),
        name="public_register_organization_admin",
    ),

    # User profile — must be reachable from the public schema so that platform
    # admins (who have no tenant context) can fetch/refresh their profile after
    # login or page refresh. The view itself is tenant-safe: it guards all
    # OrganizationMembership queries behind a schema_name == "public" check.
    path("api/v1/auth/profile/", users_views.profile_view, name="public_profile"),
    path("api/auth/profile/", users_views.profile_view),  # legacy unversioned

    # System-admin login flow (always requires 2FA)
    path("api/v1/auth/admin/login/", auth_views.admin_login_view, name="public_admin_login"),
    path("api/v1/auth/admin/login/verify/", auth_views.two_factor_verification_view, name="public_admin_login_verify"),
    path("api/v1/auth/admin/2fa/setup/", auth_views.two_factor_setup_view, name="public_admin_2fa_setup"),
    path("api/v1/auth/admin/2fa/enable/", auth_views.two_factor_enable_view, name="public_admin_2fa_enable"),

    # User 2FA management (accessible to platform admins/superusers with no tenant context)
    path("api/v1/auth/2fa/status/", auth_views.two_factor_status_view, name="public_2fa_status"),
    path("api/v1/auth/2fa/backup-codes/regenerate/", auth_views.two_factor_backup_codes_regenerate_view, name="public_2fa_backup_codes_regenerate"),

    # AI monitor endpoints must be reachable from the public schema for
    # platform superusers and external callback integrations.
    path("api/v1/ai-monitor/", include("ai_ml_services.urls")),
    path("api/v1/audit/", include("apps.audit.urls")),
    path("api/v1/governance/", include("apps.governance.urls")),
    path("api/v1/video-calls/", include("apps.video_calls.urls")),

    # Token refresh — must be reachable from the public schema so that platform
    # admins (who have no org slug and thus no tenant context) can restore their
    # session after a page refresh. JWT tokens are schema-agnostic; the blacklist
    # tables live in SHARED_APPS (public schema) and are always accessible here.
    *([path(
        "api/v1/auth/token/refresh/",
        TokenRefreshView.as_view(),
        name="public_token_refresh",
    )] if TokenRefreshView else []),

    # ------------------------------------------------------------------
    # Legacy unversioned routes — kept for backward compatibility only
    # Do NOT add new endpoints here; use /api/v1/ above.
    # ------------------------------------------------------------------
    path("api/auth/register/organization-admin/", auth_views.OrganizationAdminRegisterView.as_view()),
    path("api/auth/admin/login/", auth_views.admin_login_view),
    path("api/auth/admin/login/verify/", auth_views.two_factor_verification_view),
    path("api/auth/admin/2fa/setup/", auth_views.two_factor_setup_view),
    path("api/auth/admin/2fa/enable/", auth_views.two_factor_enable_view),
]

if SpectacularAPIView and SpectacularSwaggerView and SpectacularRedocView:
    urlpatterns += [
        path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
        path(
            "api/schema/swagger-ui/",
            SpectacularSwaggerView.as_view(url_name="schema"),
            name="swagger-ui",
        ),
        path(
            "api/schema/redoc/",
            SpectacularRedocView.as_view(url_name="schema"),
            name="redoc",
        ),
    ]
