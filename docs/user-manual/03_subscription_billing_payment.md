# 3) Subscription, Billing, and Payment Methods

## 3.1 Overview

OVS supports subscription onboarding and ongoing billing management from the application UI.

Supported providers:

- Stripe,
- Paystack,
- Sandbox/local management flow (in selected environments).

## 3.2 Typical Subscription Journey

1. User clicks **Get Started** from landing flow.
2. User selects plan and billing cycle.
3. User selects payment method/provider route.
4. Hosted checkout is opened (Stripe/Paystack).
5. User returns to callback URL:
   - `/billing/success?...`
   - `/billing/cancel?...`
6. Backend confirmation endpoint finalizes access ticket/subscription state.
7. User proceeds to login/registration flow.

## 3.3 Plans and Quotas

Plan limits are enforced by backend quota checks.

Examples of quota-constrained operations:

- candidate import volume,
- new candidate enrollment over plan threshold.

Quota state can be viewed via billing endpoints and related UI components.

## 3.4 Billing Management in Settings

From `/settings` for non-applicant users:

- View current subscription plan and status.
- Update payment method (provider-dependent).
- Schedule unsubscription (`cancel_at_period_end` style behavior).
- Retry failed or pending payment flows.

## 3.5 Important Behavior: Unsubscribe

Unsubscribing does not instantly terminate active service.

- Access remains valid until active period end.
- Cancellation effective date is displayed in settings/billing state.

## 3.6 Callback and Confirmation Behavior

Success callback page performs confirmation:

- Stripe confirmation using `stripe_session_id`.
- Paystack confirmation using reference keys:
  - `reference`,
  - `trxref`,
  - `paystack_reference`.

If confirmation fails:

- User can retry confirmation from the callback page.
- User can resume checkout if provider returns a resume URL.

## 3.7 Billing API Surfaces (User-Relevant)

- `GET /api/billing/health/`
- `GET /api/billing/exchange-rate/`
- `GET /api/billing/quotas/`
- `GET/PATCH/DELETE /api/billing/subscriptions/manage/`
- `POST /api/billing/subscriptions/manage/payment-method/update-session/`
- `POST /api/billing/subscriptions/manage/retry/`
- `POST /api/billing/subscriptions/confirm/`
- `POST /api/billing/subscriptions/access/verify/`
- Stripe:
  - `POST /api/billing/subscriptions/stripe/checkout-session/`
  - `POST /api/billing/subscriptions/stripe/confirm/`
  - `POST /api/billing/subscriptions/stripe/webhook/`
- Paystack:
  - `POST /api/billing/subscriptions/paystack/checkout-session/`
  - `POST /api/billing/subscriptions/paystack/confirm/`
  - `POST /api/billing/subscriptions/paystack/webhook/`

## 3.8 Multi-Currency Notes

- Stripe is typically USD-centric in this project flow.
- Paystack can operate with local currency configurations.
- Exchange-rate endpoint is available for conversion-aware UI and billing display logic.

## 3.9 Troubleshooting Billing Flow

If callback page hangs or fails:

1. Confirm callback URL includes session/reference parameter.
2. Check backend billing confirmation endpoint response.
3. Inspect provider webhook delivery status.
4. Use manual confirm endpoint for reconciliation.
5. Verify `STRIPE_*`, `PAYSTACK_*`, and exchange-rate env configuration.

