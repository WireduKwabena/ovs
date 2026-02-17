from rest_framework.routers import DefaultRouter

from .views import VettingCampaignViewSet

router = DefaultRouter()
router.register(r"", VettingCampaignViewSet, basename="campaign")

urlpatterns = router.urls
