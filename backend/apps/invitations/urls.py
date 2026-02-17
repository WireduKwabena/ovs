from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import AcceptInvitationAPIView, InvitationViewSet

router = DefaultRouter()
router.register(r"", InvitationViewSet, basename="invitation")

urlpatterns = [
    path("accept/", AcceptInvitationAPIView.as_view(), name="invitation-accept"),
] + router.urls
