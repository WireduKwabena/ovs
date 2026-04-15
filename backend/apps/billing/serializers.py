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


class SubscriptionTicketSerializer(serializers.Serializer):
    planId = serializers.CharField()
    planName = serializers.CharField()
    billingCycle = serializers.ChoiceField(choices=SubscriptionConfirmSerializer.BILLING_CYCLE_CHOICES)
    paymentMethod = serializers.ChoiceField(choices=SubscriptionConfirmSerializer.PAYMENT_METHOD_CHOICES)
    amountUsd = serializers.FloatField()
    reference = serializers.CharField()
    confirmedAt = serializers.IntegerField()
    expiresAt = serializers.IntegerField()


class StripeCheckoutSessionConfirmResponseSerializer(serializers.Serializer):
    status = serializers.CharField()
    provider = serializers.CharField()
    stripe_session_id = serializers.CharField()
    ticket = SubscriptionTicketSerializer()


class PaystackCheckoutSessionCreateSerializer(serializers.Serializer):
    BILLING_CYCLE_CHOICES = ("monthly", "annual")
    PAYMENT_METHOD_CHOICES = ("card", "bank_transfer", "mobile_money")

    plan_id = serializers.CharField(max_length=64)
    plan_name = serializers.CharField(max_length=128)
    billing_cycle = serializers.ChoiceField(choices=BILLING_CYCLE_CHOICES)
    payment_method = serializers.ChoiceField(choices=PAYMENT_METHOD_CHOICES, required=False, default="card")
    amount_usd = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal("0.01"))
    success_url = serializers.URLField(required=False)
    cancel_url = serializers.URLField(required=False)
    customer_email = serializers.EmailField(required=False)


class PaystackCheckoutSessionConfirmSerializer(serializers.Serializer):
    reference = serializers.CharField(max_length=255)


class PaystackCheckoutSessionConfirmResponseSerializer(serializers.Serializer):
    status = serializers.CharField()
    provider = serializers.CharField()
    paystack_reference = serializers.CharField()
    ticket = SubscriptionTicketSerializer()


class CheckoutConfirmErrorSerializer(serializers.Serializer):
    detail = serializers.CharField(required=False)
    code = serializers.CharField(required=False)
    status = serializers.CharField(required=False)
    reference = serializers.CharField(required=False)
    checkout_url = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class SubscriptionAccessVerifySerializer(serializers.Serializer):
    reference = serializers.CharField(max_length=255)
    organization_id = serializers.UUIDField(required=False, allow_null=True)


class BillingActionErrorSerializer(serializers.Serializer):
    detail = serializers.CharField(required=False)
    error = serializers.CharField(required=False)
    code = serializers.CharField(required=False)
    setup_path = serializers.CharField(required=False)


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


class BillingHealthExchangeRateSerializer(serializers.Serializer):
    api_url_configured = serializers.BooleanField()
    fallback_rate = serializers.FloatField()
    timeout_seconds = serializers.IntegerField()
    cache_ttl_seconds = serializers.IntegerField()


class BillingHealthRateLimitSerializer(serializers.Serializer):
    enabled = serializers.BooleanField()
    per_minute = serializers.IntegerField()


class BillingHealthResponseSerializer(serializers.Serializer):
    status = serializers.CharField()
    access = BillingHealthAccessSerializer()
    stripe = BillingHealthStripeSerializer()
    paystack = BillingHealthPaystackSerializer()
    exchange_rate = BillingHealthExchangeRateSerializer()
    subscription_verify_rate_limit = BillingHealthRateLimitSerializer()


class BillingExchangeRateResponseSerializer(serializers.Serializer):
    status = serializers.CharField()
    base = serializers.CharField()
    target = serializers.CharField()
    rate = serializers.FloatField()
    source = serializers.CharField()


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


class BillingLatestIncidentSerializer(serializers.Serializer):
    code = serializers.CharField()
    message = serializers.CharField()
    detected_at = serializers.DateTimeField(allow_null=True)
    source = serializers.CharField()
    event_type = serializers.CharField(allow_blank=True, allow_null=True)


class BillingManagedSubscriptionSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    organization_id = serializers.CharField(allow_null=True, required=False)
    organization_name = serializers.CharField(allow_null=True, required=False)
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
    latest_incident = BillingLatestIncidentSerializer(allow_null=True, required=False)
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


class OnboardingTokenStateSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    subscription_id = serializers.UUIDField(allow_null=True)
    token_preview = serializers.CharField()
    is_active = serializers.BooleanField()
    expires_at = serializers.DateTimeField(allow_null=True)
    max_uses = serializers.IntegerField(allow_null=True)
    uses = serializers.IntegerField()
    remaining_uses = serializers.IntegerField(allow_null=True)
    allowed_email_domain = serializers.CharField(allow_blank=True)
    last_used_at = serializers.DateTimeField(allow_null=True)
    revoked_at = serializers.DateTimeField(allow_null=True)
    revoked_reason = serializers.CharField(allow_blank=True)
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()


class OrganizationOnboardingTokenStateResponseSerializer(serializers.Serializer):
    status = serializers.CharField()
    organization_id = serializers.UUIDField()
    organization_name = serializers.CharField()
    subscription_id = serializers.UUIDField(allow_null=True)
    subscription_active = serializers.BooleanField()
    has_active_token = serializers.BooleanField()
    token = OnboardingTokenStateSerializer(allow_null=True)
    organization_seat_limit = serializers.IntegerField(allow_null=True, required=False)
    organization_seat_used = serializers.IntegerField(allow_null=True, required=False)
    organization_seat_remaining = serializers.IntegerField(allow_null=True, required=False)


class OrganizationOnboardingTokenGenerateSerializer(serializers.Serializer):
    max_uses = serializers.IntegerField(required=False, min_value=1)
    expires_in_hours = serializers.IntegerField(required=False, min_value=1, max_value=24 * 365)
    allowed_email_domain = serializers.CharField(required=False, allow_blank=True, max_length=255)
    rotate = serializers.BooleanField(required=False, default=True)


class OrganizationOnboardingTokenGenerateResponseSerializer(serializers.Serializer):
    status = serializers.CharField()
    organization_id = serializers.UUIDField()
    organization_name = serializers.CharField()
    token = serializers.CharField()
    onboarding_link = serializers.CharField(allow_blank=True)
    token_state = OnboardingTokenStateSerializer()


class OrganizationOnboardingTokenRevokeSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, max_length=255)


class OrganizationOnboardingTokenValidateSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=512)
    email = serializers.EmailField(required=False, allow_blank=True)


class OrganizationOnboardingTokenValidateResponseSerializer(serializers.Serializer):
    valid = serializers.BooleanField()
    reason = serializers.CharField()
    organization_id = serializers.UUIDField(required=False)
    organization_name = serializers.CharField(required=False)
    subscription_id = serializers.UUIDField(required=False, allow_null=True)
    remaining_uses = serializers.IntegerField(required=False, allow_null=True)
    expires_at = serializers.DateTimeField(required=False, allow_null=True)


class OrganizationOnboardingTokenSendInviteSerializer(serializers.Serializer):
    recipient_emails = serializers.ListField(
        child=serializers.EmailField(),
        min_length=1,
        max_length=20,
    )
    max_uses = serializers.IntegerField(required=False, min_value=1)
    expires_in_hours = serializers.IntegerField(required=False, min_value=1, max_value=24 * 365)
    allowed_email_domain = serializers.CharField(required=False, allow_blank=True, max_length=255)
    rotate = serializers.BooleanField(required=False, default=True)


class OrganizationOnboardingTokenSendInviteResponseSerializer(serializers.Serializer):
    status = serializers.CharField()
    sent = serializers.ListField(child=serializers.EmailField())
    failed = serializers.ListField(child=serializers.EmailField())
    organization_name = serializers.CharField()
    token_state = OnboardingTokenStateSerializer()
