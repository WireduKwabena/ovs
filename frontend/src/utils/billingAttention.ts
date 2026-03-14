import type { BillingManagedSubscription } from "@/services/billing.service";

export interface BillingAttentionSummary {
  needsAttention: boolean;
  tone: "critical" | "warning" | "info";
  title: string;
  description: string;
}

export const getBillingAttentionSummary = (
  subscription: BillingManagedSubscription | null | undefined,
): BillingAttentionSummary => {
  if (!subscription) {
    return {
      needsAttention: false,
      tone: "info",
      title: "No active subscription",
      description:
        "No active subscription is attached to the current organization scope yet.",
    };
  }

  const normalizedStatus = String(subscription.status || "").trim().toLowerCase();
  const normalizedPaymentStatus = String(subscription.payment_status || "").trim().toLowerCase();

  if (["failed", "canceled", "cancelled", "expired"].includes(normalizedStatus)) {
    return {
      needsAttention: true,
      tone: "critical",
      title: "Billing needs attention",
      description:
        "The subscription is not in a healthy state. Review payment failures and billing runtime traces before candidates or staff are blocked.",
    };
  }

  if (["failed", "unpaid", "past_due"].includes(normalizedPaymentStatus)) {
    return {
      needsAttention: true,
      tone: "critical",
      title: "Payment issue detected",
      description:
        "The provider reported a payment problem for this subscription. Review payment-failure traces and retry or update the payment method if needed.",
    };
  }

  if (normalizedStatus === "open" || normalizedPaymentStatus === "pending") {
    return {
      needsAttention: true,
      tone: "warning",
      title: "Billing action is still pending",
      description:
        "A billing checkout or provider confirmation is still pending. Monitor the traces if confirmation does not complete as expected.",
    };
  }

  if (subscription.retry_available) {
    return {
      needsAttention: true,
      tone: "warning",
      title: "Retry is available",
      description:
        "The current subscription can be retried. Review the payment-failure trace first so the next billing attempt addresses the real issue.",
    };
  }

  if (subscription.cancel_at_period_end) {
    return {
      needsAttention: true,
      tone: "warning",
      title: "Cancellation is scheduled",
      description:
        "This subscription remains active for now, but access will end at the period boundary unless billing is restored or renewed.",
    };
  }

  return {
    needsAttention: false,
    tone: "info",
    title: "Billing is healthy",
    description:
      "No active billing incident is visible right now, but runtime and payment traces remain available for operational review.",
  };
};
