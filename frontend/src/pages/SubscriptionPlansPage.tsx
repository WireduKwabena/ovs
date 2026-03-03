import React, { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
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
import { subscriptionService } from "@/services/subscription.service";

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

const formatUsd = (amount: number): string => {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(amount);
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

export const SubscriptionPlansPage: React.FC = () => {
  const navigate = useNavigate();

  const [selectedPlanId, setSelectedPlanId] = useState<string>("growth");
  const [billingCycle, setBillingCycle] = useState<BillingCycle>("monthly");
  const [paymentMethod, setPaymentMethod] = useState<PaymentMethod>("card");
  const [isProcessing, setIsProcessing] = useState(false);

  const checkoutMode = subscriptionService.getCheckoutMode();

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

  const effectivePaymentMethod: PaymentMethod =
    checkoutMode === "stripe" ? "card" : paymentMethod;

  const selectedPaymentMethodLabel =
    paymentMethods.find((method) => method.id === effectivePaymentMethod)?.label ?? "N/A";

  const handleConfirmSubscription = async () => {
    if (isProcessing) return;

    setIsProcessing(true);

    try {
      if (checkoutMode === "stripe") {
        const session = await subscriptionService.beginStripeCheckout({
          planId: selectedPlan.id,
          planName: selectedPlan.name,
          billingCycle,
          paymentMethod: "card",
          amountUsd,
        });

        window.location.assign(session.checkout_url);
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

      navigate("/register", { replace: true });
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
                  {formatUsd(planPrice)}
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

            <div className="mt-4 space-y-3">
              {paymentMethods.map((method) => {
                const selected = method.id === effectivePaymentMethod;
                const disabled = checkoutMode === "stripe" && method.id !== "card";

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

            {checkoutMode === "stripe" && (
              <p className="mt-3 text-xs text-amber-700">
                Stripe checkout currently supports card payments in this flow.
              </p>
            )}
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
                <dt className="text-slate-700">Payment</dt>
                <dd className="font-semibold text-slate-900">{selectedPaymentMethodLabel}</dd>
              </div>
              {annualSavings > 0 && (
                <div className="flex items-center justify-between">
                  <dt className="text-emerald-700">Annual savings</dt>
                  <dd className="font-bold text-emerald-700">{formatUsd(annualSavings)}</dd>
                </div>
              )}
              <div className="my-2 border-t border-slate-200" />
              <div className="flex items-center justify-between text-base">
                <dt className="font-bold text-slate-900">Total</dt>
                <dd className="text-xl font-black text-slate-900">{formatUsd(amountUsd)}</dd>
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
                ? checkoutMode === "stripe"
                  ? "Preparing Stripe checkout..."
                  : "Confirming subscription..."
                : checkoutMode === "stripe"
                ? "Continue to Stripe"
                : "Confirm and continue"}
            </Button>

            <p className="mt-3 text-xs text-slate-700">
              Checkout mode: {checkoutMode === "api" ? "API" : checkoutMode === "stripe" ? "Stripe" : "Sandbox"}.
            </p>
          </aside>
        </section>
      </div>
    </div>
  );
};

export default SubscriptionPlansPage;

