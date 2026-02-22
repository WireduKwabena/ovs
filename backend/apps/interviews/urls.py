from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    InterviewFeedbackViewSet,
    InterviewQuestionViewSet,
    InterviewResponseViewSet,
    InterviewSessionViewSet,
)

router = DefaultRouter()
router.register(r"sessions", InterviewSessionViewSet, basename="interview-session")
router.register(r"questions", InterviewQuestionViewSet, basename="interview-question")
router.register(r"responses", InterviewResponseViewSet, basename="interview-response")
router.register(r"feedback", InterviewFeedbackViewSet, basename="interview-feedback")

urlpatterns = [
    path("", include(router.urls)),
]
