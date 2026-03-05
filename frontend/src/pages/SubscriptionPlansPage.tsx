import React, { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  ArrowLeft,
  BadgeCheck,
  Banknote,
  Check,
  CreditCard,
  ShieldCheck,
  Smartphone,
  Sparkles,
} from "lucide-react";
import { toast } from "react-toastify";

import type { BillingCycle, PaymentMethod } from "@/utils/subscriptionAccess";
import { Button } from "@/components/ui/button";
import {
  subscriptionService,
  type HostedCheckoutProvider,
} from "@/services/subscription.service";

const env = (import.meta as { env?: Record<string, string | undefined> }).env;

interface Plan {
  id: string;
  name: string;
  subtitle: string;
  monthlyPriceUsd: number;
  annualPriceUsd: number;
  highlights: string[];
  featured?: boolean;
}

const plans: Plan[] = [
  {
    id: "starter",
    name: "Starter",
    subtitle: "For small HR teams",
    monthlyPriceUsd: 149,
    annualPriceUsd: 1490,
    highlights: [
      "Up to 150 candidates per month",
      "Document vetting + AI interview",
      "Email candidate invitations",
      "Standard support",
    ],
  },
  {
    id: "growth",
    name: "Growth",
    subtitle: "For scaling vetting operations",
    monthlyPriceUsd: 399,
    annualPriceUsd: 3990,
    featured: true,
    highlights: [
      "Up to 600 candidates per month",
      "Identity match + risk flags",
      "Priority processing",
      "Webhook + API support",
    ],
  },
  {
    id: "enterprise",
    name: "Enterprise",
    subtitle: "For regulated organizations",
    monthlyPriceUsd: 999,
    annualPriceUsd: 9990,
    highlights: [
      "Unlimited candidates",
      "Custom rubric orchestration",
      "Dedicated onboarding",
      "SLA + compliance package",
    ],
  },
];

const hostedProviderConfig: Record<
  HostedCheckoutProvider,
  { label: string; description: string }
> = {
  stripe: {
    label: "Stripe",
    description: "Best for global card payments.",
  },
  paystack: {
    label: "Paystack",
    description: "Supports cards and mobile money routes.",
  },
};

const paymentMethods: {
  id: PaymentMethod;
  label: string;
  description: string;
  icon: React.ReactNode;
}[] = [
  {
    id: "card",
    label: "Credit/Debit Card",
    description: "Immediate activation after authorization.",
    icon: <CreditCard className="h-4 w-4" />,
  },
  {
    id: "bank_transfer",
    label: "Bank Transfer",
    description: "Best for procurement workflows.",
    icon: <Banknote className="h-4 w-4" />,
  },
  {
    id: "mobile_money",
    label: "Mobile Money",
    description: "Alternative local payment route.",
    icon: <Smartphone className="h-4 w-4" />,
  },
];

const PAYSTACK_CURRENCY = (() => {
  const raw = String(env?.VITE_PAYSTACK_CURRENCY || "GHS").trim().toUpperCase();
  if (/^[A-Z]{3}$/.test(raw)) return raw;
  return "USD";
})();

const EXCHANGE_RATE_API_URL = String(
  env?.VITE_EXCHANGE_RATE_API_URL || env?.EXCHANGE_RATE_API_URL || "",
).trim();

const PAYSTACK_USD_EXCHANGE_RATE = (() => {
  const raw = Number(env?.VITE_PAYSTACK_USD_EXCHANGE_RATE || "1");
  if (Number.isFinite(raw) && raw > 0) return raw;
  return 1;
})();

const isTestMode = String(env?.MODE || "").toLowerCase() === "test";

const getDisplayCurrency = (provider: HostedCheckoutProvider | null): string => {
  if (provider === "paystack") return PAYSTACK_CURRENCY;
  return "USD";
};

const buildExchangeRateApiUrl = (
  baseCurrency: string,
  targetCurrency: string,
): string | null => {
  if (!EXCHANGE_RATE_API_URL) return null;

  if (
    EXCHANGE_RATE_API_URL.includes("{base}") ||
    EXCHANGE_RATE_API_URL.includes("{target}") ||
    EXCHANGE_RATE_API_URL.includes("{from}") ||
    EXCHANGE_RATE_API_URL.includes("{to}")
  ) {
    return EXCHANGE_RATE_API_URL.replace("{base}", baseCurrency)
      .replace("{target}", targetCurrency)
      .replace("{from}", baseCurrency)
      .replace("{to}", targetCurrency);
  }

  try {
    const apiUrl = new URL(EXCHANGE_RATE_API_URL);
    if (!apiUrl.searchParams.has("base")) {
      apiUrl.searchParams.set("base", baseCurrency);
    }
    if (!apiUrl.searchParams.has("symbols")) {
      apiUrl.searchParams.set("symbols", targetCurrency);
    }
    return apiUrl.toString();
  } catch {
    return EXCHANGE_RATE_API_URL;
  }
};

const extractExchangeRate = (payload: unknown, targetCurrency: string): number | null => {
  if (!payload || typeof payload !== "object") return null;
  const target = targetCurrency.trim().toUpperCase();
  if (!target) return null;
  const payloadRecord = payload as Record<string, unknown>;

  const toPositiveNumber = (value: unknown): number | null => {
    const num = Number(value);
    if (Number.isFinite(num) && num > 0) return num;
    return null;
  };

  const fromMap = (source: unknown): number | null => {
    if (!source || typeof source !== "object") return null;
    const map = source as Record<string, unknown>;
    const direct = toPositiveNumber(map[target] ?? map[target.toLowerCase()]);
    if (direct !== null) return direct;
    return null;
  };

  for (const key of ["conversion_rates", "rates", "data"]) {
    const rate = fromMap(payloadRecord[key]);
    if (rate !== null) return rate;
  }

  for (const key of ["rate", "exchange_rate", "conversion_rate", "price", "value"]) {
    const rate = toPositiveNumber(payloadRecord[key]);
    if (rate !== null) return rate;
  }

  const resultMap = payloadRecord.result;
  const resultRate = fromMap(resultMap);
  if (resultRate !== null) return resultRate;

  return null;
};

const convertUsdToDisplayAmount = (
  amountUsd: number,
  provider: HostedCheckoutProvider | null,
  paystackUsdExchangeRate: number,
): number => {
  if (provider === "paystack" && PAYSTACK_CURRENCY !== "USD") {
    return amountUsd * paystackUsdExchangeRate;
  }
  return amountUsd;
};

const formatCurrencyAmount = (amount: number, currency: string): string => {
  try {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency,
      maximumFractionDigits: 0,
    }).format(amount);
  } catch {
    return `${currency} ${amount.toFixed(2)}`;
  }
};

const getErrorMessage = (error: unknown, fallback: string): string => {
  if (!error) return fallback;
  if (typeof error === "string") return error;
  if (error instanceof Error && error.message) return error.message;

  const candidate = error as {
    response?: { data?: { message?: string; detail?: string } };
  };

  return candidate.response?.data?.message || candidate.response?.data?.detail || fallback;
};

const normalizeReturnPath = (value: string | null | undefined, fallback: string): string => {
  if (!value) return fallback;
  if (!value.startsWith("/") || value.startsWith("//")) return fallback;
  if (value.startsWith("/billing/")) return fallback;
  return value;
};

export const SubscriptionPlansPage: React.FC = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const [selectedPlanId, setSelectedPlanId] = useState<string>("growth");
  const [billingCycle, setBillingCycle] = useState<BillingCycle>("monthly");
  const [paymentMethod, setPaymentMethod] = useState<PaymentMethod>("card");
  const [customerEmail, setCustomerEmail] = useState("");
  const [isProcessing, setIsProcessing] = useState(false);
  const [paystackUsdExchangeRate, setPaystackUsdExchangeRate] = useState(PAYSTACK_USD_EXCHANGE_RATE);

  const checkoutMode = subscriptionService.getCheckoutMode();
  const hostedProviders = subscriptionService.getHostedCheckoutProviders();
  const hasHostedCheckout = hostedProviders.length > 0;
  const [selectedHostedProvider, setSelectedHostedProvider] =
    useState<HostedCheckoutProvider | null>(hostedProviders[0] ?? null);

  useEffect(() => {
    if (!hasHostedCheckout) {
      if (selectedHostedProvider !== null) {
        setSelectedHostedProvider(null);
      }
      return;
    }

    if (!selectedHostedProvider || !hostedProviders.includes(selectedHostedProvider)) {
      setSelectedHostedProvider(hostedProviders[0]);
    }
  }, [hasHostedCheckout, hostedProviders, selectedHostedProvider]);

  useEffect(() => {
    if (selectedHostedProvider === "stripe" && paymentMethod !== "card") {
      setPaymentMethod("card");
    }
  }, [paymentMethod, selectedHostedProvider]);

  useEffect(() => {
    if (isTestMode) return undefined;
    if (PAYSTACK_CURRENCY === "USD") return undefined;
    const rateApiUrl = buildExchangeRateApiUrl("USD", PAYSTACK_CURRENCY);
    if (!rateApiUrl) return undefined;

    let isActive = true;
    const abortController = new AbortController();

    const fetchExchangeRate = async () => {
      try {
        const response = await fetch(rateApiUrl, {
          method: "GET",
          signal: abortController.signal,
        });
        if (!response.ok) return;

        const payload = (await response.json()) as unknown;
        const liveRate = extractExchangeRate(payload, PAYSTACK_CURRENCY);
        if (isActive && liveRate && liveRate > 0) {
          setPaystackUsdExchangeRate(liveRate);
        }
      } catch {
        // Ignore API failures and keep configured fallback rate.
      }
    };

    void fetchExchangeRate();

    return () => {
      isActive = false;
      abortController.abort();
    };
  }, []);

  const defaultReturnPath = "/register";
  const returnToPath = normalizeReturnPath(searchParams.get("returnTo"), defaultReturnPath);

  const selectedPlan = useMemo(
    () => plans.find((plan) => plan.id === selectedPlanId) ?? plans[0],
    [selectedPlanId],
  );

  const amountUsd =
    billingCycle === "monthly"
      ? selectedPlan.monthlyPriceUsd
      : selectedPlan.annualPriceUsd;

  const annualSavings = useMemo(() => {
    if (billingCycle === "monthly") return 0;
    const annualFromMonthly = selectedPlan.monthlyPriceUsd * 12;
    return Math.max(0, annualFromMonthly - selectedPlan.annualPriceUsd);
  }, [billingCycle, selectedPlan]);
  const displayCurrency = getDisplayCurrency(selectedHostedProvider);
  const displayAmount = convertUsdToDisplayAmount(
    amountUsd,
    selectedHostedProvider,
    paystackUsdExchangeRate,
  );
  const displayAnnualSavings = convertUsdToDisplayAmount(
    annualSavings,
    selectedHostedProvider,
    paystackUsdExchangeRate,
  );

  const effectivePaymentMethod: PaymentMethod =
    selectedHostedProvider === "stripe" ? "card" : paymentMethod;

  const selectedPaymentMethodLabel =
    paymentMethods.find((method) => method.id === effectivePaymentMethod)?.label ?? "N/A";
  const selectedProviderLabel = selectedHostedProvider
    ? hostedProviderConfig[selectedHostedProvider].label
    : "Internal";
  const selectedProviderDescription = selectedHostedProvider
    ? hostedProviderConfig[selectedHostedProvider].description
    : "Direct API confirmation flow.";

  const handleConfirmSubscription = async () => {
    if (isProcessing) return;

    setIsProcessing(true);

    try {
      if (hasHostedCheckout && selectedHostedProvider === "stripe") {
        const origin =
          typeof window !== "undefined" && window.location?.origin
            ? window.location.origin
            : "http://localhost:3000";
        const encodedReturnPath = encodeURIComponent(returnToPath);
        const session = await subscriptionService.beginStripeCheckout({
          planId: selectedPlan.id,
          planName: selectedPlan.name,
          billingCycle,
          paymentMethod: "card",
          amountUsd,
          successUrl: `${origin}/billing/success?next=${encodedReturnPath}`,
          cancelUrl: `${origin}/billing/cancel?next=${encodedReturnPath}`,
        });

        window.location.assign(session.checkout_url);
        return;
      }

      if (hasHostedCheckout && selectedHostedProvider === "paystack") {
        const normalizedCustomerEmail = customerEmail.trim().toLowerCase();

        const origin =
          typeof window !== "undefined" && window.location?.origin
            ? window.location.origin
            : "http://localhost:3000";
        const encodedReturnPath = encodeURIComponent(returnToPath);
        const session = await subscriptionService.beginPaystackCheckout({
          planId: selectedPlan.id,
          planName: selectedPlan.name,
          billingCycle,
          paymentMethod: effectivePaymentMethod,
          amountUsd,
          customerEmail: normalizedCustomerEmail || undefined,
          successUrl: `${origin}/billing/success?next=${encodedReturnPath}`,
          cancelUrl: `${origin}/billing/cancel?next=${encodedReturnPath}`,
        });

        window.location.assign(session.checkout_url);
        return;
      }

      if (hasHostedCheckout && !selectedHostedProvider) {
        toast.error("Select a billing provider to continue.");
        return;
      }

      const result = await subscriptionService.confirmSubscription({
        planId: selectedPlan.id,
        planName: selectedPlan.name,
        billingCycle,
        paymentMethod: effectivePaymentMethod,
        amountUsd,
      });

      if (result.source === "mock") {
        toast.success("Sandbox subscription confirmed. Continue with registration.");
      } else {
        toast.success("Subscription confirmed. Continue with organization registration.");
      }

      navigate(returnToPath, { replace: true });
    } catch (error: unknown) {
      toast.error(getErrorMessage(error, "Subscription confirmation failed."), {
        toastId: "subscription-confirm-error",
      });
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <div className="relative min-h-screen overflow-hidden bg-slate-100 px-4 py-8 sm:px-6 lg:px-8">
      <div className="pointer-events-none absolute -left-20 top-6 h-72 w-72 rounded-full bg-cyan-200/50 blur-3xl" />
      <div className="pointer-events-none absolute -right-20 bottom-0 h-80 w-80 rounded-full bg-amber-200/45 blur-3xl" />

      <div className="relative mx-auto max-w-7xl">
        <header className="mb-8 rounded-3xl border border-slate-200 bg-white p-6 shadow-[0_20px_60px_-45px_rgba(15,23,42,0.8)] sm:p-8">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="inline-flex items-center gap-2 rounded-full border border-cyan-200 bg-cyan-50 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-cyan-800">
              <Sparkles className="h-3.5 w-3.5" />
              Subscription onboarding
            </div>
            <button
              type="button"
              onClick={() => navigate("/")}
              className="inline-flex items-center gap-2 rounded-lg border border-slate-700 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 transition hover:bg-slate-100"
            >
              <ArrowLeft className="h-3.5 w-3.5" />
              Back home
            </button>
          </div>

          <div className="mt-5 grid gap-5 lg:grid-cols-5">
            <div className="lg:col-span-3">
              <h1 className="text-3xl font-black tracking-tight text-slate-900 sm:text-4xl">
                Activate your firm workspace
              </h1>
              <p className="mt-3 max-w-2xl text-sm text-slate-700 sm:text-base">
                Registration stays locked until subscription is confirmed. Choose a plan,
                confirm payment mode, then continue to organization account setup.
              </p>
              <p className="mt-2 text-xs font-semibold uppercase tracking-wide text-slate-700">
                Next step after payment: {returnToPath}
              </p>
            </div>

            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4 lg:col-span-2">
              <div className="flex items-start gap-2">
                <ShieldCheck className="mt-0.5 h-4 w-4 text-emerald-700" />
                <p className="text-xs text-slate-700">
                  Access ticket validity: <span className="font-semibold">24 hours</span>. Complete registration before expiration.
                </p>
              </div>
            </div>
          </div>
        </header>

        <div className="mb-6 inline-flex rounded-xl border border-slate-700 bg-white p-1 shadow-sm">
          <button
            type="button"
            onClick={() => setBillingCycle("monthly")}
            className={`rounded-lg px-4 py-2 text-sm font-semibold transition ${
              billingCycle === "monthly"
                ? "bg-cyan-700 text-white"
                : "text-slate-700 hover:bg-slate-100"
            }`}
          >
            Monthly
          </button>
          <button
            type="button"
            onClick={() => setBillingCycle("annual")}
            className={`rounded-lg px-4 py-2 text-sm font-semibold transition ${
              billingCycle === "annual"
                ? "bg-cyan-700 text-white"
                : "text-slate-700 hover:bg-slate-100"
            }`}
          >
            Annual (2 months free)
          </button>
        </div>

        <section className="grid gap-5 lg:grid-cols-3">
          {plans.map((plan) => {
            const planPrice =
              billingCycle === "monthly" ? plan.monthlyPriceUsd : plan.annualPriceUsd;
            const planDisplayPrice = convertUsdToDisplayAmount(
              planPrice,
              selectedHostedProvider,
              paystackUsdExchangeRate,
            );
            const selected = plan.id === selectedPlanId;

            return (
              <button
                key={plan.id}
                type="button"
                onClick={() => setSelectedPlanId(plan.id)}
                className={`relative rounded-2xl border bg-white p-6 text-left transition ${
                  selected
                    ? "border-cyan-500 shadow-lg ring-2 ring-cyan-200"
                    : "border-slate-200 hover:border-cyan-300 hover:shadow"
                }`}
              >
                {plan.featured && (
                  <span className="absolute right-4 top-4 rounded-full bg-cyan-100 px-2.5 py-1 text-[11px] font-bold uppercase tracking-wide text-cyan-800">
                    Recommended
                  </span>
                )}

                <div className="mb-2 flex items-center gap-2">
                  <h2 className="text-xl font-black text-slate-900">{plan.name}</h2>
                  {selected && <BadgeCheck className="h-5 w-5 text-cyan-700" />}
                </div>

                <p className="text-sm text-slate-700">{plan.subtitle}</p>

                <p className="mt-4 text-3xl font-black text-slate-900">
                  {formatCurrencyAmount(planDisplayPrice, displayCurrency)}
                  <span className="ml-1 text-sm font-medium text-slate-700">
                    /{billingCycle === "monthly" ? "mo" : "yr"}
                  </span>
                </p>

                <ul className="mt-4 space-y-2">
                  {plan.highlights.map((item) => (
                    <li key={item} className="flex items-start gap-2 text-sm text-slate-700">
                      <Check className="mt-0.5 h-4 w-4 text-emerald-600" />
                      <span>{item}</span>
                    </li>
                  ))}
                </ul>
              </button>
            );
          })}
        </section>

        <section className="mt-8 grid gap-6 lg:grid-cols-5">
          <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm lg:col-span-3">
            <h3 className="text-lg font-black text-slate-900">Payment method</h3>
            <p className="mt-1 text-sm text-slate-700">Select your preferred payment route.</p>

            {hasHostedCheckout ? (
              <div className="mt-4 space-y-3">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-700">
                  Billing provider
                </p>
                <div className="grid gap-3 sm:grid-cols-2">
                  {hostedProviders.map((provider) => {
                    const selected = selectedHostedProvider === provider;
                    const config = hostedProviderConfig[provider];

                    return (
                      <button
                        key={provider}
                        type="button"
                        onClick={() => setSelectedHostedProvider(provider)}
                        className={`rounded-xl border p-4 text-left transition ${
                          selected
                            ? "border-cyan-500 bg-cyan-50"
                            : "border-slate-200 hover:border-cyan-300"
                        }`}
                      >
                        <p className="text-sm font-bold text-slate-900">{config.label}</p>
                        <p className="text-xs text-slate-700">{config.description}</p>
                      </button>
                    );
                  })}
                </div>
              </div>
            ) : null}

            <div className="mt-4 space-y-3">
              {paymentMethods.map((method) => {
                const selected = method.id === effectivePaymentMethod;
                const disabled =
                  selectedHostedProvider === "stripe" && method.id !== "card";

                return (
                  <button
                    key={method.id}
                    type="button"
                    onClick={() => {
                      if (!disabled) setPaymentMethod(method.id);
                    }}
                    disabled={disabled}
                    className={`flex w-full items-start gap-3 rounded-xl border p-4 text-left transition ${
                      selected
                        ? "border-cyan-500 bg-cyan-50"
                        : "border-slate-200 hover:border-cyan-300"
                    } ${disabled ? "cursor-not-allowed opacity-50" : ""}`}
                  >
                    <div className="rounded-lg bg-white p-2 text-cyan-700 ring-1 ring-slate-200">
                      {method.icon}
                    </div>
                    <div>
                      <p className="text-sm font-bold text-slate-900">{method.label}</p>
                      <p className="text-xs text-slate-700">{method.description}</p>
                    </div>
                  </button>
                );
              })}
            </div>

            {selectedHostedProvider === "stripe" && (
              <p className="mt-3 text-xs text-amber-700">
                Stripe checkout currently supports card payments in this flow.
              </p>
            )}
            {selectedHostedProvider === "paystack" && (
              <div className="mt-3 space-y-2">
                <label
                  htmlFor="paystack-customer-email"
                  className="block text-xs font-semibold uppercase tracking-wide text-slate-700"
                >
                  Billing Email
                </label>
                <input
                  id="paystack-customer-email"
                  type="email"
                  value={customerEmail}
                  onChange={(event) => setCustomerEmail(event.target.value)}
                  placeholder="billing@company.com"
                  className="w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 outline-none focus:ring-2 focus:ring-cyan-400"
                />
                <p className="text-xs text-slate-700">
                  Paystack requires an email for payment authorization and receipt. If signed in, your workspace email is used automatically.
                </p>
              </div>
            )}
            {hasHostedCheckout ? (
              <p className="mt-3 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-700">
                Routing: card can use Stripe or Paystack; mobile money and bank transfer are processed via Paystack.
              </p>
            ) : null}
          </div>

          <aside className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm lg:col-span-2">
            <h3 className="text-lg font-black text-slate-900">Order summary</h3>
            <dl className="mt-4 space-y-2 text-sm">
              <div className="flex items-center justify-between">
                <dt className="text-slate-700">Plan</dt>
                <dd className="font-semibold text-slate-900">{selectedPlan.name}</dd>
              </div>
              <div className="flex items-center justify-between">
                <dt className="text-slate-700">Billing cycle</dt>
                <dd className="font-semibold text-slate-900">
                  {billingCycle === "monthly" ? "Monthly" : "Annual"}
                </dd>
              </div>
              <div className="flex items-center justify-between">
                <dt className="text-slate-700">Provider</dt>
                <dd
                  className="inline-flex items-center rounded-full border border-slate-300 bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-900"
                  title={selectedProviderDescription}
                >
                  {selectedProviderLabel}
                </dd>
              </div>
              <div className="flex items-center justify-between">
                <dt className="text-slate-700">Payment</dt>
                <dd className="font-semibold text-slate-900">{selectedPaymentMethodLabel}</dd>
              </div>
              {annualSavings > 0 && (
                <div className="flex items-center justify-between">
                  <dt className="text-emerald-700">Annual savings</dt>
                  <dd className="font-bold text-emerald-700">
                    {formatCurrencyAmount(displayAnnualSavings, displayCurrency)}
                  </dd>
                </div>
              )}
              <div className="my-2 border-t border-slate-200" />
              <div className="flex items-center justify-between text-base">
                <dt className="font-bold text-slate-900">Total</dt>
                <dd className="text-xl font-black text-slate-900">
                  {formatCurrencyAmount(displayAmount, displayCurrency)}
                </dd>
              </div>
            </dl>

            <Button
              type="button"
              size="lg"
              onClick={handleConfirmSubscription}
              disabled={isProcessing}
              className="mt-6 h-12 w-full rounded-xl bg-cyan-700 text-sm font-bold text-white transition hover:bg-cyan-800"
            >
              {isProcessing
                ? selectedHostedProvider === "stripe"
                  ? "Preparing Stripe checkout..."
                  : selectedHostedProvider === "paystack"
                  ? "Preparing Paystack checkout..."
                  : "Confirming subscription..."
                : selectedHostedProvider === "stripe"
                ? "Continue to Stripe"
                : selectedHostedProvider === "paystack"
                ? "Continue to Paystack"
                : "Confirm and continue"}
            </Button>

            <p className="mt-3 text-xs text-slate-700">
              Checkout mode:{" "}
              {hasHostedCheckout
                ? hostedProviders.map((provider) => hostedProviderConfig[provider].label).join(" + ")
                : checkoutMode === "api"
                ? "API"
                : "Sandbox"}
              .
            </p>
            <p className="mt-1 text-xs text-slate-700">
              Selected provider: <span className="font-semibold text-slate-900">{selectedProviderLabel}</span>.
            </p>
            {selectedHostedProvider === "paystack" && displayCurrency !== "USD" ? (
              <p className="mt-1 text-xs text-slate-700">
                Paystack conversion rate: 1 USD = {paystackUsdExchangeRate} {displayCurrency}.
              </p>
            ) : null}
          </aside>
        </section>
      </div>
    </div>
  );
};

export default SubscriptionPlansPage;

