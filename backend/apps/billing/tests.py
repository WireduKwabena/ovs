from unittest.mock import Mock, patch
import hashlib
import hmac
import json

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.campaigns.models import VettingCampaign
from apps.candidates.models import Candidate, CandidateEnrollment

from .models import BillingSubscription, BillingWebhookEvent


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
    billing_quotas_endpoint = "/api/billing/quotas/"
    billing_manage_endpoint = "/api/billing/subscriptions/manage/"
    billing_manage_update_session_endpoint = "/api/billing/subscriptions/manage/payment-method/update-session/"
    billing_retry_endpoint = "/api/billing/subscriptions/manage/retry/"

    def setUp(self):
        cache.clear()

    def _create_hr_user(self, email: str = "billing-hr@example.com"):
        user_model = get_user_model()
        return user_model.objects.create_user(
            email=email,
            password="StrongPass123!",
            first_name="Billing",
            last_name="Manager",
            user_type="hr_manager",
        )

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
        hr_user = self._create_hr_user()
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
            registration_consumed_by_email=hr_user.email,
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

        self.client.force_authenticate(user=hr_user)
        response = self.client.get(self.billing_manage_endpoint)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "ok")
        self.assertIsNotNone(response.data["subscription"])
        self.assertEqual(response.data["subscription"]["plan_id"], "growth")
        self.assertEqual(response.data["subscription"]["payment_method"]["type"], "card")
        self.assertEqual(response.data["subscription"]["payment_method"]["display"], "Card")

    def test_billing_manage_patch_updates_sandbox_payment_method(self):
        hr_user = self._create_hr_user(email="billing-update@example.com")
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
            registration_consumed_by_email=hr_user.email,
        )

        self.client.force_authenticate(user=hr_user)
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
        hr_user = self._create_hr_user(email="billing-delete@example.com")
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
            registration_consumed_by_email=hr_user.email,
        )

        self.client.force_authenticate(user=hr_user)
        response = self.client.delete(self.billing_manage_endpoint)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        subscription.refresh_from_db()
        self.assertEqual(subscription.status, "complete")
        self.assertEqual(bool(subscription.metadata.get("cancel_at_period_end")), True)
        self.assertIn("cancellation_effective_at", subscription.metadata)
        self.assertIn("end of current billing period", response.data.get("message", "").lower())

    def test_billing_retry_creates_new_sandbox_subscription_for_failed_payment(self):
        hr_user = self._create_hr_user(email="billing-retry@example.com")
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
            registration_consumed_by_email=hr_user.email,
        )

        self.client.force_authenticate(user=hr_user)
        response = self.client.post(self.billing_retry_endpoint, {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["provider"], "sandbox")
        self.assertEqual(response.data["status"], "ok")
        self.assertEqual(
            BillingSubscription.objects.filter(
                registration_consumed_by_email=hr_user.email,
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

        hr_user = self._create_hr_user(email="billing-retry-paystack@example.com")
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
            registration_consumed_by_email=hr_user.email,
        )

        self.client.force_authenticate(user=hr_user)
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

        hr_user = self._create_hr_user(email="billing-portal@example.com")
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
            registration_consumed_by_email=hr_user.email,
            metadata={
                "stripe_customer_id": "cus_portal_123",
                "stripe_subscription_id": "sub_portal_123",
            },
        )

        self.client.force_authenticate(user=hr_user)
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
        hr_user = user_model.objects.create_user(
            email="hr-quota-check@example.com",
            password="StrongPass123!",
            first_name="Quota",
            last_name="Owner",
            user_type="hr_manager",
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
            registration_consumed_by_email=hr_user.email,
        )

        campaign = VettingCampaign.objects.create(
            name="Quota Campaign",
            description="Quota visibility",
            status="active",
            initiated_by=hr_user,
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

        self.client.force_authenticate(user=hr_user)
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
            user_type="hr_manager",
        )

        self.client.force_authenticate(user=user)
        non_staff_response = self.client.get(self.billing_health_endpoint)
        self.assertEqual(non_staff_response.status_code, status.HTTP_403_FORBIDDEN)

        user.is_staff = True
        user.save(update_fields=["is_staff"])

        self.client.force_authenticate(user=user)
        staff_response = self.client.get(self.billing_health_endpoint)
        self.assertEqual(staff_response.status_code, status.HTTP_200_OK)

    def test_confirm_subscription_returns_ticket_for_anonymous_user(self):
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

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "confirmed")
        self.assertIn("ticket", response.data)

        ticket = response.data["ticket"]
        self.assertEqual(ticket["planId"], "growth")
        self.assertEqual(ticket["planName"], "Growth")
        self.assertEqual(ticket["billingCycle"], "monthly")
        self.assertEqual(ticket["paymentMethod"], "card")
        self.assertEqual(ticket["amountUsd"], 399.0)
        self.assertTrue(ticket["reference"].startswith("OVS-"))
        self.assertGreater(ticket["expiresAt"], ticket["confirmedAt"])

        persisted = BillingSubscription.objects.get(provider="sandbox", reference=ticket["reference"])
        self.assertEqual(persisted.status, "complete")
        self.assertEqual(float(persisted.amount_usd), 399.0)

    def test_confirm_subscription_binds_authenticated_workspace_email(self):
        hr_user = self._create_hr_user(email="billing-auth-confirm@example.com")
        self.client.force_authenticate(user=hr_user)

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

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ticket = response.data["ticket"]
        persisted = BillingSubscription.objects.get(provider="sandbox", reference=ticket["reference"])
        self.assertEqual(persisted.registration_consumed_by_email, hr_user.email)
        self.assertIsNotNone(persisted.registration_consumed_at)

    def test_confirm_subscription_validates_payment_method(self):
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
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("payment_method", response.data)

    @override_settings(BILLING_SUBSCRIPTION_TICKET_TTL_HOURS=1)
    def test_confirm_subscription_respects_ttl_setting(self):
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
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ticket = response.data["ticket"]
        ttl_ms = ticket["expiresAt"] - ticket["confirmedAt"]
        self.assertGreaterEqual(ttl_ms, 3_590_000)
        self.assertLessEqual(ttl_ms, 3_610_000)

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

    @override_settings(STRIPE_SECRET_KEY="")
    def test_stripe_checkout_requires_secret_key(self):
        response = self.client.post(
            self.stripe_checkout_endpoint,
            {
                "plan_id": "growth",
                "plan_name": "Growth",
                "billing_cycle": "monthly",
                "amount_usd": "399.00",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @override_settings(PAYSTACK_SECRET_KEY="")
    def test_paystack_checkout_requires_secret_key(self):
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

        hr_user = self._create_hr_user(email="billing-auth-checkout@example.com")
        self.client.force_authenticate(user=hr_user)

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
        self.assertEqual(create_kwargs["metadata"]["workspace_email"], hr_user.email)

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








