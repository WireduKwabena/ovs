from rest_framework.routers import DefaultRouter

from .views import PersonnelRecordViewSet

router = DefaultRouter()
router.register(r"", PersonnelRecordViewSet, basename="personnel-record")

urlpatterns = router.urls
