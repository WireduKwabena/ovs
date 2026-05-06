# backend/apps/admin_dashboard/urls.py

from django.urls import path
from . import views

app_name = 'admin_dashboard'

urlpatterns = [
    path('dashboard/', views.admin_dashboard, name='dashboard'),
    path('analytics/', views.admin_analytics, name='analytics'),
    path('cases/', views.admin_cases, name='cases'),
    path('users/', views.admin_users, name='users'),
    path('users/<uuid:user_id>/', views.admin_user_update, name='user-update'),
    path('issues/report/', views.report_platform_issue, name='issues-report'),
    path('issues/', views.list_platform_issues, name='issues-list'),
    path('issues/<uuid:issue_id>/', views.update_platform_issue, name='issues-update'),
]
