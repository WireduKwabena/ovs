from decimal import Decimal

from rest_framework import serializers


class SubscriptionConfirmSerializer(serializers.Serializer):
    BILLING_CYCLE_CHOICES = ("monthly", "annual")
    PAYMENT_METHOD_CHOICES = ("card", "bank_transfer", "mobile_money")

    plan_id = serializers.CharField(max_length=64)
    plan_name = serializers.CharField(max_length=128)
    billing_cycle = serializers.ChoiceField(choices=BILLING_CYCLE_CHOICES)
    payment_method = serializers.ChoiceField(choices=PAYMENT_METHOD_CHOICES)
    amount_usd = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal("0.01"))


class StripeCheckoutSessionCreateSerializer(serializers.Serializer):
    BILLING_CYCLE_CHOICES = ("monthly", "annual")

    plan_id = serializers.CharField(max_length=64)
    plan_name = serializers.CharField(max_length=128)
    billing_cycle = serializers.ChoiceField(choices=BILLING_CYCLE_CHOICES)
    amount_usd = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal("0.01"))
    success_url = serializers.URLField(required=False)
    cancel_url = serializers.URLField(required=False)


class StripeCheckoutSessionConfirmSerializer(serializers.Serializer):
    session_id = serializers.CharField(max_length=255)


class SubscriptionAccessVerifySerializer(serializers.Serializer):
    reference = serializers.CharField(max_length=255)


class BillingActionErrorSerializer(serializers.Serializer):
    detail = serializers.CharField(required=False)
    error = serializers.CharField(required=False)


class BillingHealthAccessSerializer(serializers.Serializer):
    staff_required = serializers.BooleanField()
    requester_is_staff = serializers.BooleanField()


class BillingHealthStripeSerializer(serializers.Serializer):
    sdk_installed = serializers.BooleanField()
    secret_key_configured = serializers.BooleanField()
    webhook_secret_configured = serializers.BooleanField()


class BillingHealthRateLimitSerializer(serializers.Serializer):
    enabled = serializers.BooleanField()
    per_minute = serializers.IntegerField()


class BillingHealthResponseSerializer(serializers.Serializer):
    status = serializers.CharField()
    access = BillingHealthAccessSerializer()
    stripe = BillingHealthStripeSerializer()
    subscription_verify_rate_limit = BillingHealthRateLimitSerializer()


class BillingWebhookResponseSerializer(serializers.Serializer):
    received = serializers.BooleanField()
    event_type = serializers.CharField()
    session_id = serializers.CharField(required=False)
    payment_status = serializers.CharField(required=False)
