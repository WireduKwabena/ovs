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
