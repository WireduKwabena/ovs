from rest_framework.routers import DefaultRouter

from apps.applications.views import VettingCaseViewSet
from apps.appointments.views import AppointmentRecordViewSet
from apps.campaigns.views import VettingCampaignViewSet
from apps.positions.views import GovernmentPositionViewSet

router = DefaultRouter()
router.register(r"exercises", VettingCampaignViewSet, basename="government-exercise")
router.register(r"vetting-dossiers", VettingCaseViewSet, basename="government-vetting-dossier")
router.register(r"nominations", AppointmentRecordViewSet, basename="government-nomination")
router.register(r"offices", GovernmentPositionViewSet, basename="government-office")

urlpatterns = router.urls

