"""
URL configuration for backend project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
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

# Versioned URL patterns shared between /api/ (legacy) and /api/v1/ (current).
# New clients should target /api/v1/. Legacy /api/ routes are kept for
# backward compatibility during the migration window.
_v1_urlpatterns = [
    path("system/", include("apps.core.urls")),
    path("auth/", include("apps.authentication.urls")),
    path("users/", include("apps.users.urls")),
    path("public/transparency/", include("apps.appointments.public_urls")),
    path("admin/", include("apps.admin_dashboard.urls")),
    path("campaigns/", include("apps.campaigns.urls")),
    path("positions/", include("apps.positions.urls")),
    path("personnel/", include("apps.personnel.urls")),
    path("appointments/", include("apps.appointments.urls")),
    path("applications/", include("apps.applications.urls")),
    path("interviews/", include("apps.interviews.urls")),
    path("video-calls/", include("apps.video_calls.urls")),
    path("rubrics/", include("apps.rubrics.urls")),
    path("notifications/", include("apps.notifications.urls")),
    path("audit/", include("apps.audit.urls")),
    path("fraud/", include("apps.fraud.urls")),
    path("billing/", include("apps.billing.urls")),
    path("governance/", include("apps.governance.urls")),
    path("government/", include("apps.core.government_alias_urls")),
    path("background-checks/", include("apps.background_checks.urls")),
    path("ml-monitoring/", include("apps.ml_monitoring.urls")),
    path("ai-monitor/", include("ai_ml_services.urls")),
    path("", include("apps.candidates.urls")),
    path("invitations/", include("apps.invitations.urls")),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    # Versioned API (preferred for new integrations)
    path("api/v1/", include(_v1_urlpatterns)),
    # Legacy unversioned API (backward compatibility — do not add new endpoints here)
    path("api/system/", include("apps.core.urls")),
    path("api/auth/", include("apps.authentication.urls")),
    path("api/users/", include("apps.users.urls")),
    path("api/public/transparency/", include("apps.appointments.public_urls")),
    path("api/admin/", include("apps.admin_dashboard.urls")),
    path("api/campaigns/", include("apps.campaigns.urls")),
    path("api/positions/", include("apps.positions.urls")),
    path("api/personnel/", include("apps.personnel.urls")),
    path("api/appointments/", include("apps.appointments.urls")),
    path("api/applications/", include("apps.applications.urls")),
    path("api/interviews/", include("apps.interviews.urls")),
    path("api/video-calls/", include("apps.video_calls.urls")),
    path("api/rubrics/", include("apps.rubrics.urls")),
    path("api/notifications/", include("apps.notifications.urls")),
    path("api/audit/", include("apps.audit.urls")),
    path("api/fraud/", include("apps.fraud.urls")),
    path("api/billing/", include("apps.billing.urls")),
    path("api/governance/", include("apps.governance.urls")),
    path("api/government/", include("apps.core.government_alias_urls")),
    path("api/background-checks/", include("apps.background_checks.urls")),
    path("api/ml-monitoring/", include("apps.ml_monitoring.urls")),
    path("api/ai-monitor/", include("ai_ml_services.urls")),
    path("api/", include("apps.candidates.urls")),
    path("api/invitations/", include("apps.invitations.urls")),
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


