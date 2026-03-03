import React, { useCallback, useEffect, useRef, useState } from "react";
import { Link, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { AlertTriangle, CheckCircle2, Loader2, RotateCcw, XCircle } from "lucide-react";
import { toast } from "react-toastify";

import { subscriptionService } from "@/services/subscription.service";

const getErrorMessage = (error: unknown, fallback: string): string => {
  if (!error) return fallback;
  if (typeof error === "string") return error;
  if (error instanceof Error && error.message) return error.message;

  const candidate = error as {
    response?: { data?: { message?: string; detail?: string } };
  };

  return candidate.response?.data?.message || candidate.response?.data?.detail || fallback;
};

type ConfirmationStatus = "idle" | "processing" | "success" | "error";

const BillingCheckoutResultPage: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const stripeSessionId = searchParams.get("stripe_session_id") || "";

  const [status, setStatus] = useState<ConfirmationStatus>("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [retryCycle, setRetryCycle] = useState(0);

  const handledSessionRef = useRef<string | null>(null);

  const isSuccessRoute = location.pathname === "/billing/success";
  const isCancelRoute = location.pathname === "/billing/cancel";

  const confirmStripeSession = useCallback(async (sessionId: string) => {
    setStatus("processing");
    setErrorMessage(null);

    try {
      await subscriptionService.confirmStripeSession(sessionId);
      setStatus("success");
      toast.success("Payment confirmed. Continue with organization registration.", {
        toastId: "billing-checkout-success",
      });
    } catch (error: unknown) {
      const message = getErrorMessage(error, "Unable to confirm Stripe checkout session.");
      setErrorMessage(message);
      setStatus("error");
      toast.error(message, { toastId: "billing-checkout-error" });
    }
  }, []);

  useEffect(() => {
    if (!isSuccessRoute) return undefined;
    if (!stripeSessionId) return undefined;
    if (handledSessionRef.current === `${stripeSessionId}:${retryCycle}`) return undefined;

    handledSessionRef.current = `${stripeSessionId}:${retryCycle}`;
    const timeout = window.setTimeout(() => {
      void confirmStripeSession(stripeSessionId);
    }, 0);

    return () => {
      window.clearTimeout(timeout);
    };
  }, [confirmStripeSession, isSuccessRoute, retryCycle, stripeSessionId]);

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
              onClick={() => navigate("/subscribe")}
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

  const hasMissingSession = isSuccessRoute && !stripeSessionId;

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
              ? "Missing Stripe session ID in callback URL."
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
              onClick={() => navigate("/subscribe")}
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
            Your subscription access has been activated. Continue to organization registration.
          </p>
          <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
            <button
              type="button"
              onClick={() => navigate("/register", { replace: true })}
              className="rounded-lg bg-cyan-700 px-4 py-2 text-sm font-semibold text-white hover:bg-cyan-800"
            >
              Continue to Register
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
          We are validating your checkout session with Stripe.
        </p>
      </section>
    </main>
  );
};

export default BillingCheckoutResultPage;


