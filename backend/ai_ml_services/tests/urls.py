"""Isolated URLConf for ai_ml_services endpoint tests."""

from django.urls import include, path

urlpatterns = [
    path("api/ai-monitor/", include("ai_ml_services.urls")),
    path("api/v1/ai-monitor/", include("ai_ml_services.urls")),
]
