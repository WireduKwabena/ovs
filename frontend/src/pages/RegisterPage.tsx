import React, { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { AlertTriangle, CheckCircle2, Loader2, Lock } from "lucide-react";
import { toast } from "react-toastify";

import { RegisterForm } from "@/components/auth/RegisterForm";
import {
  clearSubscriptionAccess,
  getSubscriptionAccessTicket,
  hasValidSubscriptionAccess,
} from "@/utils/subscriptionAccess";
import { subscriptionService } from "@/services/subscription.service";

const getReasonMessage = (reason: string): string => {
  switch (reason) {
    case "already_consumed":
      return "This subscription ticket has already been used for registration.";
    case "expired":
      return "This subscription ticket has expired. Please confirm subscription again.";
    case "not_complete":
      return "Subscription payment is not complete yet.";
    case "unpaid":
      return "Subscription payment is not in paid state yet.";
    case "not_found":
      return "Subscription ticket was not found.";
    default:
      return "Unable to verify subscription access.";
  }
};

const shouldClearLocalTicket = (reason: string): boolean => {
  return reason === "already_consumed" || reason === "expired" || reason === "not_found";
};

const parseRetryAfterSeconds = (value: unknown): number | null => {
  if (typeof value === "number" && Number.isFinite(value)) {
    return Math.max(1, Math.ceil(value));
  }

  if (typeof value === "string" && value.trim() !== "") {
    const parsed = Number(value);
    if (Number.isFinite(parsed) && parsed > 0) {
      return Math.ceil(parsed);
    }
  }

  return null;
};

export const RegisterPage: React.FC = () => {
  const navigate = useNavigate();
  const hasAccess = hasValidSubscriptionAccess();
  const ticket = getSubscriptionAccessTicket();
  const ticketReference = ticket?.reference;

  const [isVerifying, setIsVerifying] = useState(Boolean(hasAccess && ticketReference));
  const [isValidServerAccess, setIsValidServerAccess] = useState(false);
  const [verificationError, setVerificationError] = useState<string | null>(null);
  const [verificationCycle, setVerificationCycle] = useState(0);
  const [retryCooldownSeconds, setRetryCooldownSeconds] = useState(0);

  useEffect(() => {
    if (retryCooldownSeconds <= 0) return undefined;

    const timeout = window.setTimeout(() => {
      setRetryCooldownSeconds((prev) => (prev > 0 ? prev - 1 : 0));
    }, 1000);

    return () => {
      window.clearTimeout(timeout);
    };
  }, [retryCooldownSeconds]);

  const verifyTicketAccess = useCallback(async (reference: string) => {
    setIsVerifying(true);
    setVerificationError(null);

    try {
      const result = await subscriptionService.verifySubscriptionAccess(reference);

      if (result.valid) {
        setIsValidServerAccess(true);
        setRetryCooldownSeconds(0);
        return;
      }

      const message = getReasonMessage(result.reason);
      if (shouldClearLocalTicket(result.reason)) {
        clearSubscriptionAccess();
      }

      setIsValidServerAccess(false);
      setVerificationError(message);
      setRetryCooldownSeconds(0);
      toast.error(message);
    } catch (error: unknown) {
      setIsValidServerAccess(false);
      const axiosError = error as {
        response?: {
          status?: number;
          data?: { detail?: string };
          headers?: Record<string, unknown>;
        };
      };

      if (axiosError.response?.status === 429) {
        const retryHeader =
          axiosError.response.headers?.["retry-after"] ?? axiosError.response.headers?.["Retry-After"];
        const retryAfterSeconds = parseRetryAfterSeconds(retryHeader) ?? 30;
        const message =
          axiosError.response.data?.detail ||
          `Too many verification attempts. Please retry in ${retryAfterSeconds} seconds.`;

        setVerificationError(message);
        setRetryCooldownSeconds(retryAfterSeconds);
        toast.error(message);
        return;
      }

      const fallbackMessage = "Could not verify subscription access right now. Please retry.";
      setVerificationError(fallbackMessage);
      setRetryCooldownSeconds(0);
      toast.error(fallbackMessage);
    } finally {
      setIsVerifying(false);
    }
  }, []);

  useEffect(() => {
    if (!hasAccess || !ticketReference) {
      return;
    }

    void verifyTicketAccess(ticketReference);
  }, [hasAccess, ticketReference, verificationCycle, verifyTicketAccess]);

  const handleRetryVerification = () => {
    if (!ticketReference || retryCooldownSeconds > 0 || isVerifying) return;
    setVerificationCycle((prev) => prev + 1);
  };

  if (isVerifying) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
        <div className="w-full max-w-xl rounded-2xl border border-slate-200 bg-white p-8 text-center shadow-sm">
          <div className="mx-auto mb-4 inline-flex rounded-full bg-cyan-50 p-3 text-cyan-700">
            <Loader2 className="h-6 w-6 animate-spin" />
          </div>
          <h1 className="text-2xl font-bold text-slate-900">Verifying Access</h1>
          <p className="mt-3 text-sm text-slate-600">
            Validating your subscription ticket before registration.
          </p>
        </div>
      </div>
    );
  }

  if (!hasAccess || !ticket || !isValidServerAccess) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
        <div className="w-full max-w-xl rounded-2xl border border-slate-200 bg-white p-8 text-center shadow-sm">
          <div className="mx-auto mb-4 inline-flex rounded-full bg-amber-50 p-3 text-amber-700">
            {verificationError ? <AlertTriangle className="h-6 w-6" /> : <Lock className="h-6 w-6" />}
          </div>
          <h1 className="text-2xl font-bold text-slate-900">Subscription Required</h1>
          <p className="mt-3 text-sm text-slate-600">
            {verificationError || "Organization registration unlocks only after subscription confirmation."}
          </p>
          <div className="mt-6 flex items-center justify-center gap-3">
            {hasAccess && ticket && verificationError ? (
              <button
                type="button"
                onClick={handleRetryVerification}
                disabled={retryCooldownSeconds > 0 || isVerifying}
                className="rounded-lg border border-cyan-600 px-4 py-2 text-sm font-semibold text-cyan-700 hover:bg-cyan-50 disabled:cursor-not-allowed disabled:border-slate-300 disabled:text-slate-400 disabled:hover:bg-transparent"
              >
                {retryCooldownSeconds > 0
                  ? `Retry in ${retryCooldownSeconds}s`
                  : "Retry Verification"}
              </button>
            ) : null}
            <button
              type="button"
              onClick={() => navigate("/subscribe")}
              className="rounded-lg bg-cyan-700 px-4 py-2 text-sm font-semibold text-white hover:bg-cyan-800"
            >
              View Plans
            </button>
            <Link
              to="/"
              className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-100"
            >
              Back Home
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className="mx-auto mt-6 w-full max-w-4xl px-4 sm:px-6 lg:px-0">
        <div className="flex items-center justify-between rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-xs text-emerald-800">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4" />
            <span>
              Subscription confirmed: {ticket.planName} ({ticket.billingCycle}) • Ref {ticket.reference}
            </span>
          </div>
          <span>
            Expires {new Date(ticket.expiresAt).toLocaleString()}
          </span>
        </div>
      </div>
      <RegisterForm />
    </div>
  );
};

export default RegisterPage;
