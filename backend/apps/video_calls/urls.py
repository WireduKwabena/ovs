from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.video_calls.views import (
    VideoMeetingViewSet,
    guest_meeting_calendar_ics,
    guest_meeting_join,
)

router = DefaultRouter()
router.register(r"meetings", VideoMeetingViewSet, basename="video-meeting")

urlpatterns = [
    path("meetings/guest-calendar-ics/", guest_meeting_calendar_ics, name="video-meeting-guest-calendar-ics"),
    path("meetings/guest-join/", guest_meeting_join, name="video-meeting-guest-join"),
    path("", include(router.urls)),
]

