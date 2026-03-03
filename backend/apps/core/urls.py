from django.urls import path

from .views import SystemHealthAPIView


urlpatterns = [
    path("health/", SystemHealthAPIView.as_view(), name="core-system-health"),
]
