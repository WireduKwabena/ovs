import React, { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "react-toastify";

import { Button } from "@/components/ui/button";
import {
  billingService,
  type BillingManagedSubscription,
} from "@/services/billing.service";
import { getBillingAttentionSummary } from "@/utils/billingAttention";
import {
  buildBillingPaymentFailureNotificationTraceHref,
  buildBillingProcessingErrorNotificationTraceHref,
} from "@/utils/notificationTrace";

interface BillingAttentionPanelProps {
  subscription: BillingManagedSubscription | null | undefined;
  onAfterAction?: () => Promise<void> | void;
  renewHref?: string;
}

const getErrorMessage = (error: unknown, fallback: string): string => {
  if (!error) return fallback;
  if (typeof error === "string") return error;
  if (error instanceof Error && error.message) return error.message;
  const payload = error as {
    response?: { data?: { detail?: string; error?: string; message?: string } };
    message?: string;
  };
  return (
    payload.response?.data?.detail ||
    payload.response?.data?.error ||
    payload.response?.data?.message ||
    payload.message ||
    fallback
  );
};

const formatDateTimeLabel = (value: string | null | undefined): string => {
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

const getProviderLabel = (provider: string | null | undefined): string => {
  const normalized = String(provider || "")
    .trim()
    .toLowerCase();
  if (normalized === "stripe") return "Stripe";
  if (normalized === "paystack") return "Paystack";
  if (normalized === "sandbox") return "Sandbox";
  return normalized
    ? normalized.charAt(0).toUpperCase() + normalized.slice(1)
    : "Billing";
};

const BillingAttentionPanel: React.FC<BillingAttentionPanelProps> = ({
  subscription,
  onAfterAction,
  renewHref,
}) => {
  const [activeAction, setActiveAction] = useState<"retry" | "payment" | null>(
    null,
  );
  const attention = useMemo(
    () => getBillingAttentionSummary(subscription),
    [subscription],
  );

  const panelStyles =
    attention.tone === "critical"
      ? "border-rose-200 bg-rose-50 text-rose-900"
      : attention.tone === "warning"
        ? "border-amber-200 bg-amber-50 text-amber-900"
        : "border-cyan-200 bg-cyan-50 text-cyan-900";
  const providerLabel = getProviderLabel(subscription?.provider);
  const nextActionHint = useMemo(() => {
    if (!subscription) return null;
    if (subscription.cancel_at_period_end && renewHref) {
      if (subscription.provider === "sandbox") {
        return "Renew before cutoff to confirm a replacement subscription without leaving the app.";
      }
      return `Renew before cutoff to start a fresh ${providerLabel} checkout and avoid service interruption.`;
    }
    if (subscription.retry_available) {
      if (subscription.provider === "sandbox") {
        return "Retry completes in-app and refreshes the current billing state when it succeeds.";
      }
      return `Retry opens a new ${providerLabel} hosted checkout for this subscription.`;
    }
    if (
      subscription.can_update_payment_method &&
      subscription.provider === "stripe"
    ) {
      return "Update payment method opens the Stripe billing portal in a hosted flow.";
    }
    return null;
  }, [providerLabel, renewHref, subscription]);

  const handleRetry = async () => {
    if (!subscription?.retry_available) return;
    setActiveAction("retry");
    try {
      const response = await billingService.retrySubscription();
      if (response.checkout_url) {
        window.open(response.checkout_url, "_self");
        return;
      }
      toast.success(response.message || "Billing retry started.");
      await onAfterAction?.();
    } catch (error) {
      toast.error(getErrorMessage(error, "Unable to retry billing."));
    } finally {
      setActiveAction(null);
    }
  };

  const handleUpdatePaymentMethod = async () => {
    if (
      !subscription?.can_update_payment_method ||
      subscription.provider !== "stripe"
    )
      return;
    setActiveAction("payment");
    try {
      const response = await billingService.createPaymentMethodUpdateSession();
      if (!response.url) {
        throw new Error("Billing portal URL is missing.");
      }
      window.open(response.url, "_self");
    } catch (error) {
      toast.error(
        getErrorMessage(error, "Unable to open payment method update flow."),
      );
      setActiveAction(null);
    }
  };

  return (
    <div className={`rounded-xl border p-4 text-xs ${panelStyles}`}>
      {subscription ? (
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <span className="inline-flex rounded-full border border-current/20 bg-white/70 px-2.5 py-1 text-[11px] font-semibold">
            Provider: {providerLabel}
          </span>
        </div>
      ) : null}
      <p className="font-semibold">{attention.title}</p>
      <p className="mt-1">{attention.description}</p>
      {nextActionHint ? (
        <p className="mt-2 text-[11px] font-medium opacity-90">
          Next action: {nextActionHint}
        </p>
      ) : null}
      {subscription?.latest_incident ? (
        <div className="mt-3 rounded-md border border-current/15 bg-white/70 px-3 py-2">
          <p className="font-semibold">Latest issue</p>
          <p className="mt-1">{subscription.latest_incident.message}</p>
          <p className="mt-1 text-[11px] opacity-80">
            Detected:{" "}
            {formatDateTimeLabel(subscription.latest_incident.detected_at)}
          </p>
        </div>
      ) : null}
      {subscription?.cancel_at_period_end ? (
        <div className="mt-3 rounded-md border border-current/15 bg-white/70 px-3 py-2">
          <p className="font-semibold">Cancellation timeline</p>
          <p className="mt-1">
            Current access ends{" "}
            {formatDateTimeLabel(
              subscription.cancellation_effective_at ||
                subscription.current_period_end,
            )}
            .
          </p>
        </div>
      ) : null}
      <div className="mt-3 flex flex-wrap gap-2">
        <Link
          to={buildBillingPaymentFailureNotificationTraceHref()}
          className="inline-flex items-center rounded-md border border-current/25 bg-white/70 px-2.5 py-1 font-medium hover:bg-white"
        >
          View payment failure notifications
        </Link>
        <Link
          to={buildBillingProcessingErrorNotificationTraceHref()}
          className="inline-flex items-center rounded-md border border-current/25 bg-white/70 px-2.5 py-1 font-medium hover:bg-white"
        >
          View billing error notifications
        </Link>
      </div>
      {subscription ? (
        <div className="mt-3 flex flex-wrap gap-2">
          {subscription.cancel_at_period_end && renewHref ? (
            <Link
              to={renewHref}
              className="inline-flex items-center rounded-md border border-current/25 bg-white/70 px-3 py-2 font-medium hover:bg-white"
            >
              Renew before cutoff
            </Link>
          ) : null}
          {subscription.retry_available ? (
            <Button
              type="button"
              variant="outline"
              disabled={activeAction !== null}
              onClick={() => void handleRetry()}
              className="border-current/25 bg-white/70 text-current hover:bg-white"
            >
              {activeAction === "retry" ? "Retrying..." : "Retry billing"}
            </Button>
          ) : null}
          {subscription.can_update_payment_method &&
          subscription.provider === "stripe" ? (
            <Button
              type="button"
              variant="outline"
              disabled={activeAction !== null}
              onClick={() => void handleUpdatePaymentMethod()}
              className="border-current/25 bg-white/70 text-current hover:bg-white"
            >
              {activeAction === "payment"
                ? "Opening..."
                : "Update payment method"}
            </Button>
          ) : null}
        </div>
      ) : null}
    </div>
  );
};

export default BillingAttentionPanel;
