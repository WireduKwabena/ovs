from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    CommitteeMembershipViewSet,
    CommitteeViewSet,
    GovernanceChoicesAPIView,
    GovernanceMemberOptionsAPIView,
    OrganizationBootstrapAPIView,
    OrganizationMembershipViewSet,
    OrganizationSummaryAPIView,
)

app_name = "governance"

router = DefaultRouter()
router.register(
    r"organization/members",
    OrganizationMembershipViewSet,
    basename="governance-organization-member",
)
router.register(
    r"organization/committees",
    CommitteeViewSet,
    basename="governance-committee",
)
router.register(
    r"organization/committee-memberships",
    CommitteeMembershipViewSet,
    basename="governance-committee-membership",
)

urlpatterns = [
    path("organization/bootstrap/", OrganizationBootstrapAPIView.as_view(), name="organization-bootstrap"),
    path("organization/summary/", OrganizationSummaryAPIView.as_view(), name="organization-summary"),
    path(
        "organization/lookups/member-options/",
        GovernanceMemberOptionsAPIView.as_view(),
        name="organization-member-options",
    ),
    path(
        "organization/lookups/choices/",
        GovernanceChoicesAPIView.as_view(),
        name="organization-choices",
    ),
    path("", include(router.urls)),
]
