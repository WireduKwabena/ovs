import unittest
from unittest.mock import Mock, patch

from django.conf import settings
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.test import APITestCase

from apps.applications.models import VettingCase
from apps.authentication.models import User
from apps.billing.models import BillingSubscription
from apps.governance.models import Organization, OrganizationMembership

from .services import refresh_background_check, submit_background_check

APP_ENABLED = "apps.background_checks" in settings.INSTALLED_APPS


@unittest.skipUnless(APP_ENABLED, "Background checks app is not enabled in INSTALLED_APPS.")
class BackgroundCheckServiceTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(
            code="bg-check-service-org",
            name="Background Check Service Org",
            organization_type="agency",
            is_active=True,
        )
        self.user = User.objects.create_user(
            email="bg-check-user@example.com",
            password="Pass1234!",
            first_name="BG",
            last_name="User",
            user_type="applicant",
        )
        OrganizationMembership.objects.create(
            user=self.user,
            organization=self.organization,
            membership_role="nominee",
            is_active=True,
            is_default=True,
        )
        self.case = VettingCase.objects.create(
            organization=self.organization,
            applicant=self.user,
            position_applied="Risk Analyst",
            department="Compliance",
            priority="medium",
            status="under_review",
        )
        self._create_org_subscription(self.organization, plan_id="starter")

    def _create_org_subscription(self, organization, *, status="complete", payment_status="paid", plan_id="starter"):
        BillingSubscription.objects.create(
            provider="sandbox",
            organization=organization,
            status=status,
            payment_status=payment_status,
            plan_id=plan_id,
            plan_name=plan_id.title(),
            billing_cycle="monthly",
            payment_method="card",
            amount_usd="149.00",
            reference=f"OVS-BGCHECK-{plan_id.upper()}-{str(organization.id)[:8]}-{status.upper()}",
        )

    @override_settings(BACKGROUND_CHECK_REQUIRE_CONSENT=True)
    def test_submit_requires_consent(self):
        with self.assertRaises(ValueError):
            submit_background_check(
                case=self.case,
                check_type="kyc_aml",
                submitted_by=self.user,
                consent_evidence={"granted": False},
            )

    @override_settings(BACKGROUND_CHECK_REQUIRE_CONSENT=True, BILLING_VETTING_OPERATION_QUOTA_ENFORCEMENT_ENABLED=True)
    def test_submit_blocks_when_org_subscription_is_inactive(self):
        organization = Organization.objects.create(
            code="bg-check-sub-inactive",
            name="Background Check Inactive Subscription Org",
            organization_type="agency",
            is_active=True,
        )
        OrganizationMembership.objects.create(
            user=self.user,
            organization=organization,
            membership_role="nominee",
            is_active=True,
            is_default=False,
        )
        self._create_org_subscription(
            organization,
            status="canceled",
            payment_status="unpaid",
            plan_id="starter",
        )
        self.case.organization = organization
        self.case.save(update_fields=["organization", "updated_at"])

        with self.assertRaises(DRFValidationError) as context:
            submit_background_check(
                case=self.case,
                check_type="kyc_aml",
                submitted_by=self.user,
                consent_evidence={"granted": True},
            )

        detail = context.exception.detail if isinstance(context.exception.detail, dict) else {}
        self.assertEqual(detail.get("code"), "subscription_required")
        self.assertEqual((detail.get("quota") or {}).get("operation"), "background_check_submission")

    @override_settings(BACKGROUND_CHECK_REQUIRE_CONSENT=True, BACKGROUND_CHECK_DEFAULT_PROVIDER="mock")
    def test_submit_then_refresh_completes(self):
        check = submit_background_check(
            case=self.case,
            check_type="employment",
            submitted_by=self.user,
            request_payload={"subject": {"full_name": "BG User"}},
            consent_evidence={"granted": True, "method": "checkbox"},
        )

        self.assertEqual(check.status, "submitted")
        self.assertTrue(bool(check.external_reference))

        refreshed = refresh_background_check(check)
        self.assertEqual(refreshed.status, "completed")
        self.assertIsNotNone(refreshed.score)
        self.assertIn(refreshed.recommendation, {"clear", "review"})

    @override_settings(BACKGROUND_CHECK_REQUIRE_CONSENT=True, BACKGROUND_CHECK_DEFAULT_PROVIDER="mock")
    def test_submit_is_idempotent_for_existing_active_check(self):
        first_check = submit_background_check(
            case=self.case,
            check_type="employment",
            submitted_by=self.user,
            request_payload={"subject": {"full_name": "BG User"}},
            consent_evidence={"granted": True},
        )
        second_check = submit_background_check(
            case=self.case,
            check_type="employment",
            submitted_by=self.user,
            request_payload={"subject": {"full_name": "BG User"}},
            consent_evidence={"granted": True},
        )

        self.assertEqual(first_check.id, second_check.id)
        self.assertEqual(
            type(first_check).objects.filter(case=self.case, check_type="employment").count(),
            1,
        )

    @override_settings(BACKGROUND_CHECK_REQUIRE_CONSENT=True, BACKGROUND_CHECK_DEFAULT_PROVIDER="mock")
    @patch("apps.background_checks.services.log_event", return_value=True)
    def test_submit_logs_audit(self, mock_log_event):
        check = submit_background_check(
            case=self.case,
            check_type="employment",
            submitted_by=self.user,
            consent_evidence={"granted": True},
        )

        self.assertTrue(mock_log_event.called)
        kwargs = mock_log_event.call_args.kwargs
        self.assertEqual(kwargs["action"], "create")
        self.assertEqual(kwargs["entity_type"], "background_check")
        self.assertEqual(kwargs["entity_id"], str(check.id))
        self.assertEqual(kwargs["user"], self.user)
        self.assertEqual(kwargs["changes"]["event"], "submit")

    @override_settings(BACKGROUND_CHECK_REQUIRE_CONSENT=True, BACKGROUND_CHECK_DEFAULT_PROVIDER="mock")
    @patch("apps.background_checks.services.log_event", return_value=True)
    def test_refresh_logs_audit(self, mock_log_event):
        check = submit_background_check(
            case=self.case,
            check_type="employment",
            submitted_by=self.user,
            consent_evidence={"granted": True},
        )

        mock_log_event.reset_mock()
        refreshed = refresh_background_check(check)

        self.assertEqual(refreshed.status, "completed")
        self.assertTrue(mock_log_event.called)
        kwargs = mock_log_event.call_args.kwargs
        self.assertEqual(kwargs["action"], "update")
        self.assertEqual(kwargs["entity_type"], "background_check")
        self.assertEqual(kwargs["entity_id"], str(check.id))
        self.assertEqual(kwargs["changes"]["event"], "provider_refresh")

    @override_settings(
        BACKGROUND_CHECK_REQUIRE_CONSENT=True,
        BACKGROUND_CHECK_HTTP_BASE_URL="https://provider.example.com",
        BACKGROUND_CHECK_HTTP_SUBMIT_PATH="/api/checks",
        BACKGROUND_CHECK_HTTP_REFRESH_PATH_TEMPLATE="/api/checks/{external_reference}",
    )
    def test_http_provider_submit_then_refresh(self):
        mock_post_response = Mock()
        mock_post_response.raise_for_status.return_value = None
        mock_post_response.json.return_value = {
            "external_reference": "ext-123",
            "status": "submitted",
        }

        mock_get_response = Mock()
        mock_get_response.raise_for_status.return_value = None
        mock_get_response.json.return_value = {
            "status": "completed",
            "score": 92,
            "risk_level": "low",
            "recommendation": "clear",
        }

        with patch("apps.background_checks.providers.http_provider.httpx.post", return_value=mock_post_response) as mock_post:
            with patch("apps.background_checks.providers.http_provider.httpx.get", return_value=mock_get_response) as mock_get:
                check = submit_background_check(
                    case=self.case,
                    check_type="kyc_aml",
                    submitted_by=self.user,
                    provider_key="http",
                    consent_evidence={"granted": True},
                )
                refreshed = refresh_background_check(check)

        self.assertEqual(check.provider_key, "http")
        self.assertEqual(check.external_reference, "ext-123")
        self.assertEqual(refreshed.status, "completed")
        self.assertEqual(refreshed.score, 92)
        self.assertEqual(refreshed.recommendation, "clear")
        mock_post.assert_called_once()
        mock_get.assert_called_once()


@unittest.skipUnless(APP_ENABLED, "Background checks app is not enabled in INSTALLED_APPS.")
class BackgroundCheckApiTests(APITestCase):
    def setUp(self):
        self.organization = Organization.objects.create(
            code="bg-check-api-org",
            name="Background Check API Org",
            organization_type="agency",
            is_active=True,
        )
        self.admin_user = User.objects.create_user(
            email="bg-admin@example.com",
            password="Pass1234!",
            first_name="BG",
            last_name="Admin",
            user_type="admin",
            is_staff=True,
        )
        self.hr_user = User.objects.create_user(
            email="bg-hr@example.com",
            password="Pass1234!",
            first_name="BG",
            last_name="HR",
            user_type="hr_manager",
        )
        self.user = User.objects.create_user(
            email="bg-api-user@example.com",
            password="Pass1234!",
            first_name="BG",
            last_name="Applicant",
            user_type="applicant",
        )
        self.other_user = User.objects.create_user(
            email="bg-api-other@example.com",
            password="Pass1234!",
            first_name="BG",
            last_name="Other",
            user_type="applicant",
        )
        OrganizationMembership.objects.create(
            user=self.hr_user,
            organization=self.organization,
            membership_role="registry_admin",
            is_active=True,
            is_default=True,
        )
        OrganizationMembership.objects.create(
            user=self.user,
            organization=self.organization,
            membership_role="nominee",
            is_active=True,
            is_default=True,
        )
        OrganizationMembership.objects.create(
            user=self.other_user,
            organization=self.organization,
            membership_role="nominee",
            is_active=True,
            is_default=True,
        )

        self.case = VettingCase.objects.create(
            organization=self.organization,
            applicant=self.user,
            position_applied="Risk Analyst",
            department="Compliance",
            priority="medium",
            status="under_review",
        )
        self.other_case = VettingCase.objects.create(
            organization=self.organization,
            applicant=self.other_user,
            position_applied="Security Analyst",
            department="Operations",
            priority="high",
            status="under_review",
        )
        self._create_org_subscription(self.organization, plan_id="starter")

    def _create_org_subscription(self, organization, *, status="complete", payment_status="paid", plan_id="starter"):
        BillingSubscription.objects.create(
            provider="sandbox",
            organization=organization,
            status=status,
            payment_status=payment_status,
            plan_id=plan_id,
            plan_name=plan_id.title(),
            billing_cycle="monthly",
            payment_method="card",
            amount_usd="149.00",
            reference=f"OVS-BGAPI-{plan_id.upper()}-{str(organization.id)[:8]}-{status.upper()}",
        )

    def test_applicant_cannot_list_background_checks(self):
        self.client.force_authenticate(self.user)
        response = self.client.get("/api/background-checks/checks/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @override_settings(BACKGROUND_CHECK_REQUIRE_CONSENT=True)
    def test_hr_manager_can_create_background_check(self):
        self.client.force_authenticate(self.hr_user)
        response = self.client.post(
            "/api/background-checks/checks/",
            {
                "case": self.case.id,
                "check_type": "kyc_aml",
                "provider_key": "mock",
                "request_payload": {"country": "US"},
                "consent_evidence": {"granted": True},
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["case"], self.case.id)
        self.assertEqual(response.data["status"], "submitted")

    @override_settings(BACKGROUND_CHECK_REQUIRE_CONSENT=True, BILLING_VETTING_OPERATION_QUOTA_ENFORCEMENT_ENABLED=True)
    def test_hr_manager_create_blocks_when_org_subscription_is_inactive(self):
        organization = Organization.objects.create(
            code="bg-api-sub-inactive",
            name="Background Check API Inactive Subscription Org",
            organization_type="agency",
            is_active=True,
        )
        OrganizationMembership.objects.create(
            user=self.hr_user,
            organization=organization,
            membership_role="registry_admin",
            is_active=True,
            is_default=False,
        )
        self._create_org_subscription(
            organization,
            status="canceled",
            payment_status="unpaid",
            plan_id="starter",
        )
        self.case.organization = organization
        self.case.save(update_fields=["organization", "updated_at"])

        self.client.force_authenticate(self.hr_user)
        response = self.client.post(
            "/api/background-checks/checks/",
            {
                "case": self.case.id,
                "check_type": "kyc_aml",
                "provider_key": "mock",
                "request_payload": {"country": "US"},
                "consent_evidence": {"granted": True},
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data.get("code"), "subscription_required")
        self.assertEqual((response.data.get("quota") or {}).get("operation"), "background_check_submission")

    @override_settings(BACKGROUND_CHECK_REQUIRE_CONSENT=True)
    def test_applicant_cannot_create_background_check(self):
        self.client.force_authenticate(self.user)
        response = self.client.post(
            "/api/background-checks/checks/",
            {
                "case": self.case.id,
                "check_type": "criminal",
                "provider_key": "mock",
                "consent_evidence": {"granted": True},
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @override_settings(BACKGROUND_CHECK_REQUIRE_CONSENT=True)
    @patch("apps.background_checks.views.refresh_background_check_task.delay", return_value=None)
    def test_create_with_async_queues_refresh(self, mock_delay):
        self.client.force_authenticate(self.hr_user)
        response = self.client.post(
            "/api/background-checks/checks/",
            {
                "case": self.case.id,
                "check_type": "identity",
                "provider_key": "mock",
                "consent_evidence": {"granted": True},
                "run_async": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["refresh_queued"])
        mock_delay.assert_called_once()


    @override_settings(BACKGROUND_CHECK_REQUIRE_CONSENT=True)
    @patch("apps.background_checks.services.log_event", return_value=True)
    def test_create_passes_request_to_audit_log(self, mock_log_event):
        self.client.force_authenticate(self.hr_user)
        response = self.client.post(
            "/api/background-checks/checks/",
            {
                "case": self.case.id,
                "check_type": "kyc_aml",
                "provider_key": "mock",
                "consent_evidence": {"granted": True},
            },
            format="json",
            HTTP_USER_AGENT="bg-audit-agent",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(mock_log_event.called)
        kwargs = mock_log_event.call_args.kwargs
        self.assertIsNotNone(kwargs.get("request"))
        self.assertEqual(kwargs["request"].META.get("HTTP_USER_AGENT"), "bg-audit-agent")

    @override_settings(BACKGROUND_CHECK_REQUIRE_CONSENT=True)
    @patch("apps.background_checks.services.log_event", return_value=True)
    def test_refresh_passes_request_to_audit_log(self, mock_log_event):
        check = submit_background_check(
            case=self.case,
            check_type="employment",
            submitted_by=self.hr_user,
            consent_evidence={"granted": True},
        )
        mock_log_event.reset_mock()

        self.client.force_authenticate(self.hr_user)
        response = self.client.post(
            f"/api/background-checks/checks/{check.id}/refresh/",
            {},
            format="json",
            HTTP_USER_AGENT="bg-refresh-agent",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(mock_log_event.called)
        kwargs = mock_log_event.call_args.kwargs
        self.assertIsNotNone(kwargs.get("request"))
        self.assertEqual(kwargs["request"].META.get("HTTP_USER_AGENT"), "bg-refresh-agent")

    @override_settings(BACKGROUND_CHECK_REQUIRE_CONSENT=True)
    def test_scoped_listing_and_admin_visibility(self):
        submit_background_check(
            case=self.case,
            check_type="employment",
            submitted_by=self.hr_user,
            consent_evidence={"granted": True},
        )
        submit_background_check(
            case=self.other_case,
            check_type="employment",
            submitted_by=self.hr_user,
            consent_evidence={"granted": True},
        )

        self.client.force_authenticate(self.hr_user)
        hr_response = self.client.get("/api/background-checks/checks/")
        self.assertEqual(hr_response.status_code, status.HTTP_200_OK)
        self.assertEqual(hr_response.data["count"], 2)

        self.client.force_authenticate(self.admin_user)
        admin_response = self.client.get("/api/background-checks/checks/")
        self.assertEqual(admin_response.status_code, status.HTTP_200_OK)
        self.assertEqual(admin_response.data["count"], 2)

    @override_settings(BACKGROUND_CHECK_REQUIRE_CONSENT=True, BACKGROUND_CHECK_WEBHOOK_TOKEN="secret-webhook")
    @patch("apps.background_checks.services.log_event", return_value=True)
    def test_provider_webhook_updates_check(self, mock_log_event):
        check = submit_background_check(
            case=self.case,
            check_type="criminal",
            submitted_by=self.user,
            consent_evidence={"granted": True},
        )
        mock_log_event.reset_mock()

        self.client.force_authenticate(None)
        response = self.client.post(
            "/api/background-checks/providers/mock/webhook/",
            {
                "external_reference": check.external_reference,
                "status": "completed",
                "score": 97,
                "risk_level": "low",
                "recommendation": "clear",
            },
            format="json",
            HTTP_X_BACKGROUND_WEBHOOK_TOKEN="secret-webhook",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        check.refresh_from_db()
        self.assertEqual(check.status, "completed")
        self.assertEqual(check.score, 97)
        self.assertEqual(check.recommendation, "clear")
        self.assertTrue(mock_log_event.called)
        self.assertEqual(mock_log_event.call_args.kwargs["changes"]["event"], "provider_webhook")
        self.assertIsNotNone(mock_log_event.call_args.kwargs.get("request"))

    @override_settings(BACKGROUND_CHECK_REQUIRE_CONSENT=True, BACKGROUND_CHECK_WEBHOOK_TOKEN="secret-webhook")
    def test_provider_webhook_rejects_invalid_token(self):
        check = submit_background_check(
            case=self.case,
            check_type="criminal",
            submitted_by=self.user,
            consent_evidence={"granted": True},
        )

        self.client.force_authenticate(None)
        response = self.client.post(
            "/api/background-checks/providers/mock/webhook/",
            {
                "external_reference": check.external_reference,
                "status": "completed",
            },
            format="json",
            HTTP_X_BACKGROUND_WEBHOOK_TOKEN="wrong-token",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
