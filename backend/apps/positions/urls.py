from rest_framework.routers import DefaultRouter

from .views import GovernmentPositionViewSet

router = DefaultRouter()
router.register(r"", GovernmentPositionViewSet, basename="government-position")

urlpatterns = router.urls
