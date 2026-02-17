# backend/apps/notifications/urls.py

from django.urls import path
from .views import NotificationViewSet

app_name = 'notifications'

urlpatterns = [
    path('', NotificationViewSet.as_view({'get': 'list'}), name='notification-list'),
    path('<int:pk>/', NotificationViewSet.as_view({'get': 'retrieve'}), name='notification-detail'),
    path('<int:pk>/mark_read/', NotificationViewSet.as_view({'post': 'mark_read'}), name='notification-mark-read'),
    path('<int:pk>/archive/', NotificationViewSet.as_view({'delete': 'archive'}), name='notification-archive'),
    path('mark-as-read/', NotificationViewSet.as_view({'post': 'mark_as_read'}), name='notification-mark-as-read'),
    path('mark-all-as-read/', NotificationViewSet.as_view({'post': 'mark_all_as_read'}), name='notification-mark-all-as-read'),
    path('unread-count/', NotificationViewSet.as_view({'get': 'unread_count'}), name='notification-unread-count'),
]
