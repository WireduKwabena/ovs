from rest_framework.routers import DefaultRouter

from apps.applications.views import DocumentViewSet, VettingCaseViewSet

router = DefaultRouter()
router.register(r"cases", VettingCaseViewSet, basename="application-case")
router.register(r"documents", DocumentViewSet, basename="application-document")

urlpatterns = router.urls
