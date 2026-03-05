// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import BillingCheckoutResultPage from "./BillingCheckoutResultPage";

const mocks = vi.hoisted(() => ({
  confirmStripeSession: vi.fn(),
  confirmPaystackReference: vi.fn(),
  toastSuccess: vi.fn(),
  toastError: vi.fn(),
}));

vi.mock("@/services/subscription.service", () => ({
  subscriptionService: {
    confirmStripeSession: mocks.confirmStripeSession,
    confirmPaystackReference: mocks.confirmPaystackReference,
  },
}));

vi.mock("react-toastify", () => ({
  toast: {
    success: mocks.toastSuccess,
    error: mocks.toastError,
  },
}));

const renderAt = (url: string) => {
  return render(
    <MemoryRouter initialEntries={[url]}>
      <Routes>
        <Route path="/billing/success" element={<BillingCheckoutResultPage />} />
        <Route path="/billing/cancel" element={<BillingCheckoutResultPage />} />
      </Routes>
    </MemoryRouter>,
  );
};

describe("BillingCheckoutResultPage", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("confirms stripe session and renders success state", async () => {
    mocks.confirmStripeSession.mockResolvedValue({
      planId: "growth",
      planName: "Growth",
      billingCycle: "monthly",
      paymentMethod: "card",
      amountUsd: 399,
      reference: "cs_test_ok",
      confirmedAt: Date.now(),
      expiresAt: Date.now() + 60_000,
    });

    renderAt("/billing/success?next=%2Fsettings&stripe_session_id=cs_test_ok");

    expect(await screen.findByText(/payment confirmed/i)).toBeTruthy();
    expect(mocks.confirmStripeSession).toHaveBeenCalledTimes(1);
    expect(mocks.confirmStripeSession).toHaveBeenCalledWith("cs_test_ok");
  });

  it("shows explicit error when stripe_session_id is missing", async () => {
    renderAt("/billing/success?next=%2Fsettings");

    expect(await screen.findByText(/verification failed/i)).toBeTruthy();
    expect(await screen.findByText(/missing checkout reference/i)).toBeTruthy();
    expect(mocks.confirmStripeSession).not.toHaveBeenCalled();
    expect(mocks.confirmPaystackReference).not.toHaveBeenCalled();
  });

  it("supports retry after failed confirmation and eventually succeeds", async () => {
    mocks.confirmStripeSession
      .mockRejectedValueOnce({
        response: {
          data: {
            detail: "Session not ready",
          },
        },
      })
      .mockResolvedValueOnce({
        planId: "growth",
        planName: "Growth",
        billingCycle: "monthly",
        paymentMethod: "card",
        amountUsd: 399,
        reference: "cs_test_retry",
        confirmedAt: Date.now(),
        expiresAt: Date.now() + 60_000,
      });

    renderAt("/billing/success?stripe_session_id=cs_test_retry");

    expect(await screen.findByText(/verification failed/i)).toBeTruthy();
    expect(await screen.findByText(/session not ready/i)).toBeTruthy();
    expect(mocks.confirmStripeSession).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole("button", { name: /retry confirmation/i }));

    expect(await screen.findByText(/payment confirmed/i)).toBeTruthy();
    expect(mocks.confirmStripeSession).toHaveBeenCalledTimes(2);
  });

  it("renders checkout cancelled state on cancel route without confirmation call", async () => {
    renderAt("/billing/cancel?next=%2Fsettings&stripe_session_id=cs_test_cancelled");

    expect(await screen.findByText(/checkout cancelled/i)).toBeTruthy();
    expect(await screen.findByText(/no charge was completed/i)).toBeTruthy();
    expect(mocks.confirmStripeSession).not.toHaveBeenCalled();
    expect(mocks.confirmPaystackReference).not.toHaveBeenCalled();
  });

  it("confirms paystack reference and renders success state", async () => {
    mocks.confirmPaystackReference.mockResolvedValue({
      planId: "growth",
      planName: "Growth",
      billingCycle: "monthly",
      paymentMethod: "card",
      amountUsd: 399,
      reference: "OVS-PAYSTACK-REF",
      confirmedAt: Date.now(),
      expiresAt: Date.now() + 60_000,
    });

    renderAt("/billing/success?next=%2Fsettings&reference=OVS-PAYSTACK-REF");

    expect(await screen.findByText(/payment confirmed/i)).toBeTruthy();
    expect(mocks.confirmPaystackReference).toHaveBeenCalledTimes(1);
    expect(mocks.confirmPaystackReference).toHaveBeenCalledWith("OVS-PAYSTACK-REF");
    expect(mocks.confirmStripeSession).not.toHaveBeenCalled();
  });
});
