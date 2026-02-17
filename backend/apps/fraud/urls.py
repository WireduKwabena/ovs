# backend/apps/fraud/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'fraud'

router = DefaultRouter()
router.register(r'results', views.FraudDetectionResultViewSet, basename='fraud-result')
router.register(r'consistency', views.ConsistencyCheckResultViewSet, basename='consistency-result')

urlpatterns = [
    path('', include(router.urls)),
]


