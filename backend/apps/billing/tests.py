from unittest.mock import Mock, patch
from datetime import timedelta
import hashlib
import hmac
import json

from django.contrib.auth.models import Group
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.audit.models import AuditLog
from apps.campaigns.models import VettingCampaign
from apps.candidates.models import Candidate, CandidateEnrollment
from apps.governance.models import Organization, OrganizationMembership

from .models import BillingSubscription, BillingWebhookEvent, OrganizationOnboardingToken
from .quotas import get_organization_seat_quota_snapshot


class BillingApiTests(APITestCase):
    sandbox_endpoint = "/api/billing/subscriptions/confirm/"
    subscription_access_verify_endpoint = "/api/billing/subscriptions/access/verify/"
    stripe_checkout_endpoint = "/api/billing/subscriptions/stripe/checkout-session/"
    stripe_confirm_endpoint = "/api/billing/subscriptions/stripe/confirm/"
    stripe_webhook_endpoint = "/api/billing/subscriptions/stripe/webhook/"
    paystack_checkout_endpoint = "/api/billing/subscriptions/paystack/checkout-session/"
    paystack_confirm_endpoint = "/api/billing/subscriptions/paystack/confirm/"
    paystack_webhook_endpoint = "/api/billing/subscriptions/paystack/webhook/"
    billing_health_endpoint = "/api/billing/health/"
    billing_exchange_rate_endpoint = "/api/billing/exchange-rate/"
    billing_quotas_endpoint = "/api/billing/quotas/"
    billing_manage_endpoint = "/api/billing/subscriptions/manage/"
    billing_manage_update_session_endpoint = "/api/billing/subscriptions/manage/payment-method/update-session/"
    billing_retry_endpoint = "/api/billing/subscriptions/manage/retry/"
    onboarding_state_endpoint = "/api/billing/onboarding-token/"
    onboarding_generate_endpoint = "/api/billing/onboarding-token/generate/"
    onboarding_revoke_endpoint = "/api/billing/onboarding-token/revoke/"
    onboarding_validate_endpoint = "/api/billing/onboarding-token/validate/"

    def setUp(self):
        cache.clear()

    def _create_internal_user(self, email: str = "billing-hr@example.com"):
        user_model = get_user_model()
        return user_model.objects.create_user(
            email=email,
            password="StrongPass123!",
            first_name="Billing",
            last_name="Manager",
            user_type="internal",
        )

    def _create_org_membership(
        self,
        user,
        *,
        code: str,
        name: str,
        membership_role: str = "registry_admin",
        is_default: bool = True,
    ) -> Organization:
        organization = Organization.objects.create(
            code=code,
            name=name,
            organization_type="agency",
            is_active=True,
        )
        OrganizationMembership.objects.create(
            user=user,
            organization=organization,
            membership_role=membership_role,
            is_active=True,
            is_default=is_default,
        )
        return organization

    def _create_active_org_subscription(
        self,
        *,
        organization: Organization,
        reference: str,
        plan_id: str = "growth",
        plan_name: str = "Growth",
    ) -> BillingSubscription:
        return BillingSubscription.objects.create(
            provider="sandbox",
            organization=organization,
            status="complete",
            payment_status="paid",
            plan_id=plan_id,
            plan_name=plan_name,
            billing_cycle="monthly",
            payment_method="card",
            amount_usd="399.00",
            reference=reference,
        )

    def _authenticate_checkout_actor(
        self,
        *,
        email: str = "billing-checkout@example.com",
        code: str = "billing-checkout-org",
        name: str = "Billing Checkout Org",
    ) -> tuple:
        user = self._create_internal_user(email=email)
        organization = self._create_org_membership(
            user,
            code=code,
            name=name,
        )
        self.client.force_authenticate(user=user)
        return user, organization

    @staticmethod
    def _paystack_signature(payload: bytes, secret: str) -> str:
        return hmac.new(secret.encode("utf-8"), payload, hashlib.sha512).hexdigest()

    def test_billing_quota_requires_authentication(self):
        response = self.client.get(self.billing_quotas_endpoint)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_billing_manage_requires_authentication(self):
        response = self.client.get(self.billing_manage_endpoint)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_billing_manage_returns_active_subscription_summary(self):
        internal_user = self._create_internal_user()
        BillingSubscription.objects.create(
            provider="sandbox",
            status="complete",
            payment_status="paid",
            plan_id="growth",
            plan_name="Growth",
            billing_cycle="monthly",
            payment_method="card",
            amount_usd="399.00",
            reference="OVS-MANAGE-SUMMARY",
            registration_consumed_by_email=internal_user.email,
            metadata={
                "payment_method_summary": {
                    "type": "card",
                    "display": "Card",
                    "brand": None,
                    "last4": None,
                    "exp_month": None,
                    "exp_year": None,
                }
            },
        )

        self.client.force_authenticate(user=internal_user)
        response = self.client.get(self.billing_manage_endpoint)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "ok")
        self.assertIsNotNone(response.data["subscription"])
        self.assertEqual(response.data["subscription"]["plan_id"], "growth")
        self.assertEqual(response.data["subscription"]["payment_method"]["type"], "card")
        self.assertEqual(response.data["subscription"]["payment_method"]["display"], "Card")

    def test_billing_manage_prefers_org_owned_subscription_when_available(self):
        internal_user = self._create_internal_user(email="billing-org-manage@example.com")
        organization = self._create_org_membership(
            internal_user,
            code="billing-org-manage",
            name="Billing Org Manage",
        )
        BillingSubscription.objects.create(
            provider="sandbox",
            organization=organization,
            status="complete",
            payment_status="paid",
            plan_id="growth",
            plan_name="Growth",
            billing_cycle="monthly",
            payment_method="card",
            amount_usd="399.00",
            reference="OVS-ORG-MANAGE-GROWTH",
        )
        BillingSubscription.objects.create(
            provider="sandbox",
            status="complete",
            payment_status="paid",
            plan_id="starter",
            plan_name="Starter",
            billing_cycle="monthly",
            payment_method="card",
            amount_usd="149.00",
            reference="OVS-LEGACY-MANAGE-STARTER",
            registration_consumed_by_email=internal_user.email,
        )

        self.client.force_authenticate(user=internal_user)
        response = self.client.get(self.billing_manage_endpoint)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "ok")
        self.assertEqual(response.data["subscription"]["plan_id"], "growth")
        self.assertEqual(response.data["subscription"]["organization_id"], str(organization.id))
        self.assertEqual(response.data["subscription"]["organization_name"], organization.name)

    def test_billing_manage_falls_back_to_legacy_subscription_when_org_owned_missing(self):
        internal_user = self._create_internal_user(email="billing-org-fallback@example.com")
        self._create_org_membership(
            internal_user,
            code="billing-org-fallback",
            name="Billing Org Fallback",
        )
        BillingSubscription.objects.create(
            provider="sandbox",
            status="complete",
            payment_status="paid",
            plan_id="starter",
            plan_name="Starter",
            billing_cycle="monthly",
            payment_method="card",
            amount_usd="149.00",
            reference="OVS-LEGACY-FALLBACK-STARTER",
            registration_consumed_by_email=internal_user.email,
        )

        self.client.force_authenticate(user=internal_user)
        response = self.client.get(self.billing_manage_endpoint)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "ok")
        self.assertEqual(response.data["subscription"]["plan_id"], "starter")
        self.assertIsNone(response.data["subscription"]["organization_id"])

    def test_billing_manage_patch_updates_sandbox_payment_method(self):
        internal_user = self._create_internal_user(email="billing-update@example.com")
        subscription = BillingSubscription.objects.create(
            provider="sandbox",
            status="complete",
            payment_status="paid",
            plan_id="starter",
            plan_name="Starter",
            billing_cycle="monthly",
            payment_method="card",
            amount_usd="149.00",
            reference="OVS-MANAGE-UPDATE",
            registration_consumed_by_email=internal_user.email,
        )

        self.client.force_authenticate(user=internal_user)
        response = self.client.patch(
            self.billing_manage_endpoint,
            {"payment_method": "bank_transfer"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        subscription.refresh_from_db()
        self.assertEqual(subscription.payment_method, "bank_transfer")
        self.assertEqual(response.data["subscription"]["payment_method"]["type"], "bank_transfer")

    def test_billing_manage_delete_schedules_end_of_period_cancellation(self):
        internal_user = self._create_internal_user(email="billing-delete@example.com")
        subscription = BillingSubscription.objects.create(
            provider="sandbox",
            status="complete",
            payment_status="paid",
            plan_id="starter",
            plan_name="Starter",
            billing_cycle="monthly",
            payment_method="card",
            amount_usd="149.00",
            reference="OVS-MANAGE-DELETE",
            registration_consumed_by_email=internal_user.email,
        )

        self.client.force_authenticate(user=internal_user)
        response = self.client.delete(self.billing_manage_endpoint)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        subscription.refresh_from_db()
        self.assertEqual(subscription.status, "complete")
        self.assertEqual(bool(subscription.metadata.get("cancel_at_period_end")), True)
        self.assertIn("cancellation_effective_at", subscription.metadata)
        self.assertIn("end of current billing period", response.data.get("message", "").lower())

    def test_billing_retry_creates_new_sandbox_subscription_for_failed_payment(self):
        internal_user = self._create_internal_user(email="billing-retry@example.com")
        BillingSubscription.objects.create(
            provider="sandbox",
            status="failed",
            payment_status="unpaid",
            plan_id="growth",
            plan_name="Growth",
            billing_cycle="monthly",
            payment_method="card",
            amount_usd="399.00",
            reference="OVS-MANAGE-RETRY-FAILED",
            registration_consumed_by_email=internal_user.email,
        )

        self.client.force_authenticate(user=internal_user)
        response = self.client.post(self.billing_retry_endpoint, {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["provider"], "sandbox")
        self.assertEqual(response.data["status"], "ok")
        self.assertEqual(
            BillingSubscription.objects.filter(
                registration_consumed_by_email=internal_user.email,
                status="complete",
                payment_status="paid",
            ).count(),
            1,
        )

    @override_settings(
        PAYSTACK_SECRET_KEY="sk_test_paystack",
        PAYSTACK_CURRENCY="GHS",
        PAYSTACK_USD_EXCHANGE_RATE=15.0,
        EXCHANGE_RATE_API_URL="",
    )
    @patch("apps.billing.views._paystack_initialize_transaction")
    def test_billing_retry_paystack_preserves_payment_method_and_converts_amount(self, mock_initialize):
        mock_initialize.return_value = {
            "authorization_url": "https://checkout.paystack.com/retry_mobile_money_123",
            "access_code": "psk_retry_mobile_money_123",
            "reference": "OVS-PAYSTACK-RETRY-TEST-123",
        }

        internal_user = self._create_internal_user(email="billing-retry-paystack@example.com")
        BillingSubscription.objects.create(
            provider="paystack",
            status="failed",
            payment_status="unpaid",
            session_id="OVS-PAYSTACK-RETRY-FAILED-001",
            plan_id="growth",
            plan_name="Growth",
            billing_cycle="monthly",
            payment_method="mobile_money",
            amount_usd="399.00",
            reference="OVS-PAYSTACK-RETRY-FAILED-001",
            registration_consumed_by_email=internal_user.email,
        )

        self.client.force_authenticate(user=internal_user)
        response = self.client.post(self.billing_retry_endpoint, {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["provider"], "paystack")
        self.assertEqual(response.data["session_id"], "OVS-PAYSTACK-RETRY-TEST-123")
        self.assertIn("checkout_url", response.data)
        mock_initialize.assert_called_once()

        initialize_payload = mock_initialize.call_args.args[0]
        self.assertEqual(initialize_payload["currency"], "GHS")
        self.assertEqual(initialize_payload["amount"], 598500)
        self.assertEqual(initialize_payload["channels"], ["mobile_money"])
        self.assertEqual(initialize_payload["metadata"]["payment_method"], "mobile_money")

        persisted = BillingSubscription.objects.get(provider="paystack", session_id="OVS-PAYSTACK-RETRY-TEST-123")
        self.assertEqual(persisted.status, "open")
        self.assertEqual(persisted.payment_status, "pending")
        self.assertEqual(persisted.payment_method, "mobile_money")
        self.assertEqual(float(persisted.amount_usd), 399.0)

    @override_settings(STRIPE_SECRET_KEY="sk_test_123")
    @patch("apps.billing.views._ensure_stripe_ready")
    @patch("apps.billing.views._stripe_create_billing_portal_session")
    def test_billing_manage_update_session_returns_stripe_portal_url(self, mock_create_portal, mock_ready):
        mock_ready.return_value = None
        mock_create_portal.return_value = {"url": "https://billing.stripe.com/session/test"}

        internal_user = self._create_internal_user(email="billing-portal@example.com")
        BillingSubscription.objects.create(
            provider="stripe",
            status="complete",
            payment_status="paid",
            session_id="cs_portal_test",
            plan_id="growth",
            plan_name="Growth",
            billing_cycle="monthly",
            payment_method="card",
            amount_usd="399.00",
            reference="OVS-MANAGE-PORTAL",
            registration_consumed_by_email=internal_user.email,
            metadata={
                "stripe_customer_id": "cus_portal_123",
                "stripe_subscription_id": "sub_portal_123",
            },
        )

        self.client.force_authenticate(user=internal_user)
        response = self.client.post(self.billing_manage_update_session_endpoint, {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["provider"], "stripe")
        self.assertEqual(response.data["status"], "ok")
        self.assertIn("billing.stripe.com", response.data["url"])
        mock_ready.assert_called_once()
        mock_create_portal.assert_called_once()

    @override_settings(
        BILLING_QUOTA_ENFORCEMENT_ENABLED=True,
        BILLING_PLAN_STARTER_CANDIDATES_PER_MONTH=2,
    )
    def test_billing_quota_returns_candidate_usage_snapshot(self):
        user_model = get_user_model()
        internal_user = user_model.objects.create_user(
            email="hr-quota-check@example.com",
            password="StrongPass123!",
            first_name="Quota",
            last_name="Owner",
            user_type="internal",
        )

        BillingSubscription.objects.create(
            provider="sandbox",
            status="complete",
            payment_status="paid",
            plan_id="starter",
            plan_name="Starter",
            billing_cycle="monthly",
            payment_method="card",
            amount_usd="149.00",
            reference="OVS-QUOTA-SNAPSHOT",
            registration_consumed_by_email=internal_user.email,
        )

        campaign = VettingCampaign.objects.create(
            name="Quota Campaign",
            description="Quota visibility",
            status="active",
            initiated_by=internal_user,
        )

        candidate_one = Candidate.objects.create(
            first_name="Cand",
            last_name="One",
            email="quota-cand-1@example.com",
        )
        candidate_two = Candidate.objects.create(
            first_name="Cand",
            last_name="Two",
            email="quota-cand-2@example.com",
        )
        CandidateEnrollment.objects.create(campaign=campaign, candidate=candidate_one, status="invited")
        CandidateEnrollment.objects.create(campaign=campaign, candidate=candidate_two, status="invited")

        self.client.force_authenticate(user=internal_user)
        response = self.client.get(self.billing_quotas_endpoint)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "ok")
        candidate_quota = response.data["candidate"]
        self.assertEqual(candidate_quota["plan_id"], "starter")
        self.assertEqual(candidate_quota["limit"], 2)
        self.assertEqual(candidate_quota["used"], 2)
        self.assertEqual(candidate_quota["remaining"], 0)
        self.assertEqual(candidate_quota["reason"], None)

    @override_settings(
        BILLING_QUOTA_ENFORCEMENT_ENABLED=True,
        BILLING_PLAN_STARTER_CANDIDATES_PER_MONTH=2,
    )
    def test_billing_quota_uses_org_owned_subscription_and_org_usage_scope(self):
        internal_user = self._create_internal_user(email="hr-org-quota@example.com")
        scoped_org = self._create_org_membership(
            internal_user,
            code="billing-org-quota",
            name="Billing Org Quota",
        )
        other_org = Organization.objects.create(
            code="billing-org-other",
            name="Billing Org Other",
            organization_type="agency",
            is_active=True,
        )

        BillingSubscription.objects.create(
            provider="sandbox",
            organization=scoped_org,
            status="complete",
            payment_status="paid",
            plan_id="starter",
            plan_name="Starter",
            billing_cycle="monthly",
            payment_method="card",
            amount_usd="149.00",
            reference="OVS-ORG-QUOTA-SNAPSHOT",
        )
        BillingSubscription.objects.create(
            provider="sandbox",
            status="complete",
            payment_status="paid",
            plan_id="growth",
            plan_name="Growth",
            billing_cycle="monthly",
            payment_method="card",
            amount_usd="399.00",
            reference="OVS-LEGACY-QUOTA-FALLBACK",
            registration_consumed_by_email=internal_user.email,
        )

        other_owner = self._create_internal_user(email="other-owner@example.com")
        scoped_campaign = VettingCampaign.objects.create(
            organization=scoped_org,
            name="Scoped Quota Campaign",
            description="Org scoped quota visibility",
            status="active",
            initiated_by=other_owner,
        )
        offscope_campaign = VettingCampaign.objects.create(
            organization=other_org,
            name="Offscope Quota Campaign",
            description="Should not count in scoped org usage",
            status="active",
            initiated_by=other_owner,
        )

        candidate_one = Candidate.objects.create(
            first_name="Scoped",
            last_name="One",
            email="scoped-cand-1@example.com",
        )
        candidate_two = Candidate.objects.create(
            first_name="Scoped",
            last_name="Two",
            email="scoped-cand-2@example.com",
        )
        candidate_three = Candidate.objects.create(
            first_name="Offscope",
            last_name="Three",
            email="offscope-cand-3@example.com",
        )
        CandidateEnrollment.objects.create(campaign=scoped_campaign, candidate=candidate_one, status="invited")
        CandidateEnrollment.objects.create(campaign=scoped_campaign, candidate=candidate_two, status="invited")
        CandidateEnrollment.objects.create(campaign=offscope_campaign, candidate=candidate_three, status="invited")

        self.client.force_authenticate(user=internal_user)
        response = self.client.get(
            self.billing_quotas_endpoint,
            HTTP_X_ACTIVE_ORGANIZATION_ID=str(scoped_org.id),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        candidate_quota = response.data["candidate"]
        self.assertEqual(candidate_quota["plan_id"], "starter")
        self.assertEqual(candidate_quota["limit"], 2)
        self.assertEqual(candidate_quota["used"], 2)
        self.assertEqual(candidate_quota["remaining"], 0)
        self.assertTrue(str(candidate_quota["scope"]).startswith("organization:"))

    @override_settings(
        BILLING_QUOTA_ENFORCEMENT_ENABLED=True,
        BILLING_PLAN_STARTER_CANDIDATES_PER_MONTH=2,
        BILLING_PLAN_GROWTH_CANDIDATES_PER_MONTH=5,
    )
    def test_billing_quota_isolated_by_active_organization_context(self):
        internal_user = self._create_internal_user(email="hr-org-isolation@example.com")
        org_a = self._create_org_membership(
            internal_user,
            code="billing-org-isolation-a",
            name="Billing Org Isolation A",
            is_default=True,
        )
        org_b = self._create_org_membership(
            internal_user,
            code="billing-org-isolation-b",
            name="Billing Org Isolation B",
            is_default=False,
        )

        self._create_active_org_subscription(
            organization=org_a,
            reference="OVS-ORG-ISOLATION-A",
            plan_id="starter",
            plan_name="Starter",
        )
        self._create_active_org_subscription(
            organization=org_b,
            reference="OVS-ORG-ISOLATION-B",
            plan_id="growth",
            plan_name="Growth",
        )

        campaign_a = VettingCampaign.objects.create(
            organization=org_a,
            name="Org A Campaign",
            description="Org A usage scope",
            status="active",
            initiated_by=internal_user,
        )
        campaign_b = VettingCampaign.objects.create(
            organization=org_b,
            name="Org B Campaign",
            description="Org B usage scope",
            status="active",
            initiated_by=internal_user,
        )

        CandidateEnrollment.objects.create(
            campaign=campaign_a,
            candidate=Candidate.objects.create(
                first_name="Scoped",
                last_name="A-One",
                email="scoped-a-one@example.com",
            ),
            status="invited",
        )
        CandidateEnrollment.objects.create(
            campaign=campaign_b,
            candidate=Candidate.objects.create(
                first_name="Scoped",
                last_name="B-One",
                email="scoped-b-one@example.com",
            ),
            status="invited",
        )
        CandidateEnrollment.objects.create(
            campaign=campaign_b,
            candidate=Candidate.objects.create(
                first_name="Scoped",
                last_name="B-Two",
                email="scoped-b-two@example.com",
            ),
            status="invited",
        )

        self.client.force_authenticate(user=internal_user)

        response_org_a = self.client.get(
            self.billing_quotas_endpoint,
            HTTP_X_ACTIVE_ORGANIZATION_ID=str(org_a.id),
        )
        self.assertEqual(response_org_a.status_code, status.HTTP_200_OK)
        quota_org_a = response_org_a.data["candidate"]
        self.assertEqual(quota_org_a["plan_id"], "starter")
        self.assertEqual(quota_org_a["used"], 1)
        self.assertEqual(quota_org_a["limit"], 2)
        self.assertEqual(quota_org_a["remaining"], 1)
        self.assertEqual(str(quota_org_a["scope"]), f"organization:{org_a.id}")

        response_org_b = self.client.get(
            self.billing_quotas_endpoint,
            HTTP_X_ACTIVE_ORGANIZATION_ID=str(org_b.id),
        )
        self.assertEqual(response_org_b.status_code, status.HTTP_200_OK)
        quota_org_b = response_org_b.data["candidate"]
        self.assertEqual(quota_org_b["plan_id"], "growth")
        self.assertEqual(quota_org_b["used"], 2)
        self.assertEqual(quota_org_b["limit"], 5)
        self.assertEqual(quota_org_b["remaining"], 3)
        self.assertEqual(str(quota_org_b["scope"]), f"organization:{org_b.id}")

    @override_settings(
        BILLING_QUOTA_ENFORCEMENT_ENABLED=True,
    )
    def test_billing_quota_denies_ambiguous_legacy_fallback_for_multi_org_member(self):
        internal_user = self._create_internal_user(email="hr-org-ambiguous@example.com")
        org_a = self._create_org_membership(
            internal_user,
            code="billing-org-ambiguous-a",
            name="Billing Org Ambiguous A",
            is_default=True,
        )
        self._create_org_membership(
            internal_user,
            code="billing-org-ambiguous-b",
            name="Billing Org Ambiguous B",
            is_default=False,
        )

        BillingSubscription.objects.create(
            provider="sandbox",
            status="complete",
            payment_status="paid",
            plan_id="growth",
            plan_name="Growth",
            billing_cycle="monthly",
            payment_method="card",
            amount_usd="399.00",
            reference="OVS-LEGACY-AMBIGUOUS-ORG",
            registration_consumed_by_email=internal_user.email,
        )

        self.client.force_authenticate(user=internal_user)
        response = self.client.get(
            self.billing_quotas_endpoint,
            HTTP_X_ACTIVE_ORGANIZATION_ID=str(org_a.id),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        candidate_quota = response.data["candidate"]
        self.assertEqual(candidate_quota["reason"], "subscription_required")
        self.assertEqual(candidate_quota["plan_id"], None)
        self.assertEqual(candidate_quota["limit"], 0)
        self.assertEqual(candidate_quota["remaining"], 0)
        self.assertEqual(str(candidate_quota["scope"]), f"organization:{org_a.id}")

    @override_settings(
        BILLING_QUOTA_ENFORCEMENT_ENABLED=True,
        BILLING_PLAN_STARTER_CANDIDATES_PER_MONTH=2,
    )
    def test_billing_quota_allows_single_org_legacy_fallback_during_migration(self):
        internal_user = self._create_internal_user(email="hr-org-legacy-single@example.com")
        scoped_org = self._create_org_membership(
            internal_user,
            code="billing-org-legacy-single",
            name="Billing Org Legacy Single",
            is_default=True,
        )
        other_org = Organization.objects.create(
            code="billing-org-legacy-other",
            name="Billing Org Legacy Other",
            organization_type="agency",
            is_active=True,
        )

        BillingSubscription.objects.create(
            provider="sandbox",
            status="complete",
            payment_status="paid",
            plan_id="starter",
            plan_name="Starter",
            billing_cycle="monthly",
            payment_method="card",
            amount_usd="149.00",
            reference="OVS-LEGACY-SINGLE-ORG",
            registration_consumed_by_email=internal_user.email,
        )

        legacy_scoped_campaign = VettingCampaign.objects.create(
            organization=None,
            name="Legacy Scoped Campaign",
            description="Legacy null-org campaign for scoped owner",
            status="active",
            initiated_by=internal_user,
        )
        CandidateEnrollment.objects.create(
            campaign=legacy_scoped_campaign,
            candidate=Candidate.objects.create(
                first_name="Legacy",
                last_name="Scoped",
                email="legacy-scoped@example.com",
            ),
            status="invited",
        )

        outsider = self._create_internal_user(email="hr-org-legacy-outsider@example.com")
        OrganizationMembership.objects.create(
            user=outsider,
            organization=other_org,
            membership_role="registry_admin",
            is_active=True,
            is_default=True,
        )
        legacy_offscope_campaign = VettingCampaign.objects.create(
            organization=None,
            name="Legacy Offscope Campaign",
            description="Legacy null-org campaign for outsider",
            status="active",
            initiated_by=outsider,
        )
        CandidateEnrollment.objects.create(
            campaign=legacy_offscope_campaign,
            candidate=Candidate.objects.create(
                first_name="Legacy",
                last_name="Offscope",
                email="legacy-offscope@example.com",
            ),
            status="invited",
        )

        self.client.force_authenticate(user=internal_user)
        response = self.client.get(
            self.billing_quotas_endpoint,
            HTTP_X_ACTIVE_ORGANIZATION_ID=str(scoped_org.id),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        candidate_quota = response.data["candidate"]
        self.assertEqual(candidate_quota["reason"], None)
        self.assertEqual(candidate_quota["plan_id"], "starter")
        self.assertEqual(candidate_quota["limit"], 2)
        self.assertEqual(candidate_quota["used"], 1)
        self.assertEqual(candidate_quota["remaining"], 1)
        self.assertEqual(str(candidate_quota["scope"]), f"organization:{scoped_org.id}")

    def test_onboarding_token_management_requires_org_admin_or_platform_admin(self):
        committee_member = self._create_internal_user(email="billing-committee-denied@example.com")
        committee_group, _ = Group.objects.get_or_create(name="committee_member")
        committee_member.groups.add(committee_group)
        organization = self._create_org_membership(
            committee_member,
            code="billing-committee-denied-org",
            name="Billing Committee Denied Org",
            membership_role="member",
        )
        self._create_active_org_subscription(
            organization=organization,
            reference="OVS-ONBOARD-DENIED-COMMITTEE",
        )

        self.client.force_authenticate(user=committee_member)
        state_response = self.client.get(
            self.onboarding_state_endpoint,
            HTTP_X_ACTIVE_ORGANIZATION_ID=str(organization.id),
        )
        generate_response = self.client.post(
            self.onboarding_generate_endpoint,
            {"max_uses": 2, "expires_in_hours": 24},
            format="json",
            HTTP_X_ACTIVE_ORGANIZATION_ID=str(organization.id),
        )
        revoke_response = self.client.post(
            self.onboarding_revoke_endpoint,
            {"reason": "should_not_work"},
            format="json",
            HTTP_X_ACTIVE_ORGANIZATION_ID=str(organization.id),
        )

        self.assertEqual(state_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(generate_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(revoke_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_checkout_initiation_requires_org_admin_or_platform_admin(self):
        vetting_user = self._create_internal_user(email="billing-vetting-denied@example.com")
        vetting_group, _ = Group.objects.get_or_create(name="vetting_officer")
        vetting_user.groups.add(vetting_group)
        organization = self._create_org_membership(
            vetting_user,
            code="billing-vetting-denied-org",
            name="Billing Vetting Denied Org",
            membership_role="vetting_officer",
        )

        self.client.force_authenticate(user=vetting_user)
        response = self.client.post(
            self.sandbox_endpoint,
            {
                "plan_id": "starter",
                "plan_name": "Starter",
                "billing_cycle": "monthly",
                "payment_method": "card",
                "amount_usd": "149.00",
            },
            format="json",
            HTTP_X_ACTIVE_ORGANIZATION_ID=str(organization.id),
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_billing_governance_actions_reject_cross_org_scope_for_non_admin(self):
        org_admin = self._create_internal_user(email="billing-cross-org@example.com")
        scoped_org = self._create_org_membership(
            org_admin,
            code="billing-cross-org-a",
            name="Billing Cross Org A",
        )
        foreign_org = Organization.objects.create(
            code="billing-cross-org-b",
            name="Billing Cross Org B",
            organization_type="agency",
            is_active=True,
        )
        self._create_active_org_subscription(
            organization=scoped_org,
            reference="OVS-CROSS-ORG-ONBOARD",
        )

        self.client.force_authenticate(user=org_admin)
        onboarding_state_response = self.client.get(
            self.onboarding_state_endpoint,
            HTTP_X_ACTIVE_ORGANIZATION_ID=str(foreign_org.id),
        )
        checkout_response = self.client.post(
            self.sandbox_endpoint,
            {
                "plan_id": "starter",
                "plan_name": "Starter",
                "billing_cycle": "monthly",
                "payment_method": "card",
                "amount_usd": "149.00",
            },
            format="json",
            HTTP_X_ACTIVE_ORGANIZATION_ID=str(foreign_org.id),
        )

        self.assertEqual(onboarding_state_response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(checkout_response.status_code, status.HTTP_404_NOT_FOUND)

    def test_platform_admin_can_manage_onboarding_with_explicit_org_scope(self):
        platform_admin = get_user_model().objects.create_user(
            email="billing-platform-admin@example.com",
            password="StrongPass123!",
            first_name="Platform",
            last_name="Admin",
            user_type="admin",
            is_staff=True,
            is_superuser=True,
        )
        owner = self._create_internal_user(email="billing-platform-owned@example.com")
        organization = self._create_org_membership(
            owner,
            code="billing-platform-admin-org",
            name="Billing Platform Admin Org",
        )
        self._create_active_org_subscription(
            organization=organization,
            reference="OVS-PLATFORM-ADMIN-ONBOARD",
        )

        self.client.force_authenticate(user=platform_admin)
        state_response = self.client.get(
            f"{self.onboarding_state_endpoint}?organization_id={organization.id}",
        )
        self.assertEqual(state_response.status_code, status.HTTP_200_OK)
        self.assertEqual(str(state_response.data["organization_id"]), str(organization.id))

        generate_response = self.client.post(
            f"{self.onboarding_generate_endpoint}?organization_id={organization.id}",
            {"max_uses": 2, "expires_in_hours": 24},
            format="json",
        )
        self.assertEqual(generate_response.status_code, status.HTTP_200_OK)
        self.assertIn("token", generate_response.data)

        checkout_response = self.client.post(
            f"{self.sandbox_endpoint}?organization_id={organization.id}",
            {
                "plan_id": "starter",
                "plan_name": "Starter",
                "billing_cycle": "monthly",
                "payment_method": "card",
                "amount_usd": "149.00",
            },
            format="json",
        )
        self.assertEqual(checkout_response.status_code, status.HTTP_200_OK)

    def test_onboarding_token_state_includes_org_seat_snapshot(self):
        org_admin = self._create_internal_user(email="billing-seat-state@example.com")
        organization = self._create_org_membership(
            org_admin,
            code="billing-seat-state-org",
            name="Billing Seat State Org",
        )
        subscription = self._create_active_org_subscription(
            organization=organization,
            reference="OVS-SEAT-STATE",
            plan_id="starter",
            plan_name="Starter",
        )

        self.client.force_authenticate(user=org_admin)
        state_response = self.client.get(
            self.onboarding_state_endpoint,
            HTTP_X_ACTIVE_ORGANIZATION_ID=str(organization.id),
        )

        self.assertEqual(state_response.status_code, status.HTTP_200_OK)
        self.assertEqual(str(state_response.data["organization_id"]), str(organization.id))
        self.assertTrue(state_response.data["subscription_active"])
        expected_snapshot = get_organization_seat_quota_snapshot(
            organization_id=str(organization.id),
            subscription=subscription,
        )
        self.assertEqual(state_response.data["organization_seat_limit"], expected_snapshot.limit)
        self.assertEqual(state_response.data["organization_seat_used"], expected_snapshot.used)
        self.assertEqual(state_response.data["organization_seat_remaining"], expected_snapshot.remaining)

    def test_onboarding_token_validate_success(self):
        internal_user = self._create_internal_user(email="onboarding-success@example.com")
        organization = self._create_org_membership(
            internal_user,
            code="onboarding-success",
            name="Onboarding Success Org",
        )
        self._create_active_org_subscription(
            organization=organization,
            reference="OVS-ONBOARD-SUCCESS",
        )

        self.client.force_authenticate(user=internal_user)
        issue_response = self.client.post(
            self.onboarding_generate_endpoint,
            {"max_uses": 3, "expires_in_hours": 24},
            format="json",
            HTTP_X_ACTIVE_ORGANIZATION_ID=str(organization.id),
        )
        self.assertEqual(issue_response.status_code, status.HTTP_200_OK)
        raw_token = issue_response.data["token"]

        validate_response = self.client.post(
            self.onboarding_validate_endpoint,
            {"token": raw_token, "email": "member@demo.gov"},
            format="json",
        )
        self.assertEqual(validate_response.status_code, status.HTTP_200_OK)
        self.assertEqual(validate_response.data["valid"], True)
        self.assertEqual(validate_response.data["reason"], "ok")
        self.assertEqual(str(validate_response.data["organization_id"]), str(organization.id))
        self.assertEqual(validate_response.data["remaining_uses"], 3)

    @override_settings(
        BILLING_ONBOARDING_TOKEN_VALIDATE_RATE_LIMIT_ENABLED=True,
        BILLING_ONBOARDING_TOKEN_VALIDATE_RATE_LIMIT_PER_MINUTE=1,
    )
    def test_onboarding_token_validate_rate_limited(self):
        internal_user = self._create_internal_user(email="onboarding-rate-limit@example.com")
        organization = self._create_org_membership(
            internal_user,
            code="onboarding-rate-limit",
            name="Onboarding Rate Limit Org",
        )
        self._create_active_org_subscription(
            organization=organization,
            reference="OVS-ONBOARD-RATE-LIMIT",
        )

        self.client.force_authenticate(user=internal_user)
        issue_response = self.client.post(
            self.onboarding_generate_endpoint,
            {"max_uses": 3, "expires_in_hours": 24},
            format="json",
            HTTP_X_ACTIVE_ORGANIZATION_ID=str(organization.id),
        )
        self.assertEqual(issue_response.status_code, status.HTTP_200_OK)
        raw_token = issue_response.data["token"]

        first_response = self.client.post(
            self.onboarding_validate_endpoint,
            {"token": raw_token, "email": "member@demo.gov"},
            format="json",
        )
        self.assertEqual(first_response.status_code, status.HTTP_200_OK)
        self.assertEqual(first_response.data["valid"], True)

        second_response = self.client.post(
            self.onboarding_validate_endpoint,
            {"token": raw_token, "email": "member@demo.gov"},
            format="json",
        )
        self.assertEqual(second_response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertIn("Retry-After", second_response)
        self.assertEqual(second_response.data.get("code"), "RATE_LIMITED")

    def test_onboarding_token_validate_fails_when_expired(self):
        internal_user = self._create_internal_user(email="onboarding-expired@example.com")
        organization = self._create_org_membership(
            internal_user,
            code="onboarding-expired",
            name="Onboarding Expired Org",
        )
        self._create_active_org_subscription(
            organization=organization,
            reference="OVS-ONBOARD-EXPIRED",
        )

        self.client.force_authenticate(user=internal_user)
        issue_response = self.client.post(
            self.onboarding_generate_endpoint,
            {"max_uses": 2, "expires_in_hours": 24},
            format="json",
            HTTP_X_ACTIVE_ORGANIZATION_ID=str(organization.id),
        )
        self.assertEqual(issue_response.status_code, status.HTTP_200_OK)
        raw_token = issue_response.data["token"]

        token_record = OrganizationOnboardingToken.objects.get(organization=organization, is_active=True)
        token_record.expires_at = timezone.now() - timedelta(minutes=1)
        token_record.save(update_fields=["expires_at", "updated_at"])

        validate_response = self.client.post(
            self.onboarding_validate_endpoint,
            {"token": raw_token, "email": "member@demo.gov"},
            format="json",
        )
        self.assertEqual(validate_response.status_code, status.HTTP_200_OK)
        self.assertEqual(validate_response.data["valid"], False)
        self.assertEqual(validate_response.data["reason"], "expired")

    def test_onboarding_token_validate_fails_when_max_uses_reached(self):
        internal_user = self._create_internal_user(email="onboarding-max@example.com")
        organization = self._create_org_membership(
            internal_user,
            code="onboarding-max",
            name="Onboarding Max Org",
        )
        self._create_active_org_subscription(
            organization=organization,
            reference="OVS-ONBOARD-MAX",
        )

        self.client.force_authenticate(user=internal_user)
        issue_response = self.client.post(
            self.onboarding_generate_endpoint,
            {"max_uses": 1, "expires_in_hours": 24},
            format="json",
            HTTP_X_ACTIVE_ORGANIZATION_ID=str(organization.id),
        )
        self.assertEqual(issue_response.status_code, status.HTTP_200_OK)
        raw_token = issue_response.data["token"]

        token_record = OrganizationOnboardingToken.objects.get(organization=organization, is_active=True)
        token_record.uses = 1
        token_record.save(update_fields=["uses", "updated_at"])

        validate_response = self.client.post(
            self.onboarding_validate_endpoint,
            {"token": raw_token, "email": "member@demo.gov"},
            format="json",
        )
        self.assertEqual(validate_response.status_code, status.HTTP_200_OK)
        self.assertEqual(validate_response.data["valid"], False)
        self.assertEqual(validate_response.data["reason"], "max_uses_reached")

    def test_onboarding_token_validate_fails_when_inactive(self):
        internal_user = self._create_internal_user(email="onboarding-inactive@example.com")
        organization = self._create_org_membership(
            internal_user,
            code="onboarding-inactive",
            name="Onboarding Inactive Org",
        )
        self._create_active_org_subscription(
            organization=organization,
            reference="OVS-ONBOARD-INACTIVE",
        )

        self.client.force_authenticate(user=internal_user)
        issue_response = self.client.post(
            self.onboarding_generate_endpoint,
            {"max_uses": 2, "expires_in_hours": 24},
            format="json",
            HTTP_X_ACTIVE_ORGANIZATION_ID=str(organization.id),
        )
        self.assertEqual(issue_response.status_code, status.HTTP_200_OK)
        raw_token = issue_response.data["token"]

        token_record = OrganizationOnboardingToken.objects.get(organization=organization, is_active=True)
        token_record.is_active = False
        token_record.revoked_at = timezone.now()
        token_record.revoked_reason = "manual_test_revoke"
        token_record.save(update_fields=["is_active", "revoked_at", "revoked_reason", "updated_at"])

        validate_response = self.client.post(
            self.onboarding_validate_endpoint,
            {"token": raw_token, "email": "member@demo.gov"},
            format="json",
        )
        self.assertEqual(validate_response.status_code, status.HTTP_200_OK)
        self.assertEqual(validate_response.data["valid"], False)
        self.assertEqual(validate_response.data["reason"], "inactive")

    def test_onboarding_token_validate_fails_when_subscription_inactive(self):
        internal_user = self._create_internal_user(email="onboarding-sub-inactive@example.com")
        organization = self._create_org_membership(
            internal_user,
            code="onboarding-sub-inactive",
            name="Onboarding Subscription Inactive Org",
        )
        self._create_active_org_subscription(
            organization=organization,
            reference="OVS-ONBOARD-SUB-INACTIVE",
        )

        self.client.force_authenticate(user=internal_user)
        issue_response = self.client.post(
            self.onboarding_generate_endpoint,
            {"max_uses": 2, "expires_in_hours": 24},
            format="json",
            HTTP_X_ACTIVE_ORGANIZATION_ID=str(organization.id),
        )
        self.assertEqual(issue_response.status_code, status.HTTP_200_OK)
        raw_token = issue_response.data["token"]

        subscription = BillingSubscription.objects.get(reference="OVS-ONBOARD-SUB-INACTIVE")
        subscription.status = "canceled"
        subscription.payment_status = "unpaid"
        subscription.save(update_fields=["status", "payment_status", "updated_at"])

        validate_response = self.client.post(
            self.onboarding_validate_endpoint,
            {"token": raw_token, "email": "member@demo.gov"},
            format="json",
        )
        self.assertEqual(validate_response.status_code, status.HTTP_200_OK)
        self.assertEqual(validate_response.data["valid"], False)
        self.assertEqual(validate_response.data["reason"], "subscription_inactive")

    def test_onboarding_token_generate_rotates_previous_active_token(self):
        internal_user = self._create_internal_user(email="onboarding-rotate@example.com")
        organization = self._create_org_membership(
            internal_user,
            code="onboarding-rotate",
            name="Onboarding Rotate Org",
        )
        self._create_active_org_subscription(
            organization=organization,
            reference="OVS-ONBOARD-ROTATE",
        )

        self.client.force_authenticate(user=internal_user)
        first_response = self.client.post(
            self.onboarding_generate_endpoint,
            {"max_uses": 3, "expires_in_hours": 24},
            format="json",
            HTTP_X_ACTIVE_ORGANIZATION_ID=str(organization.id),
        )
        self.assertEqual(first_response.status_code, status.HTTP_200_OK)
        first_token = OrganizationOnboardingToken.objects.get(
            organization=organization,
            is_active=True,
        )
        self.assertTrue(first_token.is_active)

        second_response = self.client.post(
            self.onboarding_generate_endpoint,
            {"max_uses": 4, "expires_in_hours": 24},
            format="json",
            HTTP_X_ACTIVE_ORGANIZATION_ID=str(organization.id),
        )
        self.assertEqual(second_response.status_code, status.HTTP_200_OK)

        first_token.refresh_from_db()
        self.assertFalse(first_token.is_active)
        self.assertTrue(
            OrganizationOnboardingToken.objects.filter(
                organization=organization,
                is_active=True,
            ).exists()
        )

    def test_onboarding_token_rotation_invalidates_previous_raw_token(self):
        internal_user = self._create_internal_user(email="onboarding-rotate-invalidates@example.com")
        organization = self._create_org_membership(
            internal_user,
            code="onboarding-rotate-invalidates",
            name="Onboarding Rotate Invalidates Org",
        )
        self._create_active_org_subscription(
            organization=organization,
            reference="OVS-ONBOARD-ROTATE-OLD",
        )

        self.client.force_authenticate(user=internal_user)
        first_response = self.client.post(
            self.onboarding_generate_endpoint,
            {"max_uses": 3, "expires_in_hours": 24},
            format="json",
            HTTP_X_ACTIVE_ORGANIZATION_ID=str(organization.id),
        )
        self.assertEqual(first_response.status_code, status.HTTP_200_OK)
        first_raw_token = first_response.data["token"]

        second_response = self.client.post(
            self.onboarding_generate_endpoint,
            {"max_uses": 3, "expires_in_hours": 24},
            format="json",
            HTTP_X_ACTIVE_ORGANIZATION_ID=str(organization.id),
        )
        self.assertEqual(second_response.status_code, status.HTTP_200_OK)

        old_validate_response = self.client.post(
            self.onboarding_validate_endpoint,
            {"token": first_raw_token, "email": "member@example.com"},
            format="json",
        )
        self.assertEqual(old_validate_response.status_code, status.HTTP_200_OK)
        self.assertEqual(old_validate_response.data["valid"], False)
        self.assertEqual(old_validate_response.data["reason"], "inactive")

    def test_onboarding_token_revoke_deactivates_active_token(self):
        internal_user = self._create_internal_user(email="onboarding-revoke@example.com")
        organization = self._create_org_membership(
            internal_user,
            code="onboarding-revoke",
            name="Onboarding Revoke Org",
        )
        self._create_active_org_subscription(
            organization=organization,
            reference="OVS-ONBOARD-REVOKE",
        )

        self.client.force_authenticate(user=internal_user)
        issue_response = self.client.post(
            self.onboarding_generate_endpoint,
            {"max_uses": 2, "expires_in_hours": 24},
            format="json",
            HTTP_X_ACTIVE_ORGANIZATION_ID=str(organization.id),
        )
        self.assertEqual(issue_response.status_code, status.HTTP_200_OK)

        revoke_response = self.client.post(
            self.onboarding_revoke_endpoint,
            {"reason": "demo_revoke"},
            format="json",
            HTTP_X_ACTIVE_ORGANIZATION_ID=str(organization.id),
        )
        self.assertEqual(revoke_response.status_code, status.HTTP_200_OK)
        self.assertEqual(revoke_response.data["has_active_token"], False)
        self.assertFalse(
            OrganizationOnboardingToken.objects.filter(
                organization=organization,
                is_active=True,
            ).exists()
        )

    def test_onboarding_token_audit_payload_excludes_raw_token_value(self):
        internal_user = self._create_internal_user(email="onboarding-audit-safety@example.com")
        organization = self._create_org_membership(
            internal_user,
            code="onboarding-audit-safe",
            name="Onboarding Audit Safe Org",
        )
        self._create_active_org_subscription(
            organization=organization,
            reference="OVS-ONBOARD-AUDIT-SAFE",
        )

        self.client.force_authenticate(user=internal_user)
        issue_response = self.client.post(
            self.onboarding_generate_endpoint,
            {"max_uses": 2, "expires_in_hours": 24},
            format="json",
            HTTP_X_ACTIVE_ORGANIZATION_ID=str(organization.id),
        )
        self.assertEqual(issue_response.status_code, status.HTTP_200_OK)
        raw_token = issue_response.data["token"]

        audit = (
            AuditLog.objects.filter(
                entity_type="OrganizationOnboardingToken",
            )
            .order_by("-created_at")
            .first()
        )
        self.assertIsNotNone(audit)
        audit_payload = str(audit.changes)
        self.assertNotIn(raw_token, audit_payload)
        self.assertIn("token_preview", audit_payload)


    @override_settings(
        STRIPE_SECRET_KEY="",
        STRIPE_WEBHOOK_SECRET="",
        EXCHANGE_RATE_API_URL="",
        BILLING_SUBSCRIPTION_VERIFY_RATE_LIMIT_ENABLED=True,
        BILLING_SUBSCRIPTION_VERIFY_RATE_LIMIT_PER_MINUTE=30,
    )
    def test_billing_health_reports_runtime_flags(self):
        response = self.client.get(self.billing_health_endpoint)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "ok")
        self.assertIn("stripe", response.data)
        self.assertIn("paystack", response.data)
        self.assertIn("exchange_rate", response.data)
        self.assertIn("subscription_verify_rate_limit", response.data)
        self.assertIn("access", response.data)
        self.assertEqual(response.data["access"]["staff_required"], False)
        self.assertEqual(response.data["exchange_rate"]["api_url_configured"], False)
        self.assertEqual(response.data["exchange_rate"]["fallback_rate"], 1.0)
        self.assertEqual(response.data["subscription_verify_rate_limit"]["enabled"], True)
        self.assertEqual(response.data["subscription_verify_rate_limit"]["per_minute"], 30)

    @override_settings(
        PAYSTACK_CURRENCY="USD",
        PAYSTACK_USD_EXCHANGE_RATE=15.0,
        EXCHANGE_RATE_API_URL="https://fx.example.com/latest/{base}?target={target}",
    )
    def test_billing_exchange_rate_identity_when_target_is_usd(self):
        response = self.client.get(self.billing_exchange_rate_endpoint)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "ok")
        self.assertEqual(response.data["base"], "USD")
        self.assertEqual(response.data["target"], "USD")
        self.assertEqual(response.data["rate"], 1.0)
        self.assertEqual(response.data["source"], "identity")

    @override_settings(
        PAYSTACK_CURRENCY="GHS",
        PAYSTACK_USD_EXCHANGE_RATE=15.0,
        EXCHANGE_RATE_API_URL="",
    )
    def test_billing_exchange_rate_fallback_when_api_not_configured(self):
        response = self.client.get(self.billing_exchange_rate_endpoint)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "ok")
        self.assertEqual(response.data["base"], "USD")
        self.assertEqual(response.data["target"], "GHS")
        self.assertEqual(response.data["rate"], 15.0)
        self.assertEqual(response.data["source"], "fallback")

    @override_settings(
        PAYSTACK_CURRENCY="GHS",
        PAYSTACK_USD_EXCHANGE_RATE=15.0,
        EXCHANGE_RATE_API_URL="https://fx.example.com/latest/{base}?target={target}",
    )
    @patch("apps.billing.views.requests.get")
    def test_billing_exchange_rate_uses_configured_api(self, mock_get):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "conversion_rates": {
                "GHS": 20.0,
            },
        }
        mock_get.return_value = mock_response

        response = self.client.get(self.billing_exchange_rate_endpoint)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "ok")
        self.assertEqual(response.data["base"], "USD")
        self.assertEqual(response.data["target"], "GHS")
        self.assertEqual(response.data["rate"], 20.0)
        self.assertEqual(response.data["source"], "api_live")
        mock_get.assert_called_once()

    @override_settings(
        PAYSTACK_CURRENCY="GHS",
        PAYSTACK_USD_EXCHANGE_RATE=15.0,
        EXCHANGE_RATE_API_URL="https://fx.example.com/latest/{base}?target={target}",
    )
    @patch("apps.billing.views.requests.get")
    def test_billing_exchange_rate_uses_cache_after_live_fetch(self, mock_get):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "conversion_rates": {
                "GHS": 19.5,
            },
        }
        mock_get.return_value = mock_response

        first_response = self.client.get(self.billing_exchange_rate_endpoint)
        second_response = self.client.get(self.billing_exchange_rate_endpoint)

        self.assertEqual(first_response.status_code, status.HTTP_200_OK)
        self.assertEqual(first_response.data["rate"], 19.5)
        self.assertEqual(first_response.data["source"], "api_live")

        self.assertEqual(second_response.status_code, status.HTTP_200_OK)
        self.assertEqual(second_response.data["rate"], 19.5)
        self.assertEqual(second_response.data["source"], "api_cache")

        mock_get.assert_called_once()

    @override_settings(
        STRIPE_SECRET_KEY="sk_test_123",
        STRIPE_WEBHOOK_SECRET="whsec_test_123",
    )
    def test_billing_health_reflects_stripe_configuration(self):
        response = self.client.get(self.billing_health_endpoint)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["stripe"]["secret_key_configured"], True)
        self.assertEqual(response.data["stripe"]["webhook_secret_configured"], True)
        self.assertIn("secret_key_configured", response.data["paystack"])

    @override_settings(
        PAYSTACK_CURRENCY="GHS",
        PAYSTACK_USD_EXCHANGE_RATE=15.0,
        EXCHANGE_RATE_API_URL="https://fx.example.com/latest/{base}?target={target}",
        EXCHANGE_RATE_API_TIMEOUT_SECONDS=5,
        EXCHANGE_RATE_CACHE_TTL_SECONDS=1200,
    )
    def test_billing_health_reports_exchange_rate_configuration(self):
        response = self.client.get(self.billing_health_endpoint)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["exchange_rate"]["api_url_configured"], True)
        self.assertEqual(response.data["exchange_rate"]["fallback_rate"], 15.0)
        self.assertEqual(response.data["exchange_rate"]["timeout_seconds"], 5)
        self.assertEqual(response.data["exchange_rate"]["cache_ttl_seconds"], 1200)

    @override_settings(BILLING_HEALTH_REQUIRE_STAFF=True)
    def test_billing_health_requires_staff_when_enabled(self):
        anonymous_response = self.client.get(self.billing_health_endpoint)
        self.assertEqual(anonymous_response.status_code, status.HTTP_401_UNAUTHORIZED)

        user_model = get_user_model()
        user = user_model.objects.create_user(
            email="hr-health-check@example.com",
            password="StrongPass123!",
            first_name="Health",
            last_name="Checker",
            user_type="internal",
        )

        self.client.force_authenticate(user=user)
        non_staff_response = self.client.get(self.billing_health_endpoint)
        self.assertEqual(non_staff_response.status_code, status.HTTP_403_FORBIDDEN)

        user.is_staff = True
        user.save(update_fields=["is_staff"])

        self.client.force_authenticate(user=user)
        staff_response = self.client.get(self.billing_health_endpoint)
        self.assertEqual(staff_response.status_code, status.HTTP_200_OK)

    def test_confirm_subscription_requires_authentication(self):
        response = self.client.post(
            self.sandbox_endpoint,
            {
                "plan_id": "growth",
                "plan_name": "Growth",
                "billing_cycle": "monthly",
                "payment_method": "card",
                "amount_usd": "399.00",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_confirm_subscription_binds_authenticated_workspace_email(self):
        internal_user = self._create_internal_user(email="billing-auth-confirm@example.com")
        organization = self._create_org_membership(
            internal_user,
            code="billing-auth-confirm-org",
            name="Billing Auth Confirm Org",
        )
        self.client.force_authenticate(user=internal_user)

        response = self.client.post(
            self.sandbox_endpoint,
            {
                "plan_id": "starter",
                "plan_name": "Starter",
                "billing_cycle": "monthly",
                "payment_method": "card",
                "amount_usd": "149.00",
            },
            format="json",
            HTTP_X_ACTIVE_ORGANIZATION_ID=str(organization.id),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ticket = response.data["ticket"]
        persisted = BillingSubscription.objects.get(provider="sandbox", reference=ticket["reference"])
        self.assertEqual(persisted.registration_consumed_by_email, internal_user.email)
        self.assertIsNotNone(persisted.registration_consumed_at)
        self.assertEqual(persisted.organization_id, organization.id)

    def test_confirm_subscription_validates_payment_method(self):
        _user, organization = self._authenticate_checkout_actor(
            email="billing-confirm-validation@example.com",
            code="billing-confirm-validation-org",
            name="Billing Confirm Validation Org",
        )

        response = self.client.post(
            self.sandbox_endpoint,
            {
                "plan_id": "growth",
                "plan_name": "Growth",
                "billing_cycle": "monthly",
                "payment_method": "crypto",
                "amount_usd": "399.00",
            },
            format="json",
            HTTP_X_ACTIVE_ORGANIZATION_ID=str(organization.id),
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("payment_method", response.data)

    @override_settings(BILLING_SUBSCRIPTION_TICKET_TTL_HOURS=1)
    def test_confirm_subscription_respects_ttl_setting(self):
        _user, organization = self._authenticate_checkout_actor(
            email="billing-confirm-ttl@example.com",
            code="billing-confirm-ttl-org",
            name="Billing Confirm TTL Org",
        )

        response = self.client.post(
            self.sandbox_endpoint,
            {
                "plan_id": "starter",
                "plan_name": "Starter",
                "billing_cycle": "annual",
                "payment_method": "bank_transfer",
                "amount_usd": "1490.00",
            },
            format="json",
            HTTP_X_ACTIVE_ORGANIZATION_ID=str(organization.id),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ticket = response.data["ticket"]
        ttl_ms = ticket["expiresAt"] - ticket["confirmedAt"]
        self.assertGreaterEqual(ttl_ms, 3_590_000)
        self.assertLessEqual(ttl_ms, 3_610_000)

    def test_confirm_subscription_requires_active_organization_context(self):
        internal_user = self._create_internal_user(email="billing-confirm-no-org@example.com")
        self.client.force_authenticate(user=internal_user)

        response = self.client.post(
            self.sandbox_endpoint,
            {
                "plan_id": "starter",
                "plan_name": "Starter",
                "billing_cycle": "monthly",
                "payment_method": "card",
                "amount_usd": "149.00",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("active organization", str(response.data).lower())
        self.assertEqual(response.data.get("code"), "ORG_SETUP_REQUIRED")
        self.assertEqual(response.data.get("setup_path"), "/organization/setup")

    def test_onboarding_token_state_requires_active_organization_context(self):
        internal_user = self._create_internal_user(email="billing-onboarding-no-org@example.com")
        self.client.force_authenticate(user=internal_user)

        response = self.client.get(self.onboarding_state_endpoint)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data.get("code"), "ORG_SETUP_REQUIRED")
        self.assertEqual(response.data.get("setup_path"), "/organization/setup")

    def test_subscription_access_verify_returns_valid_ticket(self):
        BillingSubscription.objects.create(
            provider="sandbox",
            status="complete",
            payment_status="paid",
            plan_id="growth",
            plan_name="Growth",
            billing_cycle="monthly",
            payment_method="card",
            amount_usd="399.00",
            reference="OVS-VALID-TICKET",
        )

        response = self.client.post(
            self.subscription_access_verify_endpoint,
            {"reference": "OVS-VALID-TICKET"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["valid"])
        self.assertEqual(response.data["reason"], "ok")
        self.assertEqual(response.data["reference"], "OVS-VALID-TICKET")

    def test_subscription_access_verify_returns_already_consumed(self):
        BillingSubscription.objects.create(
            provider="sandbox",
            status="complete",
            payment_status="paid",
            plan_id="growth",
            plan_name="Growth",
            billing_cycle="monthly",
            payment_method="card",
            amount_usd="399.00",
            reference="OVS-CONSUMED-TICKET",
            registration_consumed_at=timezone.now(),
            registration_consumed_by_email="hr@example.com",
        )

        response = self.client.post(
            self.subscription_access_verify_endpoint,
            {"reference": "OVS-CONSUMED-TICKET"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["valid"])
        self.assertEqual(response.data["reason"], "already_consumed")

    def test_subscription_access_verify_returns_not_found(self):
        response = self.client.post(
            self.subscription_access_verify_endpoint,
            {"reference": "OVS-NOT-FOUND"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["valid"])
        self.assertEqual(response.data["reason"], "not_found")


    @override_settings(
        BILLING_SUBSCRIPTION_VERIFY_RATE_LIMIT_ENABLED=True,
        BILLING_SUBSCRIPTION_VERIFY_RATE_LIMIT_PER_MINUTE=1,
    )
    def test_subscription_access_verify_rate_limited(self):
        BillingSubscription.objects.create(
            provider="sandbox",
            status="complete",
            payment_status="paid",
            plan_id="growth",
            plan_name="Growth",
            billing_cycle="monthly",
            payment_method="card",
            amount_usd="399.00",
            reference="OVS-RATE-LIMIT",
        )

        first = self.client.post(
            self.subscription_access_verify_endpoint,
            {"reference": "OVS-RATE-LIMIT"},
            format="json",
            REMOTE_ADDR="10.10.10.10",
        )
        second = self.client.post(
            self.subscription_access_verify_endpoint,
            {"reference": "OVS-RATE-LIMIT"},
            format="json",
            REMOTE_ADDR="10.10.10.10",
        )

        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(second.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertIn("Retry-After", second)

    @patch("apps.billing.views.log_event", return_value=True)
    def test_subscription_access_verify_logs_audit(self, mock_log_event):
        BillingSubscription.objects.create(
            provider="sandbox",
            status="complete",
            payment_status="paid",
            plan_id="growth",
            plan_name="Growth",
            billing_cycle="monthly",
            payment_method="card",
            amount_usd="399.00",
            reference="OVS-AUDIT",
        )

        response = self.client.post(
            self.subscription_access_verify_endpoint,
            {"reference": "OVS-AUDIT"},
            format="json",
            REMOTE_ADDR="10.0.0.15",
            HTTP_USER_AGENT="billing-test-agent",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(mock_log_event.called)
        kwargs = mock_log_event.call_args.kwargs
        self.assertEqual(kwargs["entity_type"], "BillingSubscriptionAccess")
        self.assertEqual(kwargs["entity_id"], "OVS-AUDIT")
        self.assertEqual(kwargs["changes"]["event"], "subscription_access_verify")
        self.assertEqual(kwargs["changes"]["reason"], "ok")
        self.assertEqual(kwargs["changes"]["rate_limited"], False)

    def test_checkout_session_create_requires_authentication(self):
        stripe_response = self.client.post(
            self.stripe_checkout_endpoint,
            {
                "plan_id": "growth",
                "plan_name": "Growth",
                "billing_cycle": "monthly",
                "amount_usd": "399.00",
            },
            format="json",
        )
        paystack_response = self.client.post(
            self.paystack_checkout_endpoint,
            {
                "plan_id": "growth",
                "plan_name": "Growth",
                "billing_cycle": "monthly",
                "amount_usd": "399.00",
                "customer_email": "billing-paystack@example.com",
            },
            format="json",
        )

        self.assertEqual(stripe_response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(paystack_response.status_code, status.HTTP_401_UNAUTHORIZED)

    @override_settings(STRIPE_SECRET_KEY="")
    def test_stripe_checkout_requires_secret_key(self):
        _user, organization = self._authenticate_checkout_actor(
            email="billing-stripe-key@example.com",
            code="billing-stripe-key-org",
            name="Billing Stripe Key Org",
        )

        response = self.client.post(
            self.stripe_checkout_endpoint,
            {
                "plan_id": "growth",
                "plan_name": "Growth",
                "billing_cycle": "monthly",
                "amount_usd": "399.00",
            },
            format="json",
            HTTP_X_ACTIVE_ORGANIZATION_ID=str(organization.id),
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @override_settings(PAYSTACK_SECRET_KEY="")
    def test_paystack_checkout_requires_secret_key(self):
        _user, organization = self._authenticate_checkout_actor(
            email="billing-paystack-key@example.com",
            code="billing-paystack-key-org",
            name="Billing Paystack Key Org",
        )

        response = self.client.post(
            self.paystack_checkout_endpoint,
            {
                "plan_id": "growth",
                "plan_name": "Growth",
                "billing_cycle": "monthly",
                "amount_usd": "399.00",
                "customer_email": "billing-paystack@example.com",
            },
            format="json",
            HTTP_X_ACTIVE_ORGANIZATION_ID=str(organization.id),
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @override_settings(PAYSTACK_SECRET_KEY="sk_test_paystack")
    @patch("apps.billing.views._paystack_initialize_transaction")
    def test_paystack_checkout_session_create(self, mock_initialize):
        mock_initialize.return_value = {
            "authorization_url": "https://checkout.paystack.com/psk_test_123",
            "access_code": "psk_access_123",
            "reference": "OVS-PAYSTACK-TEST-123",
        }
        _user, organization = self._authenticate_checkout_actor(
            email="billing-paystack-create@example.com",
            code="billing-paystack-create-org",
            name="Billing Paystack Create Org",
        )

        response = self.client.post(
            self.paystack_checkout_endpoint,
            {
                "plan_id": "growth",
                "plan_name": "Growth",
                "billing_cycle": "monthly",
                "amount_usd": "399.00",
                "customer_email": "billing-paystack@example.com",
                "success_url": "http://localhost:3000/billing/success?next=%2Fregister",
                "cancel_url": "http://localhost:3000/billing/cancel?next=%2Fregister",
            },
            format="json",
            HTTP_X_ACTIVE_ORGANIZATION_ID=str(organization.id),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["provider"], "paystack")
        self.assertEqual(response.data["reference"], "OVS-PAYSTACK-TEST-123")
        self.assertIn("checkout_url", response.data)
        mock_initialize.assert_called_once()
        initialize_payload = mock_initialize.call_args.args[0]
        self.assertEqual(initialize_payload["channels"], ["card"])
        self.assertEqual(initialize_payload["metadata"]["payment_method"], "card")

        persisted = BillingSubscription.objects.get(provider="paystack", session_id="OVS-PAYSTACK-TEST-123")
        self.assertEqual(persisted.status, "open")
        self.assertEqual(persisted.payment_status, "pending")
        self.assertEqual(persisted.payment_method, "card")

    @override_settings(PAYSTACK_SECRET_KEY="sk_test_paystack")
    @patch("apps.billing.views._paystack_initialize_transaction")
    def test_paystack_checkout_mobile_money_sets_channel_and_payment_method(self, mock_initialize):
        mock_initialize.return_value = {
            "authorization_url": "https://checkout.paystack.com/psk_mobile_money_123",
            "access_code": "psk_access_mobile_money_123",
            "reference": "OVS-PAYSTACK-MOMO-TEST-123",
        }
        _user, organization = self._authenticate_checkout_actor(
            email="billing-paystack-mobile-money@example.com",
            code="billing-paystack-mobile-money-org",
            name="Billing Paystack Mobile Money Org",
        )

        response = self.client.post(
            self.paystack_checkout_endpoint,
            {
                "plan_id": "growth",
                "plan_name": "Growth",
                "billing_cycle": "monthly",
                "payment_method": "mobile_money",
                "amount_usd": "399.00",
                "customer_email": "billing-paystack@example.com",
                "success_url": "http://localhost:3000/billing/success?next=%2Fregister",
                "cancel_url": "http://localhost:3000/billing/cancel?next=%2Fregister",
            },
            format="json",
            HTTP_X_ACTIVE_ORGANIZATION_ID=str(organization.id),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["provider"], "paystack")
        self.assertEqual(response.data["reference"], "OVS-PAYSTACK-MOMO-TEST-123")
        mock_initialize.assert_called_once()

        initialize_payload = mock_initialize.call_args.args[0]
        self.assertEqual(initialize_payload["channels"], ["mobile_money"])
        self.assertEqual(initialize_payload["metadata"]["payment_method"], "mobile_money")

        persisted = BillingSubscription.objects.get(provider="paystack", session_id="OVS-PAYSTACK-MOMO-TEST-123")
        self.assertEqual(persisted.payment_method, "mobile_money")
        self.assertEqual(persisted.payment_status, "pending")

    @override_settings(PAYSTACK_SECRET_KEY="sk_test_paystack")
    @patch("apps.billing.views._paystack_initialize_transaction")
    def test_paystack_checkout_bank_transfer_sets_channel_and_payment_method(self, mock_initialize):
        mock_initialize.return_value = {
            "authorization_url": "https://checkout.paystack.com/psk_bank_transfer_123",
            "access_code": "psk_access_bank_transfer_123",
            "reference": "OVS-PAYSTACK-BANK-TEST-123",
        }
        _user, organization = self._authenticate_checkout_actor(
            email="billing-paystack-bank-transfer@example.com",
            code="billing-paystack-bank-transfer-org",
            name="Billing Paystack Bank Transfer Org",
        )

        response = self.client.post(
            self.paystack_checkout_endpoint,
            {
                "plan_id": "growth",
                "plan_name": "Growth",
                "billing_cycle": "monthly",
                "payment_method": "bank_transfer",
                "amount_usd": "399.00",
                "customer_email": "billing-paystack@example.com",
                "success_url": "http://localhost:3000/billing/success?next=%2Fregister",
                "cancel_url": "http://localhost:3000/billing/cancel?next=%2Fregister",
            },
            format="json",
            HTTP_X_ACTIVE_ORGANIZATION_ID=str(organization.id),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["provider"], "paystack")
        self.assertEqual(response.data["reference"], "OVS-PAYSTACK-BANK-TEST-123")
        mock_initialize.assert_called_once()

        initialize_payload = mock_initialize.call_args.args[0]
        self.assertEqual(initialize_payload["channels"], ["bank_transfer"])
        self.assertEqual(initialize_payload["metadata"]["payment_method"], "bank_transfer")

        persisted = BillingSubscription.objects.get(provider="paystack", session_id="OVS-PAYSTACK-BANK-TEST-123")
        self.assertEqual(persisted.payment_method, "bank_transfer")
        self.assertEqual(persisted.payment_status, "pending")

    @override_settings(
        PAYSTACK_SECRET_KEY="sk_test_paystack",
        PAYSTACK_CURRENCY="GHS",
        PAYSTACK_USD_EXCHANGE_RATE=15.0,
        EXCHANGE_RATE_API_URL="",
    )
    @patch("apps.billing.views._paystack_initialize_transaction")
    def test_paystack_checkout_converts_usd_amount_when_currency_is_ghs(self, mock_initialize):
        mock_initialize.return_value = {
            "authorization_url": "https://checkout.paystack.com/psk_ghs_123",
            "access_code": "psk_access_ghs_123",
            "reference": "OVS-PAYSTACK-GHS-TEST-123",
        }
        _user, organization = self._authenticate_checkout_actor(
            email="billing-paystack-ghs@example.com",
            code="billing-paystack-ghs-org",
            name="Billing Paystack GHS Org",
        )

        response = self.client.post(
            self.paystack_checkout_endpoint,
            {
                "plan_id": "growth",
                "plan_name": "Growth",
                "billing_cycle": "monthly",
                "payment_method": "card",
                "amount_usd": "399.00",
                "customer_email": "billing-paystack@example.com",
                "success_url": "http://localhost:3000/billing/success?next=%2Fregister",
                "cancel_url": "http://localhost:3000/billing/cancel?next=%2Fregister",
            },
            format="json",
            HTTP_X_ACTIVE_ORGANIZATION_ID=str(organization.id),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        initialize_payload = mock_initialize.call_args.args[0]
        self.assertEqual(initialize_payload["currency"], "GHS")
        self.assertEqual(initialize_payload["amount"], 598500)
        self.assertEqual(initialize_payload["metadata"]["amount_usd"], "399.00")

        persisted = BillingSubscription.objects.get(provider="paystack", session_id="OVS-PAYSTACK-GHS-TEST-123")
        self.assertEqual(float(persisted.amount_usd), 399.0)

    @override_settings(
        PAYSTACK_SECRET_KEY="sk_test_paystack",
        PAYSTACK_CURRENCY="GHS",
        PAYSTACK_USD_EXCHANGE_RATE=15.0,
        EXCHANGE_RATE_API_URL="https://fx.example.com/latest/{base}?target={target}",
    )
    @patch("apps.billing.views.requests.get")
    @patch("apps.billing.views._paystack_initialize_transaction")
    def test_paystack_checkout_uses_exchange_rate_api_when_configured(self, mock_initialize, mock_get):
        mock_initialize.return_value = {
            "authorization_url": "https://checkout.paystack.com/psk_ghs_live_123",
            "access_code": "psk_access_ghs_live_123",
            "reference": "OVS-PAYSTACK-GHS-LIVE-TEST-123",
        }

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "result": "success",
            "conversion_rates": {
                "GHS": 20.0,
            },
        }
        mock_get.return_value = mock_response
        _user, organization = self._authenticate_checkout_actor(
            email="billing-paystack-fx@example.com",
            code="billing-paystack-fx-org",
            name="Billing Paystack FX Org",
        )

        response = self.client.post(
            self.paystack_checkout_endpoint,
            {
                "plan_id": "growth",
                "plan_name": "Growth",
                "billing_cycle": "monthly",
                "payment_method": "card",
                "amount_usd": "399.00",
                "customer_email": "billing-paystack@example.com",
                "success_url": "http://localhost:3000/billing/success?next=%2Fregister",
                "cancel_url": "http://localhost:3000/billing/cancel?next=%2Fregister",
            },
            format="json",
            HTTP_X_ACTIVE_ORGANIZATION_ID=str(organization.id),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_get.assert_called_once()
        initialize_payload = mock_initialize.call_args.args[0]
        self.assertEqual(initialize_payload["currency"], "GHS")
        self.assertEqual(initialize_payload["amount"], 798000)
        self.assertEqual(initialize_payload["metadata"]["amount_usd"], "399.00")

    @override_settings(PAYSTACK_SECRET_KEY="sk_test_paystack")
    @patch("apps.billing.views._paystack_verify_transaction")
    def test_paystack_confirm_issues_ticket(self, mock_verify):
        mock_verify.return_value = {
            "reference": "OVS-PAYSTACK-VERIFY-123",
            "status": "success",
            "amount": 39900,
            "channel": "card",
            "customer": {"email": "billing-paystack@example.com"},
            "metadata": {
                "plan_id": "growth",
                "plan_name": "Growth",
                "billing_cycle": "monthly",
                "amount_usd": "399.00",
            },
        }

        response = self.client.post(
            self.paystack_confirm_endpoint,
            {"reference": "OVS-PAYSTACK-VERIFY-123"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["provider"], "paystack")
        self.assertEqual(response.data["paystack_reference"], "OVS-PAYSTACK-VERIFY-123")
        self.assertIn("ticket", response.data)
        self.assertEqual(response.data["ticket"]["amountUsd"], 399.0)

        persisted = BillingSubscription.objects.get(provider="paystack", session_id="OVS-PAYSTACK-VERIFY-123")
        self.assertEqual(persisted.status, "complete")
        self.assertEqual(persisted.payment_status, "paid")

    @override_settings(PAYSTACK_SECRET_KEY="sk_test_paystack")
    @patch("apps.billing.views._paystack_verify_transaction")
    def test_paystack_confirm_preserves_mobile_money_payment_method(self, mock_verify):
        mock_verify.return_value = {
            "reference": "OVS-PAYSTACK-VERIFY-MOMO-123",
            "status": "success",
            "amount": 39900,
            "channel": "mobile_money",
            "customer": {"email": "billing-paystack@example.com"},
            "metadata": {
                "plan_id": "growth",
                "plan_name": "Growth",
                "billing_cycle": "monthly",
                "amount_usd": "399.00",
                "payment_method": "mobile_money",
            },
        }

        response = self.client.post(
            self.paystack_confirm_endpoint,
            {"reference": "OVS-PAYSTACK-VERIFY-MOMO-123"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["ticket"]["paymentMethod"], "mobile_money")

        persisted = BillingSubscription.objects.get(provider="paystack", session_id="OVS-PAYSTACK-VERIFY-MOMO-123")
        self.assertEqual(persisted.status, "complete")
        self.assertEqual(persisted.payment_status, "paid")
        self.assertEqual(persisted.payment_method, "mobile_money")

    @override_settings(
        PAYSTACK_SECRET_KEY="sk_test_paystack",
        BILLING_CHECKOUT_CONFIRM_RATE_LIMIT_ENABLED=True,
        BILLING_CHECKOUT_CONFIRM_RATE_LIMIT_PER_MINUTE=1,
    )
    @patch("apps.billing.views._paystack_verify_transaction")
    def test_paystack_confirm_rate_limited(self, mock_verify):
        mock_verify.return_value = {
            "reference": "OVS-PAYSTACK-VERIFY-RATE-LIMIT-123",
            "status": "success",
            "amount": 39900,
            "channel": "card",
            "customer": {"email": "billing-paystack@example.com"},
            "metadata": {
                "plan_id": "growth",
                "plan_name": "Growth",
                "billing_cycle": "monthly",
                "amount_usd": "399.00",
            },
        }

        first = self.client.post(
            self.paystack_confirm_endpoint,
            {"reference": "OVS-PAYSTACK-VERIFY-RATE-LIMIT-123"},
            format="json",
            REMOTE_ADDR="10.1.1.50",
        )
        second = self.client.post(
            self.paystack_confirm_endpoint,
            {"reference": "OVS-PAYSTACK-VERIFY-RATE-LIMIT-123"},
            format="json",
            REMOTE_ADDR="10.1.1.50",
        )

        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(second.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(second.data.get("code"), "RATE_LIMITED")
        self.assertIn("Retry-After", second)
        self.assertEqual(mock_verify.call_count, 1)

    @override_settings(PAYSTACK_SECRET_KEY="sk_test_paystack")
    @patch("apps.billing.views._paystack_verify_transaction")
    def test_paystack_confirm_prefers_provider_metadata_organization(self, mock_verify):
        metadata_org = Organization.objects.create(
            code="paystack-meta-org",
            name="Paystack Metadata Org",
            organization_type="agency",
            is_active=True,
        )
        request_org = Organization.objects.create(
            code="paystack-request-org",
            name="Paystack Request Org",
            organization_type="agency",
            is_active=True,
        )
        mock_verify.return_value = {
            "reference": "OVS-PAYSTACK-VERIFY-META-ORG-123",
            "status": "success",
            "amount": 39900,
            "channel": "card",
            "customer": {"email": "billing-paystack@example.com"},
            "metadata": {
                "plan_id": "growth",
                "plan_name": "Growth",
                "billing_cycle": "monthly",
                "amount_usd": "399.00",
                "organization_id": str(metadata_org.id),
            },
        }

        response = self.client.post(
            self.paystack_confirm_endpoint,
            {"reference": "OVS-PAYSTACK-VERIFY-META-ORG-123"},
            format="json",
            HTTP_X_ACTIVE_ORGANIZATION_ID=str(request_org.id),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        persisted = BillingSubscription.objects.get(
            provider="paystack",
            session_id="OVS-PAYSTACK-VERIFY-META-ORG-123",
        )
        self.assertEqual(persisted.organization_id, metadata_org.id)

    @override_settings(PAYSTACK_SECRET_KEY="sk_test_paystack")
    @patch("apps.billing.views._paystack_verify_transaction")
    def test_paystack_confirm_returns_structured_failure_payload(self, mock_verify):
        BillingSubscription.objects.create(
            provider="paystack",
            status="open",
            payment_status="pending",
            session_id="OVS-PAYSTACK-VERIFY-FAILED-123",
            plan_id="growth",
            plan_name="Growth",
            billing_cycle="monthly",
            payment_method="card",
            amount_usd="399.00",
            reference="OVS-PAYSTACK-VERIFY-FAILED-123",
            checkout_url="https://checkout.paystack.com/OVS-PAYSTACK-VERIFY-FAILED-123",
        )

        mock_verify.return_value = {
            "reference": "OVS-PAYSTACK-VERIFY-FAILED-123",
            "status": "abandoned",
            "gateway_response": "The transaction was not completed",
            "amount": 39900,
            "channel": "card",
            "customer": {"email": "billing-paystack@example.com"},
            "metadata": {
                "plan_id": "growth",
                "plan_name": "Growth",
                "billing_cycle": "monthly",
                "amount_usd": "399.00",
            },
        }

        response = self.client.post(
            self.paystack_confirm_endpoint,
            {"reference": "OVS-PAYSTACK-VERIFY-FAILED-123"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["status"], "abandoned")
        self.assertEqual(response.data["reference"], "OVS-PAYSTACK-VERIFY-FAILED-123")
        self.assertIn("Paystack transaction is not successful yet", response.data["detail"])
        self.assertIn("Gateway response", response.data["detail"])
        self.assertEqual(
            response.data["checkout_url"],
            "https://checkout.paystack.com/OVS-PAYSTACK-VERIFY-FAILED-123",
        )

        persisted = BillingSubscription.objects.get(provider="paystack", session_id="OVS-PAYSTACK-VERIFY-FAILED-123")
        self.assertEqual(persisted.status, "open")
        self.assertEqual(persisted.payment_status, "abandoned")

    @override_settings(PAYSTACK_SECRET_KEY="sk_test_paystack")
    def test_paystack_webhook_requires_signature_header(self):
        response = self.client.post(
            self.paystack_webhook_endpoint,
            "{}",
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @override_settings(PAYSTACK_SECRET_KEY="sk_test_paystack")
    def test_paystack_webhook_rejects_invalid_signature(self):
        payload = b'{"event":"charge.success","data":{"reference":"OVS-PAYSTACK-WEBHOOK-1"}}'
        response = self.client.post(
            self.paystack_webhook_endpoint,
            payload,
            content_type="application/json",
            HTTP_X_PAYSTACK_SIGNATURE="invalid",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @override_settings(PAYSTACK_SECRET_KEY="sk_test_paystack")
    def test_paystack_webhook_accepts_charge_success(self):
        payload_data = {
            "id": "evt_paystack_success_123",
            "event": "charge.success",
            "data": {
                "reference": "OVS-PAYSTACK-WEBHOOK-SUCCESS-123",
                "status": "success",
                "amount": 39900,
                "channel": "card",
                "customer": {"email": "billing-paystack-webhook@example.com"},
                "metadata": {
                    "plan_id": "growth",
                    "plan_name": "Growth",
                    "billing_cycle": "monthly",
                    "amount_usd": "399.00",
                },
            },
        }
        payload = json.dumps(payload_data).encode("utf-8")
        signature = self._paystack_signature(payload, "sk_test_paystack")

        response = self.client.post(
            self.paystack_webhook_endpoint,
            payload,
            content_type="application/json",
            HTTP_X_PAYSTACK_SIGNATURE=signature,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["received"])
        self.assertEqual(response.data["event_type"], "charge.success")
        self.assertEqual(response.data["session_id"], "OVS-PAYSTACK-WEBHOOK-SUCCESS-123")
        self.assertEqual(response.data["payment_status"], "paid")

        persisted = BillingSubscription.objects.get(
            provider="paystack",
            session_id="OVS-PAYSTACK-WEBHOOK-SUCCESS-123",
        )
        self.assertEqual(persisted.status, "complete")
        self.assertEqual(persisted.payment_status, "paid")

        webhook_event = BillingWebhookEvent.objects.get(provider="paystack", event_id="evt_paystack_success_123")
        self.assertEqual(webhook_event.processing_status, "processed")
        self.assertEqual(webhook_event.event_type, "charge.success")

    @override_settings(PAYSTACK_SECRET_KEY="sk_test_paystack")
    def test_paystack_webhook_charge_success_preserves_bank_transfer_payment_method(self):
        payload_data = {
            "id": "evt_paystack_success_bank_transfer_123",
            "event": "charge.success",
            "data": {
                "reference": "OVS-PAYSTACK-WEBHOOK-SUCCESS-BANK-123",
                "status": "success",
                "amount": 39900,
                "channel": "bank_transfer",
                "customer": {"email": "billing-paystack-webhook@example.com"},
                "metadata": {
                    "plan_id": "growth",
                    "plan_name": "Growth",
                    "billing_cycle": "monthly",
                    "amount_usd": "399.00",
                    "payment_method": "bank_transfer",
                },
            },
        }
        payload = json.dumps(payload_data).encode("utf-8")
        signature = self._paystack_signature(payload, "sk_test_paystack")

        response = self.client.post(
            self.paystack_webhook_endpoint,
            payload,
            content_type="application/json",
            HTTP_X_PAYSTACK_SIGNATURE=signature,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["received"])
        self.assertEqual(response.data["event_type"], "charge.success")

        persisted = BillingSubscription.objects.get(
            provider="paystack",
            session_id="OVS-PAYSTACK-WEBHOOK-SUCCESS-BANK-123",
        )
        self.assertEqual(persisted.status, "complete")
        self.assertEqual(persisted.payment_status, "paid")
        self.assertEqual(persisted.payment_method, "bank_transfer")

        payment_summary = dict((persisted.metadata or {}).get("payment_method_summary") or {})
        self.assertEqual(payment_summary.get("type"), "bank_transfer")

    @override_settings(PAYSTACK_SECRET_KEY="sk_test_paystack")
    def test_paystack_webhook_marks_charge_failed(self):
        BillingSubscription.objects.create(
            provider="paystack",
            status="open",
            payment_status="pending",
            session_id="OVS-PAYSTACK-WEBHOOK-FAILED-123",
            plan_id="growth",
            plan_name="Growth",
            billing_cycle="monthly",
            payment_method="card",
            amount_usd="399.00",
            reference="OVS-PAYSTACK-WEBHOOK-FAILED-123",
        )

        payload_data = {
            "id": "evt_paystack_failed_123",
            "event": "charge.failed",
            "data": {
                "reference": "OVS-PAYSTACK-WEBHOOK-FAILED-123",
                "status": "failed",
            },
        }
        payload = json.dumps(payload_data).encode("utf-8")
        signature = self._paystack_signature(payload, "sk_test_paystack")

        response = self.client.post(
            self.paystack_webhook_endpoint,
            payload,
            content_type="application/json",
            HTTP_X_PAYSTACK_SIGNATURE=signature,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["event_type"], "charge.failed")

        persisted = BillingSubscription.objects.get(
            provider="paystack",
            session_id="OVS-PAYSTACK-WEBHOOK-FAILED-123",
        )
        self.assertEqual(persisted.status, "failed")
        self.assertEqual(persisted.payment_status, "unpaid")

    @override_settings(STRIPE_SECRET_KEY="sk_test_123")
    @patch("apps.billing.views._ensure_stripe_ready")
    @patch("apps.billing.views._stripe_create_checkout_session")
    def test_stripe_checkout_session_create(self, mock_create, mock_ready):
        mock_ready.return_value = None
        mock_create.return_value = {
            "id": "cs_test_123",
            "url": "https://checkout.stripe.com/c/pay/cs_test_123",
            "status": "open",
            "payment_status": "unpaid",
            "metadata": {
                "plan_id": "growth",
                "plan_name": "Growth",
                "billing_cycle": "monthly",
                "payment_method": "card",
                "amount_usd": "399.00",
            },
            "amount_total": 39900,
        }
        _user, organization = self._authenticate_checkout_actor(
            email="billing-stripe-create@example.com",
            code="billing-stripe-create-org",
            name="Billing Stripe Create Org",
        )

        response = self.client.post(
            self.stripe_checkout_endpoint,
            {
                "plan_id": "growth",
                "plan_name": "Growth",
                "billing_cycle": "monthly",
                "amount_usd": "399.00",
                "success_url": "http://localhost:3000/subscribe",
                "cancel_url": "http://localhost:3000/subscribe?stripe_cancelled=1",
            },
            format="json",
            HTTP_X_ACTIVE_ORGANIZATION_ID=str(organization.id),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["provider"], "stripe")
        self.assertEqual(response.data["session_id"], "cs_test_123")
        self.assertIn("checkout_url", response.data)
        mock_ready.assert_called_once()
        mock_create.assert_called_once()

        persisted = BillingSubscription.objects.get(provider="stripe", session_id="cs_test_123")
        self.assertEqual(persisted.status, "open")
        self.assertEqual(persisted.payment_status, "unpaid")

    @override_settings(STRIPE_SECRET_KEY="sk_test_123")
    @patch("apps.billing.views._ensure_stripe_ready")
    @patch("apps.billing.views._stripe_create_checkout_session")
    def test_stripe_checkout_session_create_binds_authenticated_workspace_email(self, mock_create, mock_ready):
        mock_ready.return_value = None
        mock_create.return_value = {
            "id": "cs_test_auth_123",
            "url": "https://checkout.stripe.com/c/pay/cs_test_auth_123",
            "status": "open",
            "payment_status": "unpaid",
            "metadata": {
                "plan_id": "growth",
                "plan_name": "Growth",
                "billing_cycle": "monthly",
                "payment_method": "card",
                "amount_usd": "399.00",
                "workspace_email": "billing-auth-checkout@example.com",
            },
            "amount_total": 39900,
        }

        internal_user = self._create_internal_user(email="billing-auth-checkout@example.com")
        organization = self._create_org_membership(
            internal_user,
            code="billing-auth-checkout-org",
            name="Billing Auth Checkout Org",
        )
        self.client.force_authenticate(user=internal_user)

        response = self.client.post(
            self.stripe_checkout_endpoint,
            {
                "plan_id": "growth",
                "plan_name": "Growth",
                "billing_cycle": "monthly",
                "amount_usd": "399.00",
                "success_url": "http://localhost:3000/subscribe?returnTo=%2Fsettings",
                "cancel_url": "http://localhost:3000/billing/cancel?next=%2Fsettings",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["provider"], "stripe")
        self.assertEqual(response.data["session_id"], "cs_test_auth_123")
        self.assertEqual(mock_create.call_count, 1)
        create_kwargs = mock_create.call_args.kwargs
        self.assertEqual(create_kwargs["metadata"]["workspace_email"], internal_user.email)
        self.assertEqual(create_kwargs["metadata"]["organization_id"], str(organization.id))

    @override_settings(STRIPE_SECRET_KEY="sk_test_123")
    @patch("apps.billing.views._ensure_stripe_ready")
    @patch("apps.billing.views._stripe_retrieve_checkout_session")
    def test_stripe_confirm_issues_ticket(self, mock_retrieve, mock_ready):
        mock_ready.return_value = None
        mock_retrieve.return_value = {
            "id": "cs_test_123",
            "status": "complete",
            "payment_status": "paid",
            "amount_total": 39900,
            "payment_intent": "pi_test_123",
            "metadata": {
                "plan_id": "growth",
                "plan_name": "Growth",
                "billing_cycle": "monthly",
                "payment_method": "card",
                "amount_usd": "399.00",
            },
        }

        response = self.client.post(
            self.stripe_confirm_endpoint,
            {"session_id": "cs_test_123"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["provider"], "stripe")
        self.assertEqual(response.data["stripe_session_id"], "cs_test_123")
        self.assertIn("ticket", response.data)
        self.assertEqual(response.data["ticket"]["reference"], "pi_test_123")
        self.assertEqual(response.data["ticket"]["amountUsd"], 399.0)

        persisted = BillingSubscription.objects.get(provider="stripe", session_id="cs_test_123")
        self.assertEqual(persisted.status, "complete")
        self.assertEqual(persisted.payment_status, "paid")
        self.assertEqual(persisted.payment_intent_id, "pi_test_123")

    @override_settings(
        STRIPE_SECRET_KEY="sk_test_123",
        BILLING_CHECKOUT_CONFIRM_RATE_LIMIT_ENABLED=True,
        BILLING_CHECKOUT_CONFIRM_RATE_LIMIT_PER_MINUTE=1,
    )
    @patch("apps.billing.views._ensure_stripe_ready")
    @patch("apps.billing.views._stripe_retrieve_checkout_session")
    def test_stripe_confirm_rate_limited(self, mock_retrieve, mock_ready):
        mock_ready.return_value = None
        mock_retrieve.return_value = {
            "id": "cs_test_rate_limit_123",
            "status": "complete",
            "payment_status": "paid",
            "amount_total": 39900,
            "payment_intent": "pi_test_rate_limit_123",
            "metadata": {
                "plan_id": "growth",
                "plan_name": "Growth",
                "billing_cycle": "monthly",
                "payment_method": "card",
                "amount_usd": "399.00",
            },
        }

        first = self.client.post(
            self.stripe_confirm_endpoint,
            {"session_id": "cs_test_rate_limit_123"},
            format="json",
            REMOTE_ADDR="10.1.1.60",
        )
        second = self.client.post(
            self.stripe_confirm_endpoint,
            {"session_id": "cs_test_rate_limit_123"},
            format="json",
            REMOTE_ADDR="10.1.1.60",
        )

        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(second.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(second.data.get("code"), "RATE_LIMITED")
        self.assertIn("Retry-After", second)
        self.assertEqual(mock_retrieve.call_count, 1)

    @override_settings(
        STRIPE_SECRET_KEY="sk_test_123",
        BILLING_CHECKOUT_CONFIRM_RATE_LIMIT_ENABLED=False,
    )
    @patch("apps.billing.views._ensure_stripe_ready")
    @patch("apps.billing.views._stripe_retrieve_checkout_session")
    def test_stripe_confirm_is_idempotent_for_retries(self, mock_retrieve, mock_ready):
        mock_ready.return_value = None
        mock_retrieve.return_value = {
            "id": "cs_test_idempotent_123",
            "status": "complete",
            "payment_status": "paid",
            "amount_total": 39900,
            "payment_intent": "pi_test_idempotent_123",
            "metadata": {
                "plan_id": "growth",
                "plan_name": "Growth",
                "billing_cycle": "monthly",
                "payment_method": "card",
                "amount_usd": "399.00",
            },
        }

        first = self.client.post(
            self.stripe_confirm_endpoint,
            {"session_id": "cs_test_idempotent_123"},
            format="json",
        )
        second = self.client.post(
            self.stripe_confirm_endpoint,
            {"session_id": "cs_test_idempotent_123"},
            format="json",
        )

        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        self.assertEqual(
            BillingSubscription.objects.filter(
                provider="stripe",
                session_id="cs_test_idempotent_123",
            ).count(),
            1,
        )

    @override_settings(STRIPE_SECRET_KEY="sk_test_123")
    @patch("apps.billing.views._ensure_stripe_ready")
    @patch("apps.billing.views._stripe_retrieve_checkout_session")
    def test_stripe_confirm_prefers_provider_metadata_organization(self, mock_retrieve, mock_ready):
        metadata_org = Organization.objects.create(
            code="stripe-meta-org",
            name="Stripe Metadata Org",
            organization_type="agency",
            is_active=True,
        )
        request_org = Organization.objects.create(
            code="stripe-request-org",
            name="Stripe Request Org",
            organization_type="agency",
            is_active=True,
        )
        mock_ready.return_value = None
        mock_retrieve.return_value = {
            "id": "cs_test_metadata_org_123",
            "status": "complete",
            "payment_status": "paid",
            "amount_total": 39900,
            "payment_intent": "pi_test_metadata_org_123",
            "metadata": {
                "plan_id": "growth",
                "plan_name": "Growth",
                "billing_cycle": "monthly",
                "payment_method": "card",
                "amount_usd": "399.00",
                "organization_id": str(metadata_org.id),
            },
        }

        response = self.client.post(
            self.stripe_confirm_endpoint,
            {"session_id": "cs_test_metadata_org_123"},
            format="json",
            HTTP_X_ACTIVE_ORGANIZATION_ID=str(request_org.id),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        persisted = BillingSubscription.objects.get(provider="stripe", session_id="cs_test_metadata_org_123")
        self.assertEqual(persisted.organization_id, metadata_org.id)

    @override_settings(STRIPE_SECRET_KEY="sk_test_123")
    @patch("apps.billing.views._ensure_stripe_ready")
    @patch("apps.billing.views._stripe_retrieve_checkout_session")
    def test_stripe_confirm_rejects_incomplete_sessions(self, mock_retrieve, mock_ready):
        mock_ready.return_value = None
        mock_retrieve.return_value = {
            "id": "cs_test_123",
            "status": "open",
            "payment_status": "unpaid",
            "metadata": {
                "plan_id": "growth",
                "plan_name": "Growth",
                "billing_cycle": "monthly",
                "payment_method": "card",
                "amount_usd": "399.00",
            },
        }

        response = self.client.post(
            self.stripe_confirm_endpoint,
            {"session_id": "cs_test_123"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_stripe_webhook_requires_webhook_secret(self):
        response = self.client.post(
            self.stripe_webhook_endpoint,
            {},
            format="json",
            HTTP_STRIPE_SIGNATURE="sig_test",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @override_settings(STRIPE_WEBHOOK_SECRET="whsec_test_123")
    @patch("apps.billing.views._ensure_stripe_webhook_ready")
    def test_stripe_webhook_requires_signature_header(self, mock_ready):
        mock_ready.return_value = None

        response = self.client.post(
            self.stripe_webhook_endpoint,
            {},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @override_settings(STRIPE_WEBHOOK_SECRET="whsec_test_123")
    @patch("apps.billing.views._ensure_stripe_webhook_ready")
    @patch("apps.billing.views._stripe_construct_event")
    def test_stripe_webhook_rejects_invalid_signature(self, mock_construct, mock_ready):
        mock_ready.return_value = None
        mock_construct.side_effect = ValueError("Invalid signature")

        response = self.client.post(
            self.stripe_webhook_endpoint,
            "{}",
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="sig_test",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @override_settings(STRIPE_WEBHOOK_SECRET="whsec_test_123")
    @patch("apps.billing.views._ensure_stripe_webhook_ready")
    @patch("apps.billing.views._stripe_construct_event")
    def test_stripe_webhook_accepts_checkout_session_completed(self, mock_construct, mock_ready):
        mock_ready.return_value = None
        mock_construct.return_value = {
            "id": "evt_test_123",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_test_123",
                    "status": "complete",
                    "payment_status": "paid",
                    "amount_total": 39900,
                    "payment_intent": "pi_test_123",
                    "metadata": {
                        "plan_id": "growth",
                        "plan_name": "Growth",
                        "billing_cycle": "monthly",
                        "payment_method": "card",
                        "amount_usd": "399.00",
                    },
                }
            },
        }

        response = self.client.post(
            self.stripe_webhook_endpoint,
            "{}",
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="sig_test",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["received"])
        self.assertEqual(response.data["event_type"], "checkout.session.completed")
        self.assertEqual(response.data["session_id"], "cs_test_123")
        self.assertEqual(response.data["payment_status"], "paid")

        persisted = BillingSubscription.objects.get(provider="stripe", session_id="cs_test_123")
        self.assertEqual(persisted.status, "complete")
        self.assertEqual(persisted.payment_status, "paid")

        webhook_event = BillingWebhookEvent.objects.get(provider="stripe", event_id="evt_test_123")
        self.assertEqual(webhook_event.processing_status, "processed")
        self.assertEqual(webhook_event.event_type, "checkout.session.completed")

    @override_settings(STRIPE_WEBHOOK_SECRET="whsec_test_123")
    @patch("apps.billing.views._ensure_stripe_webhook_ready")
    @patch("apps.billing.views._stripe_construct_event")
    def test_stripe_webhook_marks_invoice_payment_failed_for_subscription(self, mock_construct, mock_ready):
        mock_ready.return_value = None
        subscription = BillingSubscription.objects.create(
            provider="stripe",
            status="complete",
            payment_status="paid",
            session_id="cs_failed_invoice",
            plan_id="growth",
            plan_name="Growth",
            billing_cycle="monthly",
            payment_method="card",
            amount_usd="399.00",
            reference="OVS-WEBHOOK-FAILED",
            metadata={"stripe_subscription_id": "sub_failed_123"},
        )
        mock_construct.return_value = {
            "id": "evt_invoice_failed_123",
            "type": "invoice.payment_failed",
            "data": {
                "object": {
                    "id": "in_failed_123",
                    "subscription": "sub_failed_123",
                }
            },
        }

        response = self.client.post(
            self.stripe_webhook_endpoint,
            "{}",
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="sig_test",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        subscription.refresh_from_db()
        self.assertEqual(subscription.status, "failed")
        self.assertEqual(subscription.payment_status, "unpaid")
        self.assertIn("last_invoice_payment_failed_at", subscription.metadata)

    @override_settings(STRIPE_WEBHOOK_SECRET="whsec_test_123")
    @patch("apps.billing.views._ensure_stripe_webhook_ready")
    @patch("apps.billing.views._stripe_construct_event")
    def test_stripe_webhook_marks_subscription_deleted_as_canceled(self, mock_construct, mock_ready):
        mock_ready.return_value = None
        subscription = BillingSubscription.objects.create(
            provider="stripe",
            status="complete",
            payment_status="paid",
            session_id="cs_deleted_subscription",
            plan_id="growth",
            plan_name="Growth",
            billing_cycle="monthly",
            payment_method="card",
            amount_usd="399.00",
            reference="OVS-WEBHOOK-DELETED",
            metadata={"stripe_subscription_id": "sub_deleted_123"},
        )
        mock_construct.return_value = {
            "id": "evt_subscription_deleted_123",
            "type": "customer.subscription.deleted",
            "data": {
                "object": {
                    "id": "sub_deleted_123",
                    "cancel_at_period_end": False,
                    "current_period_end": 1760000000,
                }
            },
        }

        response = self.client.post(
            self.stripe_webhook_endpoint,
            "{}",
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="sig_test",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        subscription.refresh_from_db()
        self.assertEqual(subscription.status, "canceled")
        self.assertEqual(subscription.payment_status, "unpaid")
        self.assertIn("cancellation_effective_at", subscription.metadata)










