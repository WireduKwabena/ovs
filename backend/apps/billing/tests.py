from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from .models import BillingSubscription, BillingWebhookEvent


class BillingApiTests(APITestCase):
    sandbox_endpoint = "/api/billing/subscriptions/confirm/"
    subscription_access_verify_endpoint = "/api/billing/subscriptions/access/verify/"
    stripe_checkout_endpoint = "/api/billing/subscriptions/stripe/checkout-session/"
    stripe_confirm_endpoint = "/api/billing/subscriptions/stripe/confirm/"
    stripe_webhook_endpoint = "/api/billing/subscriptions/stripe/webhook/"
    billing_health_endpoint = "/api/billing/health/"

    def setUp(self):
        cache.clear()


    @override_settings(
        STRIPE_SECRET_KEY="",
        STRIPE_WEBHOOK_SECRET="",
        BILLING_SUBSCRIPTION_VERIFY_RATE_LIMIT_ENABLED=True,
        BILLING_SUBSCRIPTION_VERIFY_RATE_LIMIT_PER_MINUTE=30,
    )
    def test_billing_health_reports_runtime_flags(self):
        response = self.client.get(self.billing_health_endpoint)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "ok")
        self.assertIn("stripe", response.data)
        self.assertIn("subscription_verify_rate_limit", response.data)
        self.assertIn("access", response.data)
        self.assertEqual(response.data["access"]["staff_required"], False)
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








