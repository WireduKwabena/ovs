# backend/apps/audit/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'audit'

router = DefaultRouter()
router.register(r'logs', views.AuditLogViewSet, basename='audit-log')

urlpatterns = [
    path(
        'logs/by-entity/',
        views.AuditLogViewSet.as_view({'get': 'by_entity'}),
        name='audit-log-by-entity-hyphen',
    ),
    path(
        'logs/by_entity/',
        views.AuditLogViewSet.as_view({'get': 'by_entity'}),
        name='audit-log-by-entity-legacy',
    ),
    path(
        'logs/by-user/',
        views.AuditLogViewSet.as_view({'get': 'by_user'}),
        name='audit-log-by-user-hyphen',
    ),
    path(
        'logs/by_user/',
        views.AuditLogViewSet.as_view({'get': 'by_user'}),
        name='audit-log-by-user-legacy',
    ),
    path(
        'logs/recent-activity/',
        views.AuditLogViewSet.as_view({'get': 'recent_activity'}),
        name='audit-log-recent-activity-hyphen',
    ),
    path(
        'logs/recent_activity/',
        views.AuditLogViewSet.as_view({'get': 'recent_activity'}),
        name='audit-log-recent-activity-legacy',
    ),
    path(
        'logs/event-catalog/',
        views.AuditLogViewSet.as_view({'get': 'event_catalog'}),
        name='audit-log-event-catalog-hyphen',
    ),
    path(
        'logs/event_catalog/',
        views.AuditLogViewSet.as_view({'get': 'event_catalog'}),
        name='audit-log-event-catalog-legacy',
    ),
    path('', include(router.urls)),
]

