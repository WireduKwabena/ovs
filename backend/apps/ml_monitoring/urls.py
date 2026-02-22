from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import MLModelMetricsViewSet

app_name = "ml_monitoring"

# Primary routes expected by the current project/tests:
# /api/ml-monitoring/
# /api/ml-monitoring/{id}/
# /api/ml-monitoring/latest/
router = DefaultRouter()
router.register(r"", MLModelMetricsViewSet, basename="ml-metrics")

# Backward-compatible legacy path:
# /api/ml-monitoring/metrics/
legacy_router = DefaultRouter()
legacy_router.register(r"", MLModelMetricsViewSet, basename="ml-metrics-legacy")

urlpatterns = [
    path("metrics/", include(legacy_router.urls)),
    path("", include(router.urls)),
]
