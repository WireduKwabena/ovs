// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { StrictMode } from "react";

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

const renderAtStrict = (url: string) => {
  return render(
    <StrictMode>
      <MemoryRouter initialEntries={[url]}>
        <Routes>
          <Route path="/billing/success" element={<BillingCheckoutResultPage />} />
          <Route path="/billing/cancel" element={<BillingCheckoutResultPage />} />
        </Routes>
      </MemoryRouter>
    </StrictMode>,
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
    expect(await screen.findByText(/confirmed via stripe/i)).toBeTruthy();
    const summaryHeading = await screen.findByText(/confirmation summary/i);
    const summaryCard = summaryHeading.closest("div")?.parentElement;
    expect(summaryCard).toBeTruthy();
    expect(summaryCard?.textContent).toMatch(/payment route:\s*credit \/ debit card/i);
    expect(summaryCard?.textContent).toMatch(/next step:\s*open settings/i);
    expect(await screen.findByRole("button", { name: /open organization dashboard/i })).toBeTruthy();
    expect(mocks.confirmStripeSession).toHaveBeenCalledTimes(1);
    expect(mocks.confirmStripeSession).toHaveBeenCalledWith("cs_test_ok");
  });

  it("renders registration-specific success guidance when checkout returns to register", async () => {
    mocks.confirmStripeSession.mockResolvedValue({
      planId: "growth",
      planName: "Growth",
      billingCycle: "monthly",
      paymentMethod: "card",
      amountUsd: 399,
      reference: "cs_test_register",
      confirmedAt: Date.now(),
      expiresAt: Date.now() + 60_000,
    });

    renderAt("/billing/success?next=%2Fregister&stripe_session_id=cs_test_register");

    expect(await screen.findByText(/payment confirmed/i)).toBeTruthy();
    expect(
      await screen.findByText(/your payment is confirmed\. create your account now so you can start using the platform\./i),
    ).toBeTruthy();

    const summaryHeading = await screen.findByText(/confirmation summary/i);
    const summaryCard = summaryHeading.closest("div")?.parentElement;
    expect(summaryCard?.textContent).toMatch(/next step:\s*create account/i);
    expect(await screen.findByRole("button", { name: /create account/i })).toBeTruthy();
  });

  it("renders admin registration-specific success guidance when checkout returns to admin register", async () => {
    mocks.confirmStripeSession.mockResolvedValue({
      planId: "growth",
      planName: "Growth",
      billingCycle: "monthly",
      paymentMethod: "card",
      amountUsd: 399,
      reference: "cs_test_admin_register",
      confirmedAt: Date.now(),
      expiresAt: Date.now() + 60_000,
    });

    renderAt("/billing/success?next=%2Fadmin%2Fregister&stripe_session_id=cs_test_admin_register");

    expect(await screen.findByText(/payment confirmed/i)).toBeTruthy();
    expect(
      await screen.findByText(
        /your payment is confirmed\. create the administrator account that will manage this workspace\./i,
      ),
    ).toBeTruthy();

    const summaryHeading = await screen.findByText(/confirmation summary/i);
    const summaryCard = summaryHeading.closest("div")?.parentElement;
    expect(summaryCard?.textContent).toMatch(/next step:\s*create admin account/i);
    expect(await screen.findByRole("button", { name: /create admin account/i })).toBeTruthy();
  });

  it("shows explicit error when stripe_session_id is missing", async () => {
    renderAt("/billing/success?next=%2Fsettings");

    expect(await screen.findByText(/verification failed/i)).toBeTruthy();
    expect(await screen.findByText(/missing checkout reference/i)).toBeTruthy();
    expect(
      await screen.findByText(
        /return to plans to restart this billing update, or review your current subscription settings before trying again\./i,
      ),
    ).toBeTruthy();
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
    expect(await screen.findByText(/no charge was completed, so your billing update was not applied/i)).toBeTruthy();
    const providerSummaryHeading = await screen.findByText(/provider summary/i);
    const providerSummaryCard = providerSummaryHeading.parentElement;
    expect(providerSummaryCard).toBeTruthy();
    expect(providerSummaryCard?.textContent).toMatch(/provider:\s*stripe/i);
    expect(providerSummaryCard?.textContent).toMatch(/stripe checkout was cancelled before payment confirmation/i);
    expect(mocks.confirmStripeSession).not.toHaveBeenCalled();
    expect(mocks.confirmPaystackReference).not.toHaveBeenCalled();
  });

  it("renders registration-specific recovery guidance on error and cancel states", async () => {
    renderAt("/billing/cancel?next=%2Fregister&stripe_session_id=cs_test_register_cancel");

    expect(await screen.findByText(/checkout cancelled/i)).toBeTruthy();
    expect(
      await screen.findByText(
        /no charge was completed, so account creation is still locked\. return to plans when you're ready to continue\./i,
      ),
    ).toBeTruthy();

    cleanup();
    vi.clearAllMocks();

    renderAt("/billing/success?next=%2Fregister");

    expect(await screen.findByText(/verification failed/i)).toBeTruthy();
    expect(await screen.findByText(/missing checkout reference in callback url\./i)).toBeTruthy();
    expect(
      await screen.findByText(
        /return to plans to restart checkout\. once payment is confirmed, you can create your account\./i,
      ),
    ).toBeTruthy();
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
    expect(await screen.findByText(/confirmed via paystack/i)).toBeTruthy();
    expect(mocks.confirmPaystackReference).toHaveBeenCalledTimes(1);
    expect(mocks.confirmPaystackReference).toHaveBeenCalledWith("OVS-PAYSTACK-REF");
    expect(mocks.confirmStripeSession).not.toHaveBeenCalled();
  });

  it("renders paystack list error message from DRF response payload", async () => {
    mocks.confirmPaystackReference.mockRejectedValue({
      response: {
        data: ["Paystack transaction is not successful yet (status: abandoned)."],
      },
    });

    renderAt("/billing/success?reference=OVS-PAYSTACK-ABANDONED");

    expect(await screen.findByText(/verification failed/i)).toBeTruthy();
    expect(await screen.findByText(/paystack checkout could not be confirmed yet/i)).toBeTruthy();
    expect(
      await screen.findByText(/paystack transaction is not successful yet \(status: abandoned\)\./i),
    ).toBeTruthy();
    expect(mocks.confirmPaystackReference).toHaveBeenCalledTimes(1);
  });

  it("shows Resume Checkout link when backend returns checkout_url on confirmation failure", async () => {
    mocks.confirmPaystackReference.mockRejectedValue({
      response: {
        data: {
          detail: "Paystack transaction is not successful yet (status: abandoned).",
          checkout_url: "https://checkout.paystack.com/retry-flow",
        },
      },
    });

    renderAt("/billing/success?reference=OVS-PAYSTACK-RESUME");

    expect(await screen.findByText(/verification failed/i)).toBeTruthy();
    const resumeLink = await screen.findByRole("link", { name: /resume checkout/i });
    expect(resumeLink.getAttribute("href")).toBe("https://checkout.paystack.com/retry-flow");
  });

  it("retries same callback URL after remount even when prior attempt never resolved", async () => {
    mocks.confirmPaystackReference.mockImplementationOnce(
      () => new Promise(() => undefined),
    );

    renderAt("/billing/success?reference=OVS-PAYSTACK-STUCK");
    await waitFor(() => {
      expect(mocks.confirmPaystackReference).toHaveBeenCalledTimes(1);
    });

    cleanup();

    mocks.confirmPaystackReference.mockResolvedValueOnce({
      planId: "growth",
      planName: "Growth",
      billingCycle: "monthly",
      paymentMethod: "card",
      amountUsd: 399,
      reference: "OVS-PAYSTACK-STUCK",
      confirmedAt: Date.now(),
      expiresAt: Date.now() + 60_000,
    });

    renderAt("/billing/success?reference=OVS-PAYSTACK-STUCK");

    expect(await screen.findByText(/payment confirmed/i)).toBeTruthy();
    expect(mocks.confirmPaystackReference).toHaveBeenCalledTimes(2);
  });

  it("confirms paystack callback in React StrictMode", async () => {
    mocks.confirmPaystackReference.mockResolvedValue({
      planId: "growth",
      planName: "Growth",
      billingCycle: "monthly",
      paymentMethod: "mobile_money",
      amountUsd: 399,
      reference: "OVS-PAYSTACK-STRICT",
      confirmedAt: Date.now(),
      expiresAt: Date.now() + 60_000,
    });

    renderAtStrict("/billing/success?reference=OVS-PAYSTACK-STRICT");

    expect(await screen.findByText(/payment confirmed/i)).toBeTruthy();
    expect(mocks.confirmPaystackReference).toHaveBeenCalledTimes(1);
  });
});
