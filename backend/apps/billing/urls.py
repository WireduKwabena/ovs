from django.urls import path

from .views import (
    BillingHealthAPIView,
    StripeCheckoutSessionConfirmAPIView,
    StripeCheckoutSessionCreateAPIView,
    StripeWebhookAPIView,
    SubscriptionAccessVerifyAPIView,
    SubscriptionConfirmAPIView,
)

app_name = "billing"

urlpatterns = [
    path("health/", BillingHealthAPIView.as_view(), name="billing-health"),
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
        "subscriptions/stripe/webhook/",
        StripeWebhookAPIView.as_view(),
        name="stripe-webhook",
    ),
]
