from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import RubricCriteriaViewSet, RubricEvaluationViewSet, VettingRubricViewSet

router = DefaultRouter()
router.register(r"vetting-rubrics", VettingRubricViewSet, basename="vetting-rubric")
router.register(r"criteria", RubricCriteriaViewSet, basename="rubric-criteria")
router.register(r"evaluations", RubricEvaluationViewSet, basename="rubric-evaluation")

urlpatterns = [
    path("", include(router.urls)),
]
