import React, { useCallback, useEffect, useState } from "react";
import { Link, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { AlertTriangle, CheckCircle2, Loader2, RotateCcw, XCircle } from "lucide-react";
import { toast } from "react-toastify";

import { subscriptionService } from "@/services/subscription.service";
import type { SubscriptionAccessTicket } from "@/utils/subscriptionAccess";

const getErrorMessage = (error: unknown, fallback: string): string => {
  if (!error) return fallback;
  if (typeof error === "string") return error;
  if (error instanceof Error && error.message) return error.message;

  const candidate = error as {
    response?: { data?: unknown };
  };
  const responseData = candidate.response?.data;

  if (Array.isArray(responseData)) {
    const first = responseData.find((item) => typeof item === "string");
    if (first) return first;
  }

  if (responseData && typeof responseData === "object") {
    const dataObject = responseData as {
      message?: unknown;
      detail?: unknown;
      [key: string]: unknown;
    };

    if (typeof dataObject.message === "string" && dataObject.message.trim()) {
      return dataObject.message;
    }

    if (typeof dataObject.detail === "string" && dataObject.detail.trim()) {
      return dataObject.detail;
    }

    if (Array.isArray(dataObject.detail)) {
      const detailItem = dataObject.detail.find((item) => typeof item === "string");
      if (detailItem) return detailItem;
    }

    for (const value of Object.values(dataObject)) {
      if (typeof value === "string" && value.trim()) return value;
      if (Array.isArray(value)) {
        const firstString = value.find((item) => typeof item === "string");
        if (firstString) return firstString;
      }
    }
  }

  return fallback;
};

type ConfirmationStatus = "idle" | "processing" | "success" | "error";

const getProviderLabel = (provider: "stripe" | "paystack" | null): string => {
  if (provider === "stripe") return "Stripe";
  if (provider === "paystack") return "Paystack";
  return "Hosted checkout";
};

const getPaymentMethodLabel = (paymentMethod: SubscriptionAccessTicket["paymentMethod"]): string => {
  if (paymentMethod === "mobile_money") return "Mobile money";
  if (paymentMethod === "bank_transfer") return "Bank transfer";
  return "Credit / debit card";
};

const formatTicketDateTime = (value: number | null | undefined): string => {
  if (!value) return "N/A";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "N/A";
  return parsed.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
};

const getContinueLabel = (path: string): string => {
  if (path === "/register") return "Create Account";
  if (path === "/admin/register") return "Create Admin Account";
  if (path === "/settings") return "Open Settings";
  if (path === "/organization/dashboard") return "Open Organization Dashboard";
  if (path === "/organization/onboarding") return "Open Organization Onboarding";
  if (path === "/login") return "Go to Login";
  return "Continue";
};

const getSuccessDescription = (path: string): string => {
  if (path === "/register") {
    return "Your payment is confirmed. Create your account now so you can start using the platform.";
  }
  if (path === "/admin/register") {
    return "Your payment is confirmed. Create the administrator account that will manage this workspace.";
  }
  if (path === "/settings") {
    return "Your subscription is active. You can review subscription details now or continue into the workspace.";
  }
  if (path === "/organization/dashboard") {
    return "Your organization subscription is active. Continue into the organization dashboard.";
  }
  if (path === "/login") {
    return "Your payment is confirmed. Sign in to continue.";
  }
  return "Your organization subscription is active. Continue into the organization workspace and complete onboarding setup.";
};

const getCancelDescription = (path: string): string => {
  if (path === "/register") {
    return "No charge was completed, so account creation is still locked. Return to plans when you're ready to continue.";
  }
  if (path === "/admin/register") {
    return "No charge was completed, so the administrator account is not unlocked yet. Return to plans when you're ready to continue.";
  }
  if (path === "/settings") {
    return "No charge was completed, so your billing update was not applied. You can return to plans and try again.";
  }
  if (path === "/organization/dashboard") {
    return "No charge was completed. Return to plans when you're ready to continue billing for this organization.";
  }
  if (path === "/login") {
    return "No charge was completed. Return to plans when you're ready, then sign in after payment is confirmed.";
  }
  return "No charge was completed. You can return to plans and try again.";
};

const getErrorRecoveryHint = (path: string): string => {
  if (path === "/register") {
    return "Return to plans to restart checkout. Once payment is confirmed, you can create your account.";
  }
  if (path === "/admin/register") {
    return "Return to plans to restart checkout. Once payment is confirmed, you can create the administrator account.";
  }
  if (path === "/settings") {
    return "Return to plans to restart this billing update, or review your current subscription settings before trying again.";
  }
  if (path === "/organization/dashboard") {
    return "Return to plans to restart billing for this organization, or continue into the dashboard to review the current state.";
  }
  if (path === "/login") {
    return "Return to plans to restart checkout. After payment is confirmed, sign in to continue.";
  }
  return "Return to plans to restart checkout when you are ready.";
};

const normalizeNextPath = (value: string | null, fallback: string): string => {
  if (!value) return fallback;
  if (!value.startsWith("/") || value.startsWith("//")) return fallback;
  if (value.startsWith("/billing/")) return fallback;
  return value;
};

const getCheckoutResumeUrl = (error: unknown): string | null => {
  if (!error || typeof error !== "object") return null;

  const candidate = error as { response?: { data?: unknown } };
  const responseData = candidate.response?.data;
  if (!responseData || typeof responseData !== "object" || Array.isArray(responseData)) {
    return null;
  }

  const value = (responseData as { checkout_url?: unknown }).checkout_url;
  if (typeof value !== "string") return null;
  const url = value.trim();
  if (!url) return null;

  try {
    const parsed = new URL(url);
    if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
      return null;
    }
    return url;
  } catch {
    return null;
  }
};

const BillingCheckoutResultPage: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const organizationDashboardPath = "/organization/dashboard";
  const onboardingManagementPath = "/organization/onboarding";
  const stripeSessionId = searchParams.get("stripe_session_id") || "";
  const paystackReference =
    searchParams.get("paystack_reference") ||
    searchParams.get("reference") ||
    searchParams.get("trxref") ||
    "";
  const checkoutProvider: "stripe" | "paystack" | null = stripeSessionId
    ? "stripe"
    : paystackReference
    ? "paystack"
    : null;
  const checkoutIdentifier = stripeSessionId || paystackReference;
  const nextPath = normalizeNextPath(searchParams.get("next"), onboardingManagementPath);

  const [status, setStatus] = useState<ConfirmationStatus>("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [resumeCheckoutUrl, setResumeCheckoutUrl] = useState<string | null>(null);
  const [retryCycle, setRetryCycle] = useState(0);
  const [confirmedTicket, setConfirmedTicket] = useState<SubscriptionAccessTicket | null>(null);

  const normalizedPath = location.pathname.replace(/\/+$/, "") || "/";
  const isSuccessRoute = normalizedPath === "/billing/success";
  const isCancelRoute = normalizedPath === "/billing/cancel";

  const confirmHostedCheckout = useCallback(async (provider: "stripe" | "paystack", identifier: string) => {
    setStatus("processing");
    setErrorMessage(null);
    setResumeCheckoutUrl(null);
    setConfirmedTicket(null);

    try {
      const ticket =
        provider === "stripe"
          ? await subscriptionService.confirmStripeSession(identifier)
          : await subscriptionService.confirmPaystackReference(identifier);
      setConfirmedTicket(ticket);
      setStatus("success");
      toast.success("Payment confirmed.", {
        toastId: "billing-checkout-success",
      });
    } catch (error: unknown) {
      const message = getErrorMessage(
        error,
        provider === "stripe"
          ? "Unable to confirm Stripe checkout session."
          : "Unable to confirm Paystack checkout session.",
      );
      setResumeCheckoutUrl(getCheckoutResumeUrl(error));
      setErrorMessage(message);
      setStatus("error");
      toast.error(message, { toastId: "billing-checkout-error" });
    }
  }, []);

  useEffect(() => {
    if (!isSuccessRoute) return undefined;
    if (!checkoutProvider || !checkoutIdentifier) return undefined;

    let isActive = true;
    const timerId = window.setTimeout(() => {
      if (!isActive) return;
      void confirmHostedCheckout(checkoutProvider, checkoutIdentifier);
    }, 0);

    return () => {
      isActive = false;
      window.clearTimeout(timerId);
    };
  }, [checkoutIdentifier, checkoutProvider, confirmHostedCheckout, isSuccessRoute, retryCycle]);

  if (isCancelRoute) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-slate-100 px-4 py-10">
        <section className="w-full max-w-xl rounded-3xl border border-slate-200 bg-white p-8 shadow-sm">
          <div className="mx-auto mb-4 inline-flex rounded-full bg-amber-100 p-3 text-amber-700">
            <XCircle className="h-6 w-6" />
          </div>
          <h1 className="text-center text-2xl font-black text-slate-900">Checkout Cancelled</h1>
          <p className="mt-3 text-center text-sm text-slate-700">
            {getCancelDescription(nextPath)}
          </p>
          <div className="mt-4 rounded-xl border border-slate-200 bg-slate-50 p-4 text-left text-xs text-slate-700">
            <p className="font-semibold text-slate-900">Provider summary</p>
            <p className="mt-2">
              Provider: <span className="font-semibold">{getProviderLabel(checkoutProvider)}</span>
            </p>
            <p className="mt-1">
              {checkoutProvider === "stripe"
                ? "Stripe checkout was cancelled before payment confirmation."
                : checkoutProvider === "paystack"
                  ? "Paystack checkout was cancelled before payment confirmation."
                  : "Hosted checkout was cancelled before payment confirmation."}
            </p>
          </div>
          <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
            <button
              type="button"
              onClick={() => navigate(`/subscribe?returnTo=${encodeURIComponent(nextPath)}`)}
              className="rounded-lg bg-cyan-700 px-4 py-2 text-sm font-semibold text-white hover:bg-cyan-800"
            >
              Back to Plans
            </button>
            <Link
              to="/login"
              className="rounded-lg border border-slate-700 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-100"
            >
              Go to Login
            </Link>
          </div>
        </section>
      </main>
    );
  }

  const hasMissingSession = isSuccessRoute && !checkoutIdentifier;

  if (hasMissingSession || status === "error") {
    return (
      <main className="flex min-h-screen items-center justify-center bg-slate-100 px-4 py-10">
        <section className="w-full max-w-xl rounded-3xl border border-rose-200 bg-white p-8 shadow-sm">
          <div className="mx-auto mb-4 inline-flex rounded-full bg-rose-100 p-3 text-rose-700">
            <AlertTriangle className="h-6 w-6" />
          </div>
          <h1 className="text-center text-2xl font-black text-slate-900">Verification Failed</h1>
          <p className="mt-3 text-center text-sm text-slate-700">
            {hasMissingSession
              ? "Missing checkout reference in callback URL."
              : errorMessage || "Unable to confirm payment at the moment."}
          </p>
          <p className="mt-2 text-center text-xs text-slate-600">{getErrorRecoveryHint(nextPath)}</p>
          {checkoutProvider ? (
            <div className="mt-4 rounded-xl border border-rose-100 bg-rose-50 p-4 text-left text-xs text-rose-900">
              <p className="font-semibold">Provider summary</p>
              <p className="mt-2">
                Provider: <span className="font-semibold">{getProviderLabel(checkoutProvider)}</span>
              </p>
              <p className="mt-1">
                {getProviderLabel(checkoutProvider)} checkout could not be confirmed yet.
              </p>
            </div>
          ) : null}
          <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
            {resumeCheckoutUrl ? (
              <a
                href={resumeCheckoutUrl}
                className="rounded-lg border border-cyan-600 px-4 py-2 text-sm font-semibold text-cyan-700 hover:bg-cyan-50"
              >
                Resume Checkout
              </a>
            ) : null}
            {!hasMissingSession ? (
              <button
                type="button"
                onClick={() => setRetryCycle((prev) => prev + 1)}
                className="inline-flex items-center gap-2 rounded-lg border border-cyan-600 px-4 py-2 text-sm font-semibold text-cyan-700 hover:bg-cyan-50"
              >
                <RotateCcw className="h-4 w-4" />
                Retry Confirmation
              </button>
            ) : null}
            <button
              type="button"
              onClick={() => navigate(`/subscribe?returnTo=${encodeURIComponent(nextPath)}`)}
              className="rounded-lg bg-cyan-700 px-4 py-2 text-sm font-semibold text-white hover:bg-cyan-800"
            >
              Back to Plans
            </button>
          </div>
        </section>
      </main>
    );
  }

  if (status === "success") {
    return (
      <main className="flex min-h-screen items-center justify-center bg-slate-100 px-4 py-10">
        <section className="w-full max-w-xl rounded-3xl border border-emerald-200 bg-white p-8 shadow-sm">
          <div className="mx-auto mb-4 inline-flex rounded-full bg-emerald-100 p-3 text-emerald-700">
            <CheckCircle2 className="h-6 w-6" />
          </div>
          <h1 className="text-center text-2xl font-black text-slate-900">Payment Confirmed</h1>
          <p className="mt-3 text-center text-sm text-slate-700">
            {getSuccessDescription(nextPath)}
          </p>
          <div className="mt-4 rounded-xl border border-emerald-100 bg-emerald-50 p-4 text-left text-xs text-emerald-900">
            <div className="flex flex-wrap items-center gap-2">
              <p className="font-semibold">Confirmation summary</p>
              {checkoutProvider ? (
                <span className="inline-flex rounded-full border border-emerald-200 bg-white px-2 py-0.5 text-[11px] font-semibold text-emerald-900">
                  Confirmed via {getProviderLabel(checkoutProvider)}
                </span>
              ) : null}
            </div>
            {confirmedTicket ? (
              <div className="mt-3 space-y-1">
                <p>
                  Plan: <span className="font-semibold">{confirmedTicket.planName}</span> ({confirmedTicket.billingCycle})
                </p>
                <p>
                  Payment route: <span className="font-semibold">{getPaymentMethodLabel(confirmedTicket.paymentMethod)}</span>
                </p>
                <p>
                  Reference: <span className="font-semibold">{confirmedTicket.reference}</span>
                </p>
                <p>
                  Confirmed: <span className="font-semibold">{formatTicketDateTime(confirmedTicket.confirmedAt)}</span>
                </p>
              </div>
            ) : null}
            <p className="mt-3">
              Next step: <span className="font-semibold">{getContinueLabel(nextPath)}</span>
            </p>
          </div>
          <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
            <button
              type="button"
              onClick={() => navigate(nextPath, { replace: true })}
              className="rounded-lg bg-cyan-700 px-4 py-2 text-sm font-semibold text-white hover:bg-cyan-800"
            >
              {getContinueLabel(nextPath)}
            </button>
            <button
              type="button"
              onClick={() => navigate(organizationDashboardPath)}
              className="rounded-lg border border-cyan-700 px-4 py-2 text-sm font-semibold text-cyan-700 hover:bg-cyan-50"
            >
              Open Organization Dashboard
            </button>
            <Link
              to="/login"
              className="rounded-lg border border-slate-700 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-100"
            >
              Go to Login
            </Link>
          </div>
        </section>
      </main>
    );
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-100 px-4 py-10">
      <section className="w-full max-w-xl rounded-3xl border border-slate-200 bg-white p-8 shadow-sm text-center">
        <div className="mx-auto mb-4 inline-flex rounded-full bg-cyan-100 p-3 text-cyan-700">
          <Loader2 className="h-6 w-6 animate-spin" />
        </div>
        <h1 className="text-2xl font-black text-slate-900">Confirming Payment</h1>
        <p className="mt-3 text-sm text-slate-700">
          We are validating your {checkoutProvider ? getProviderLabel(checkoutProvider) : "hosted checkout"} session.
        </p>
      </section>
    </main>
  );
};

export default BillingCheckoutResultPage;


