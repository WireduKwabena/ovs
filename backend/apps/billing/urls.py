from django.urls import path

from .views import (
    BillingExchangeRateAPIView,
    BillingHealthAPIView,
    BillingPaymentMethodUpdateSessionAPIView,
    BillingQuotaAPIView,
    BillingSubscriptionManageAPIView,
    BillingSubscriptionRetryAPIView,
    OrganizationOnboardingTokenGenerateAPIView,
    OrganizationOnboardingTokenRevokeAPIView,
    OrganizationOnboardingTokenStateAPIView,
    OrganizationOnboardingTokenValidateAPIView,
    PaystackCheckoutSessionConfirmAPIView,
    PaystackCheckoutSessionCreateAPIView,
    PaystackWebhookAPIView,
    StripeCheckoutSessionConfirmAPIView,
    StripeCheckoutSessionCreateAPIView,
    StripeWebhookAPIView,
    SubscriptionAccessVerifyAPIView,
    SubscriptionConfirmAPIView,
)

app_name = "billing"

urlpatterns = [
    path("health/", BillingHealthAPIView.as_view(), name="billing-health"),
    path("exchange-rate/", BillingExchangeRateAPIView.as_view(), name="billing-exchange-rate"),
    path("quotas/", BillingQuotaAPIView.as_view(), name="billing-quotas"),
    path("onboarding-token/", OrganizationOnboardingTokenStateAPIView.as_view(), name="billing-onboarding-token-state"),
    path(
        "onboarding-token/generate/",
        OrganizationOnboardingTokenGenerateAPIView.as_view(),
        name="billing-onboarding-token-generate",
    ),
    path(
        "onboarding-token/revoke/",
        OrganizationOnboardingTokenRevokeAPIView.as_view(),
        name="billing-onboarding-token-revoke",
    ),
    path(
        "onboarding-token/validate/",
        OrganizationOnboardingTokenValidateAPIView.as_view(),
        name="billing-onboarding-token-validate",
    ),
    path("subscriptions/manage/", BillingSubscriptionManageAPIView.as_view(), name="billing-subscription-manage"),
    path(
        "subscriptions/manage/payment-method/update-session/",
        BillingPaymentMethodUpdateSessionAPIView.as_view(),
        name="billing-subscription-payment-method-update-session",
    ),
    path("subscriptions/manage/retry/", BillingSubscriptionRetryAPIView.as_view(), name="billing-subscription-retry"),
    path("subscriptions/confirm/", SubscriptionConfirmAPIView.as_view(), name="subscription-confirm"),
    path(
        "subscriptions/access/verify/",
        SubscriptionAccessVerifyAPIView.as_view(),
        name="subscription-access-verify",
    ),
    path(
        "subscriptions/stripe/checkout-session/",
        StripeCheckoutSessionCreateAPIView.as_view(),
        name="stripe-checkout-session",
    ),
    path(
        "subscriptions/stripe/confirm/",
        StripeCheckoutSessionConfirmAPIView.as_view(),
        name="stripe-confirm",
    ),
    path(
        "subscriptions/paystack/checkout-session/",
        PaystackCheckoutSessionCreateAPIView.as_view(),
        name="paystack-checkout-session",
    ),
    path(
        "subscriptions/paystack/confirm/",
        PaystackCheckoutSessionConfirmAPIView.as_view(),
        name="paystack-confirm",
    ),
    path(
        "subscriptions/paystack/webhook/",
        PaystackWebhookAPIView.as_view(),
        name="paystack-webhook",
    ),
    path(
        "subscriptions/stripe/webhook/",
        StripeWebhookAPIView.as_view(),
        name="stripe-webhook",
    ),
]
