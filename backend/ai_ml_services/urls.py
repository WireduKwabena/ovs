"""URL routes for ai_ml_services operational endpoints."""

from django.urls import path

from ai_ml_services.views import monitor_health_view

app_name = "ai_ml_services"

urlpatterns = [
    path("health/", monitor_health_view, name="monitor-health"),
]
