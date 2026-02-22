from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    AcceptInvitationAPIView,
    CandidateAccessConsumeAPIView,
    CandidateAccessContextAPIView,
    CandidateAccessLogoutAPIView,
    CandidateAccessResultsAPIView,
    InvitationViewSet,
)

router = DefaultRouter()
router.register(r"", InvitationViewSet, basename="invitation")

urlpatterns = [
    path("accept/", AcceptInvitationAPIView.as_view(), name="invitation-accept"),
    path("access/consume/", CandidateAccessConsumeAPIView.as_view(), name="candidate-access-consume"),
    path("access/me/", CandidateAccessContextAPIView.as_view(), name="candidate-access-me"),
    path("access/results/", CandidateAccessResultsAPIView.as_view(), name="candidate-access-results"),
    path("access/logout/", CandidateAccessLogoutAPIView.as_view(), name="candidate-access-logout"),
] + router.urls
