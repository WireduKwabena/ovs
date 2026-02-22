# backend/apps/audit/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'audit'

router = DefaultRouter()
router.register(r'logs', views.AuditLogViewSet, basename='audit-log')

urlpatterns = [
    path('', include(router.urls)),
]