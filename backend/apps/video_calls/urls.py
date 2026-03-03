from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.video_calls.views import VideoMeetingViewSet

router = DefaultRouter()
router.register(r"meetings", VideoMeetingViewSet, basename="video-meeting")

urlpatterns = [
    path("", include(router.urls)),
]

