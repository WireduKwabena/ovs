# backend/apps/ml_monitoring/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'ml_monitoring'

router = DefaultRouter()
router.register(r'metrics', views.MLModelMetricsViewSet, basename='ml-metrics')

urlpatterns = [
    path('', include(router.urls)),
]