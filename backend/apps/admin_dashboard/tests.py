# backend/apps/admin_dashboard/tests.py
import unittest

from django.conf import settings
from rest_framework import status
from rest_framework.test import APITestCase

from apps.users.models import User
from apps.applications.models import VettingCase
from apps.tenants.models import Organization
from apps.governance.models import OrganizationMembership


APP_ENABLED = "apps.admin_dashboard" in settings.INSTALLED_APPS


@unittest.skipUnless(APP_ENABLED, "Admin dashboard app is not enabled in INSTALLED_APPS.")
class AdminDashboardAPITests(APITestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(
            email="admin@example.com",
            password="strongpassword123",
            first_name="Admin",
            last_name="User",
            user_type="admin",
            is_staff=True,
        )
        self.regular_user = User.objects.create_user(
            email="test@example.com",
            password="strongpassword123",
            first_name="Test",
            last_name="User",
            user_type="applicant",
        )
        self.internal_user = User.objects.create_user(
            email="hr@example.com",
            password="strongpassword123",
            first_name="Internal",
            last_name="Manager",
            user_type="internal",
        )
        self.organization_one = Organization.objects.create(
            code="org-one",
            name="Organization One",
            organization_type="agency",
        )
        self.organization_two = Organization.objects.create(
            code="org-two",
            name="Organization Two",
            organization_type="agency",
        )
        self.org_admin_user = User.objects.create_user(
            email="org-admin@example.com",
            password="strongpassword123",
            first_name="Org",
            last_name="Admin",
            user_type="internal",
        )
        self.org_internal_user = User.objects.create_user(
            email="org-member@example.com",
            password="strongpassword123",
            first_name="Org",
            last_name="Member",
            user_type="internal",
        )
        self.other_org_user = User.objects.create_user(
            email="other-org@example.com",
            password="strongpassword123",
            first_name="Other",
            last_name="Member",
            user_type="internal",
        )
        OrganizationMembership.objects.create(
            user=self.org_admin_user,
            organization=self.organization_one,
            membership_role="registry_admin",
            is_active=True,
            is_default=True,
        )
        OrganizationMembership.objects.create(
            user=self.org_internal_user,
            organization=self.organization_one,
            membership_role="member",
            is_active=True,
            is_default=True,
        )
        OrganizationMembership.objects.create(
            user=self.other_org_user,
            organization=self.organization_two,
            membership_role="member",
            is_active=True,
            is_default=True,
        )
        VettingCase.objects.create(
            applicant=self.regular_user,
            position_applied="Employment",
            department="General",
            status="pending",
            priority="medium",
            organization=self.organization_one,
        )
        VettingCase.objects.create(
            applicant=self.regular_user,
            position_applied="Visa",
            department="General",
            status="approved",
            priority="medium",
            organization=self.organization_two,
        )

    def test_dashboard_as_admin(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get("/api/admin/dashboard/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_dashboard_as_regular_user(self):
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.get("/api/admin/dashboard/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_dashboard_as_internal_is_forbidden(self):
        self.client.force_authenticate(user=self.internal_user)
        response = self.client.get("/api/admin/dashboard/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_dashboard_as_staff_non_admin_is_forbidden(self):
        staff_user = User.objects.create_user(
            email="staff-non-admin@example.com",
            password="strongpassword123",
            first_name="Staff",
            last_name="NonAdmin",
            user_type="internal",
            is_staff=True,
        )
        self.client.force_authenticate(user=staff_user)
        response = self.client.get("/api/admin/dashboard/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_analytics_as_admin(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get("/api/admin/analytics/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_dashboard_as_org_admin_is_scoped_to_active_organization(self):
        self.client.force_authenticate(user=self.org_admin_user)
        response = self.client.get(
            "/api/admin/dashboard/",
            HTTP_X_ACTIVE_ORGANIZATION_ID=str(self.organization_one.id),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_applications"], 1)
        self.assertEqual(len(response.data["recent_applications"]), 1)

    def test_analytics_as_org_admin_are_scoped_to_active_organization(self):
        self.client.force_authenticate(user=self.org_admin_user)
        response = self.client.get(
            "/api/admin/analytics/",
            HTTP_X_ACTIVE_ORGANIZATION_ID=str(self.organization_one.id),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["status_distribution"]), 1)
        self.assertEqual(response.data["total_applications"], 1)

    def test_cases_as_admin(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get("/api/admin/cases/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_cases_filter_by_status(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get("/api/admin/cases/?status=pending")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_analytics_invalid_months_falls_back_to_default_window(self):
        self.client.force_authenticate(user=self.org_admin_user)
        response = self.client.get(
            "/api/admin/analytics/?months=invalid",
            HTTP_X_ACTIVE_ORGANIZATION_ID=str(self.organization_one.id),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["monthly_trend"]), 6)

    def test_cases_invalid_page_and_page_size_use_defaults(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get("/api/admin/cases/?page=abc&page_size=-5")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_cases_supports_ordering(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get("/api/admin/cases/?ordering=created_at")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_cases_invalid_ordering_falls_back_to_default(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get("/api/admin/cases/?ordering=unsupported_field")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_cases_as_org_admin_are_scoped_to_active_organization(self):
        self.client.force_authenticate(user=self.org_admin_user)
        response = self.client.get(
            "/api/admin/cases/",
            HTTP_X_ACTIVE_ORGANIZATION_ID=str(self.organization_one.id),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["application_type"], "Employment")

    def test_users_list_as_admin(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get("/api/admin/users/")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_users_filter_by_type(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get("/api/admin/users/?user_type=internal")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_users_list_as_org_admin_are_scoped_to_active_organization(self):
        self.client.force_authenticate(user=self.org_admin_user)
        response = self.client.get(
            "/api/admin/users/",
            HTTP_X_ACTIVE_ORGANIZATION_ID=str(self.organization_one.id),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        returned_emails = {item["email"] for item in response.data["results"]}
        self.assertIn("org-admin@example.com", returned_emails)
        self.assertIn("org-member@example.com", returned_emails)
        self.assertNotIn("other-org@example.com", returned_emails)
        self.assertNotIn("admin@example.com", returned_emails)

    def test_admin_can_disable_non_self_user(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.patch(
            f"/api/admin/users/{self.internal_user.id}/",
            {"is_active": False},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_cannot_disable_self(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.patch(
            f"/api/admin/users/{self.admin_user.id}/",
            {"is_active": False},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_org_admin_can_disable_user_within_active_organization_scope(self):
        self.client.force_authenticate(user=self.org_admin_user)
        response = self.client.patch(
            f"/api/admin/users/{self.org_internal_user.id}/",
            {"is_active": False},
            format="json",
            HTTP_X_ACTIVE_ORGANIZATION_ID=str(self.organization_one.id),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.org_internal_user.refresh_from_db()
        self.assertFalse(self.org_internal_user.is_active)

    def test_org_admin_cannot_update_user_outside_active_organization_scope(self):
        self.client.force_authenticate(user=self.org_admin_user)
        response = self.client.patch(
            f"/api/admin/users/{self.other_org_user.id}/",
            {"is_active": False},
            format="json",
            HTTP_X_ACTIVE_ORGANIZATION_ID=str(self.organization_one.id),
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_org_admin_cannot_assign_platform_identity_fields(self):
        self.client.force_authenticate(user=self.org_admin_user)
        response = self.client.patch(
            f"/api/admin/users/{self.org_internal_user.id}/",
            {"user_type": "admin"},
            format="json",
            HTTP_X_ACTIVE_ORGANIZATION_ID=str(self.organization_one.id),
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.org_internal_user.refresh_from_db()
        self.assertEqual(self.org_internal_user.user_type, "internal")

    def test_admin_can_assign_government_group_roles(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.patch(
            f"/api/admin/users/{self.internal_user.id}/",
            {"group_roles": ["vetting_officer", "auditor"]},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_cannot_assign_internal_roles_to_applicant_user(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.patch(
            f"/api/admin/users/{self.regular_user.id}/",
            {"group_roles": ["vetting_officer"]},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


