from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import BackgroundCheckViewSet, ProviderWebhookAPIView

app_name = "background_checks"

router = DefaultRouter()
router.register(r"checks", BackgroundCheckViewSet, basename="background-check")

urlpatterns = [
    path("", include(router.urls)),
    path("providers/<str:provider_key>/webhook/", ProviderWebhookAPIView.as_view(), name="provider-webhook"),
]
