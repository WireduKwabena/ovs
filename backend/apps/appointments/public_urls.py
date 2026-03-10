from django.urls import path

from .public_views import (
    PublicTransparencyAppointmentDetailView,
    PublicTransparencyAppointmentListView,
    PublicTransparencyGazetteFeedView,
    PublicTransparencyOfficeholderListView,
    PublicTransparencyOpenAppointmentListView,
    PublicTransparencyPositionListView,
    PublicTransparencySummaryView,
    PublicTransparencyVacantPositionListView,
)

urlpatterns = [
    path("summary/", PublicTransparencySummaryView.as_view(), name="public-transparency-summary"),
    path("appointments/", PublicTransparencyAppointmentListView.as_view(), name="public-transparency-appointments"),
    path(
        "appointments/gazette-feed/",
        PublicTransparencyGazetteFeedView.as_view(),
        name="public-transparency-gazette-feed",
    ),
    path("appointments/open/", PublicTransparencyOpenAppointmentListView.as_view(), name="public-transparency-open-appointments"),
    path(
        "appointments/<uuid:appointment_id>/",
        PublicTransparencyAppointmentDetailView.as_view(),
        name="public-transparency-appointment-detail",
    ),
    path("positions/", PublicTransparencyPositionListView.as_view(), name="public-transparency-positions"),
    path("positions/vacant/", PublicTransparencyVacantPositionListView.as_view(), name="public-transparency-vacant-positions"),
    path("officeholders/", PublicTransparencyOfficeholderListView.as_view(), name="public-transparency-officeholders"),
]
