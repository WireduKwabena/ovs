# backend/apps/admin_dashboard/urls.py

from django.urls import path
from . import views

app_name = 'admin_dashboard'

urlpatterns = [
    path('dashboard/', views.admin_dashboard, name='dashboard'),
    path('analytics/', views.admin_analytics, name='analytics'),
    path('cases/', views.admin_cases, name='cases'),
]