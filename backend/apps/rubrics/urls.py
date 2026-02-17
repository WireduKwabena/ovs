from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import VettingRubricViewSet,  RubricEvaluationViewSet # , RubricCriteriaViewSet, CriteriaOverrideViewSet
router = DefaultRouter()
router.register(r'vetting-rubrics', VettingRubricViewSet, basename='vettingrubric')
# router.register(r'criteria', RubricCriteriaViewSet, basename='rubriccriteria')
router.register(r'evaluations', RubricEvaluationViewSet, basename='rubricevaluation')
# router.register(r'overrides', CriteriaOverrideViewSet, basename='criteriaoverride')
urlpatterns = [
    path('', include(router.urls)),
]
