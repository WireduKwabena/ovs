from rest_framework.routers import DefaultRouter

from .views import CandidateEnrollmentViewSet, CandidateViewSet

router = DefaultRouter()
router.register(r"candidates", CandidateViewSet, basename="candidate")
router.register(r"enrollments", CandidateEnrollmentViewSet, basename="candidate-enrollment")

urlpatterns = router.urls
