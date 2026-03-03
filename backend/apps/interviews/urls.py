from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    InterviewFeedbackViewSet,
    InterviewQuestionViewSet,
    InterviewResponseUploadAPIView,
    InterviewResponseViewSet,
    InterviewSessionViewSet,
    LegacyInterviewStartAPIView,
)

router = DefaultRouter()
router.register(r"sessions", InterviewSessionViewSet, basename="interview-session")
router.register(r"questions", InterviewQuestionViewSet, basename="interview-question")
router.register(r"responses", InterviewResponseViewSet, basename="interview-response")
router.register(r"feedback", InterviewFeedbackViewSet, basename="interview-feedback")

urlpatterns = [
    path("interrogation/start/", LegacyInterviewStartAPIView.as_view(), name="interview-legacy-start"),
    path("upload-response/", InterviewResponseUploadAPIView.as_view(), name="interview-upload-response"),
    path("", include(router.urls)),
]
