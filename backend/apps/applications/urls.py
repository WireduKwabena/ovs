from rest_framework.routers import DefaultRouter
from apps.applications.views import VettingCaseViewSet

router = DefaultRouter()
router.register(r'', VettingCaseViewSet, basename='application')

urlpatterns = router.urls
