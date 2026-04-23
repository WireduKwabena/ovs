// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import BillingAttentionPanel from "./BillingAttentionPanel";

const mocks = vi.hoisted(() => ({
  retrySubscription: vi.fn(),
  createPaymentMethodUpdateSession: vi.fn(),
  toastSuccess: vi.fn(),
  toastError: vi.fn(),
}));

vi.mock("@/services/billing.service", async () => {
  const actual = await vi.importActual<
    typeof import("@/services/billing.service")
  >("@/services/billing.service");
  return {
    ...actual,
    billingService: {
      ...actual.billingService,
      retrySubscription: mocks.retrySubscription,
      createPaymentMethodUpdateSession: mocks.createPaymentMethodUpdateSession,
    },
  };
});

vi.mock("react-toastify", () => ({
  toast: {
    success: mocks.toastSuccess,
    error: mocks.toastError,
  },
}));

describe("BillingAttentionPanel", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("redirects to provider checkout when retry billing returns a checkout URL", async () => {
    const openSpy = vi.spyOn(window, "open").mockImplementation(() => null);
    mocks.retrySubscription.mockResolvedValue({
      status: "ok",
      provider: "paystack",
      message: "Retry checkout session created.",
      checkout_url: "https://checkout.example.com/retry",
    });

    render(
      <MemoryRouter>
        <BillingAttentionPanel
          subscription={{
            id: "sub-1",
            provider: "paystack",
            status: "failed",
            payment_status: "unpaid",
            plan_id: "growth",
            plan_name: "Growth",
            billing_cycle: "monthly",
            amount_usd: "399.00",
            payment_method: {
              type: "card",
              display: "Card",
              brand: null,
              last4: null,
              exp_month: null,
              exp_year: null,
            },
            checkout_url: null,
            current_period_start: null,
            current_period_end: null,
            cancel_at_period_end: false,
            cancellation_requested_at: null,
            cancellation_effective_at: null,
            can_update_payment_method: false,
            can_delete_payment_method: true,
            retry_available: true,
            retry_reason: "payment_failed",
            latest_incident: {
              code: "payment_failed",
              message:
                "Paystack reported a payment failure event (charge.failed).",
              detected_at: "2026-01-02T10:30:00Z",
              source: "paystack",
              event_type: "charge.failed",
            },
            updated_at: "2026-01-01T00:00:00Z",
          }}
        />
      </MemoryRouter>,
    );

    expect(screen.getByText(/provider: paystack/i)).toBeTruthy();
    expect(
      screen.getByText(/retry opens a new paystack hosted checkout/i),
    ).toBeTruthy();
    expect(
      screen
        .getByRole("link", {
          name: /view payment failure notifications/i,
        })
        .getAttribute("href"),
    ).toBe(
      "/notifications?channel=all&event_type=billing_payment_failed&subsystem=billing",
    );
    expect(
      screen
        .getByRole("link", {
          name: /view billing error notifications/i,
        })
        .getAttribute("href"),
    ).toBe(
      "/notifications?channel=all&event_type=processing_error&subsystem=billing",
    );
    fireEvent.click(screen.getByRole("button", { name: /retry billing/i }));

    await waitFor(() => {
      expect(mocks.retrySubscription).toHaveBeenCalledTimes(1);
    });
    expect(openSpy).toHaveBeenCalledWith(
      "https://checkout.example.com/retry",
      "_self",
    );
  });

  it("refreshes billing state after a sandbox retry without redirect", async () => {
    const afterAction = vi.fn().mockResolvedValue(undefined);
    const openSpy = vi.spyOn(window, "open").mockImplementation(() => null);
    mocks.retrySubscription.mockResolvedValue({
      status: "ok",
      provider: "sandbox",
      message: "Sandbox subscription retry confirmed.",
    });

    render(
      <MemoryRouter>
        <BillingAttentionPanel
          subscription={{
            id: "sub-2",
            provider: "sandbox",
            status: "failed",
            payment_status: "unpaid",
            plan_id: "starter",
            plan_name: "Starter",
            billing_cycle: "monthly",
            amount_usd: "149.00",
            payment_method: {
              type: "card",
              display: "Card",
              brand: null,
              last4: null,
              exp_month: null,
              exp_year: null,
            },
            checkout_url: null,
            current_period_start: null,
            current_period_end: null,
            cancel_at_period_end: false,
            cancellation_requested_at: null,
            cancellation_effective_at: null,
            can_update_payment_method: false,
            can_delete_payment_method: true,
            retry_available: true,
            retry_reason: "payment_failed",
            latest_incident: null,
            updated_at: "2026-01-01T00:00:00Z",
          }}
          onAfterAction={afterAction}
        />
      </MemoryRouter>,
    );

    expect(screen.getByText(/provider: sandbox/i)).toBeTruthy();
    expect(
      screen.getByText(
        /retry completes in-app and refreshes the current billing state/i,
      ),
    ).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /retry billing/i }));

    await waitFor(() => {
      expect(mocks.retrySubscription).toHaveBeenCalledTimes(1);
      expect(afterAction).toHaveBeenCalledTimes(1);
    });
    expect(openSpy).not.toHaveBeenCalled();
  });

  it("opens Stripe payment method update flow when available", async () => {
    const openSpy = vi.spyOn(window, "open").mockImplementation(() => null);
    mocks.createPaymentMethodUpdateSession.mockResolvedValue({
      status: "ok",
      provider: "stripe",
      url: "https://billing.example.com/portal",
    });

    render(
      <MemoryRouter>
        <BillingAttentionPanel
          subscription={{
            id: "sub-3",
            provider: "stripe",
            status: "complete",
            payment_status: "paid",
            plan_id: "growth",
            plan_name: "Growth",
            billing_cycle: "monthly",
            amount_usd: "399.00",
            payment_method: {
              type: "card",
              display: "Visa •••• 4242",
              brand: "visa",
              last4: "4242",
              exp_month: 1,
              exp_year: 2030,
            },
            checkout_url: null,
            current_period_start: null,
            current_period_end: null,
            cancel_at_period_end: false,
            cancellation_requested_at: null,
            cancellation_effective_at: null,
            can_update_payment_method: true,
            can_delete_payment_method: true,
            retry_available: false,
            retry_reason: null,
            latest_incident: {
              code: "retry_available",
              message: "Billing retry is available for this subscription.",
              detected_at: "2026-01-02T10:30:00Z",
              source: "stripe",
              event_type: null,
            },
            updated_at: "2026-01-01T00:00:00Z",
          }}
        />
      </MemoryRouter>,
    );

    expect(screen.getByText(/provider: stripe/i)).toBeTruthy();
    expect(
      screen.getByText(
        /update payment method opens the stripe billing portal/i,
      ),
    ).toBeTruthy();
    fireEvent.click(
      screen.getByRole("button", { name: /update payment method/i }),
    );

    await waitFor(() => {
      expect(mocks.createPaymentMethodUpdateSession).toHaveBeenCalledTimes(1);
    });
    expect(openSpy).toHaveBeenCalledWith(
      "https://billing.example.com/portal",
      "_self",
    );
  });

  it("shows a renewal path when cancellation is scheduled", () => {
    render(
      <MemoryRouter>
        <BillingAttentionPanel
          subscription={{
            id: "sub-4",
            provider: "stripe",
            status: "complete",
            payment_status: "paid",
            plan_id: "growth",
            plan_name: "Growth",
            billing_cycle: "monthly",
            amount_usd: "399.00",
            payment_method: {
              type: "card",
              display: "Visa •••• 4242",
              brand: "visa",
              last4: "4242",
              exp_month: 1,
              exp_year: 2030,
            },
            checkout_url: null,
            current_period_start: "2026-01-01T00:00:00Z",
            current_period_end: "2026-02-01T00:00:00Z",
            cancel_at_period_end: true,
            cancellation_requested_at: "2026-01-15T10:00:00Z",
            cancellation_effective_at: "2026-02-01T00:00:00Z",
            can_update_payment_method: true,
            can_delete_payment_method: false,
            retry_available: false,
            retry_reason: null,
            latest_incident: {
              code: "cancellation_scheduled",
              message:
                "Cancellation is scheduled at the end of the current billing period.",
              detected_at: "2026-02-01T00:00:00Z",
              source: "stripe",
              event_type: null,
            },
            updated_at: "2026-01-15T10:00:00Z",
          }}
          renewHref="/subscribe?returnTo=%2Forganization%2Fdashboard"
        />
      </MemoryRouter>,
    );

    expect(screen.getByText(/provider: stripe/i)).toBeTruthy();
    expect(
      screen.getByText(/renew before cutoff to start a fresh stripe checkout/i),
    ).toBeTruthy();
    expect(screen.getByText(/cancellation timeline/i)).toBeTruthy();
    expect(screen.getByText(/current access ends/i)).toBeTruthy();
    expect(
      screen
        .getByRole("link", { name: /renew before cutoff/i })
        .getAttribute("href"),
    ).toBe("/subscribe?returnTo=%2Forganization%2Fdashboard");
  });
});
