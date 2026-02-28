from rest_framework.routers import DefaultRouter

from .views import CandidateEnrollmentViewSet, CandidateSocialProfileViewSet, CandidateViewSet

router = DefaultRouter()
router.register(r"candidates", CandidateViewSet, basename="candidate")
router.register(r"social-profiles", CandidateSocialProfileViewSet, basename="candidate-social-profile")
router.register(r"enrollments", CandidateEnrollmentViewSet, basename="candidate-enrollment")

urlpatterns = router.urls
