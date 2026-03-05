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


class PaystackCheckoutSessionCreateSerializer(serializers.Serializer):
    BILLING_CYCLE_CHOICES = ("monthly", "annual")

    plan_id = serializers.CharField(max_length=64)
    plan_name = serializers.CharField(max_length=128)
    billing_cycle = serializers.ChoiceField(choices=BILLING_CYCLE_CHOICES)
    amount_usd = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal("0.01"))
    success_url = serializers.URLField(required=False)
    cancel_url = serializers.URLField(required=False)
    customer_email = serializers.EmailField(required=False)


class PaystackCheckoutSessionConfirmSerializer(serializers.Serializer):
    reference = serializers.CharField(max_length=255)


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


class BillingHealthPaystackSerializer(serializers.Serializer):
    secret_key_configured = serializers.BooleanField()
    base_url = serializers.CharField()
    currency = serializers.CharField()


class BillingHealthRateLimitSerializer(serializers.Serializer):
    enabled = serializers.BooleanField()
    per_minute = serializers.IntegerField()


class BillingHealthResponseSerializer(serializers.Serializer):
    status = serializers.CharField()
    access = BillingHealthAccessSerializer()
    stripe = BillingHealthStripeSerializer()
    paystack = BillingHealthPaystackSerializer()
    subscription_verify_rate_limit = BillingHealthRateLimitSerializer()


class BillingQuotaCandidateSerializer(serializers.Serializer):
    enforced = serializers.BooleanField()
    scope = serializers.CharField()
    reason = serializers.CharField(allow_null=True)
    plan_id = serializers.CharField(allow_null=True)
    plan_name = serializers.CharField(allow_null=True)
    limit = serializers.IntegerField(allow_null=True)
    used = serializers.IntegerField()
    remaining = serializers.IntegerField(allow_null=True)
    period_start = serializers.DateTimeField()
    period_end = serializers.DateTimeField()


class BillingQuotaResponseSerializer(serializers.Serializer):
    status = serializers.CharField()
    candidate = BillingQuotaCandidateSerializer()


class BillingWebhookResponseSerializer(serializers.Serializer):
    received = serializers.BooleanField()
    event_type = serializers.CharField()
    session_id = serializers.CharField(required=False)
    payment_status = serializers.CharField(required=False)


class BillingPaymentMethodSummarySerializer(serializers.Serializer):
    type = serializers.CharField(allow_null=True)
    display = serializers.CharField(allow_blank=True, allow_null=True)
    brand = serializers.CharField(allow_blank=True, allow_null=True)
    last4 = serializers.CharField(allow_blank=True, allow_null=True)
    exp_month = serializers.IntegerField(allow_null=True)
    exp_year = serializers.IntegerField(allow_null=True)


class BillingManagedSubscriptionSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    provider = serializers.CharField()
    status = serializers.CharField()
    payment_status = serializers.CharField()
    plan_id = serializers.CharField()
    plan_name = serializers.CharField()
    billing_cycle = serializers.CharField()
    amount_usd = serializers.DecimalField(max_digits=10, decimal_places=2)
    payment_method = BillingPaymentMethodSummarySerializer()
    checkout_url = serializers.CharField(allow_blank=True, allow_null=True)
    current_period_start = serializers.DateTimeField(allow_null=True)
    current_period_end = serializers.DateTimeField(allow_null=True)
    cancel_at_period_end = serializers.BooleanField()
    cancellation_requested_at = serializers.DateTimeField(allow_null=True)
    cancellation_effective_at = serializers.DateTimeField(allow_null=True)
    can_update_payment_method = serializers.BooleanField()
    can_delete_payment_method = serializers.BooleanField()
    retry_available = serializers.BooleanField()
    retry_reason = serializers.CharField(allow_null=True)
    updated_at = serializers.DateTimeField()


class BillingSubscriptionManageResponseSerializer(serializers.Serializer):
    status = serializers.CharField()
    message = serializers.CharField(required=False)
    subscription = BillingManagedSubscriptionSerializer(allow_null=True)


class BillingPaymentMethodUpdateSerializer(serializers.Serializer):
    payment_method = serializers.ChoiceField(choices=SubscriptionConfirmSerializer.PAYMENT_METHOD_CHOICES)


class BillingPortalSessionResponseSerializer(serializers.Serializer):
    status = serializers.CharField()
    provider = serializers.CharField()
    url = serializers.URLField()


class BillingSubscriptionRetryResponseSerializer(serializers.Serializer):
    status = serializers.CharField()
    provider = serializers.CharField()
    message = serializers.CharField(required=False)
    session_id = serializers.CharField(required=False)
    checkout_url = serializers.URLField(required=False)
