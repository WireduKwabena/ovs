# backend/apps/interviews/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import InterviewViewSet, AnalyticsViewSet

router = DefaultRouter()
router.register(r'sessions', InterviewViewSet, basename='interview')
router.register(r'analytics', AnalyticsViewSet, basename='analytics')

urlpatterns = [
    path('', include(router.urls)),
]
