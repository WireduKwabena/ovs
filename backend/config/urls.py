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

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("apps.authentication.urls")),
    path("api/admin/", include("apps.admin_dashboard.urls")),
    path("api/campaigns/", include("apps.campaigns.urls")),
    path("api/applications/", include("apps.applications.urls")),
    path("api/interviews/", include("apps.interviews.urls")),
    path("api/rubrics/", include("apps.rubrics.urls")),
    path("api/notifications/", include("apps.notifications.urls")),
    path("api/audit/", include("apps.audit.urls")),
    path("api/fraud/", include("apps.fraud.urls")),
    path("api/billing/", include("apps.billing.urls")),
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
