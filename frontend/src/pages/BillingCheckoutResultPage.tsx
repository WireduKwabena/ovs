import React, { useCallback, useEffect, useState } from "react";
import { Link, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { AlertTriangle, CheckCircle2, Loader2, RotateCcw, XCircle } from "lucide-react";
import { toast } from "react-toastify";

import { subscriptionService } from "@/services/subscription.service";

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

// Prevent duplicate confirmation requests in React StrictMode double-effect runs.
const inFlightConfirmationAttempts = new Set<string>();

const normalizeNextPath = (value: string | null, fallback: string): string => {
  if (!value) return fallback;
  if (!value.startsWith("/") || value.startsWith("//")) return fallback;
  if (value.startsWith("/billing/")) return fallback;
  return value;
};

const BillingCheckoutResultPage: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();
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
  const nextPath = normalizeNextPath(searchParams.get("next"), "/register");

  const [status, setStatus] = useState<ConfirmationStatus>("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [retryCycle, setRetryCycle] = useState(0);

  const normalizedPath = location.pathname.replace(/\/+$/, "") || "/";
  const isSuccessRoute = normalizedPath === "/billing/success";
  const isCancelRoute = normalizedPath === "/billing/cancel";

  const confirmHostedCheckout = useCallback(async (provider: "stripe" | "paystack", identifier: string) => {
    setStatus("processing");
    setErrorMessage(null);

    try {
      if (provider === "stripe") {
        await subscriptionService.confirmStripeSession(identifier);
      } else {
        await subscriptionService.confirmPaystackReference(identifier);
      }
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
      setErrorMessage(message);
      setStatus("error");
      toast.error(message, { toastId: "billing-checkout-error" });
    }
  }, []);

  useEffect(() => {
    if (!isSuccessRoute) return undefined;
    if (!checkoutProvider || !checkoutIdentifier) return undefined;
    const attemptKey = `${checkoutProvider}:${checkoutIdentifier}:${retryCycle}`;
    if (inFlightConfirmationAttempts.has(attemptKey)) return undefined;

    let isActive = true;
    inFlightConfirmationAttempts.add(attemptKey);
    queueMicrotask(() => {
      if (!isActive) {
        inFlightConfirmationAttempts.delete(attemptKey);
        return;
      }
      void confirmHostedCheckout(checkoutProvider, checkoutIdentifier).finally(() => {
        inFlightConfirmationAttempts.delete(attemptKey);
      });
    });
    return () => {
      isActive = false;
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
            No charge was completed. You can return to plans and try again.
          </p>
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
          <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
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
            Your subscription access has been activated.
          </p>
          <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
            <button
              type="button"
              onClick={() => navigate(nextPath, { replace: true })}
              className="rounded-lg bg-cyan-700 px-4 py-2 text-sm font-semibold text-white hover:bg-cyan-800"
            >
              Continue
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
          We are validating your checkout session.
        </p>
      </section>
    </main>
  );
};

export default BillingCheckoutResultPage;


