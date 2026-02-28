"""URL routes for ai_ml_services operational endpoints."""

from django.urls import path

from ai_ml_services.views import (
    document_classification_view,
    monitor_health_view,
    social_profile_check_view,
)

app_name = "ai_ml_services"

urlpatterns = [
    path("health/", monitor_health_view, name="monitor-health"),
    path("classify-document/", document_classification_view, name="classify-document"),
    path("check-social-profiles/", social_profile_check_view, name="check-social-profiles"),
]
