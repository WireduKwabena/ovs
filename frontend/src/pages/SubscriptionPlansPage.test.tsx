// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import SubscriptionPlansPage from "./SubscriptionPlansPage";

const mocks = vi.hoisted(() => ({
  getCheckoutMode: vi.fn(),
  getHostedCheckoutProviders: vi.fn(),
  beginStripeCheckout: vi.fn(),
  beginPaystackCheckout: vi.fn(),
  getPaystackExchangeRate: vi.fn(),
  confirmSubscription: vi.fn(),
  toastSuccess: vi.fn(),
  toastError: vi.fn(),
  useAuth: vi.fn(),
}));

vi.mock("@/services/subscription.service", () => ({
  subscriptionService: {
    getCheckoutMode: mocks.getCheckoutMode,
    getHostedCheckoutProviders: mocks.getHostedCheckoutProviders,
    beginStripeCheckout: mocks.beginStripeCheckout,
    beginPaystackCheckout: mocks.beginPaystackCheckout,
    getPaystackExchangeRate: mocks.getPaystackExchangeRate,
    confirmSubscription: mocks.confirmSubscription,
  },
}));

vi.mock("react-toastify", () => ({
  toast: {
    success: mocks.toastSuccess,
    error: mocks.toastError,
  },
}));

vi.mock("@/hooks/useAuth", () => ({
  useAuth: () => mocks.useAuth(),
}));

const renderAt = (route = "/subscribe") => {
  return render(
    <MemoryRouter initialEntries={[route]}>
      <SubscriptionPlansPage />
    </MemoryRouter>,
  );
};

describe("SubscriptionPlansPage hosted checkout integration", () => {
  const locationAssignMock = vi.fn();

  beforeEach(() => {
    vi.stubGlobal("location", {
      ...(window.location as Location),
      assign: locationAssignMock,
    });
    mocks.useAuth.mockReturnValue({
      isAuthenticated: true,
      userType: "hr_manager",
      activeOrganizationId: "org-1",
      canManageActiveOrganizationGovernance: true,
    });
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
    vi.unstubAllGlobals();
  });

  it("starts Stripe checkout and redirects to Stripe URL", async () => {
    mocks.getCheckoutMode.mockReturnValue("paystack");
    mocks.getHostedCheckoutProviders.mockReturnValue(["stripe", "paystack"]);
    mocks.beginStripeCheckout.mockResolvedValue({
      provider: "stripe",
      session_id: "cs_test_123",
      checkout_url: "https://checkout.stripe.com/c/pay/cs_test_123",
    });

    renderAt();

    fireEvent.click(await screen.findByRole("button", { name: /continue to stripe/i }));

    await waitFor(() => {
      expect(mocks.beginStripeCheckout).toHaveBeenCalledTimes(1);
    });

    expect(mocks.beginStripeCheckout).toHaveBeenCalledWith(
      expect.objectContaining({
        planId: "growth",
        planName: "Growth",
        billingCycle: "monthly",
        paymentMethod: "card",
        amountUsd: 399,
      }),
    );

    const payload = mocks.beginStripeCheckout.mock.calls[0][0] as {
      successUrl: string;
      cancelUrl: string;
    };
    expect(payload.successUrl).toContain("/billing/success?next=%2Forganization%2Fonboarding");
    expect(payload.cancelUrl).toContain("/billing/cancel?next=%2Forganization%2Fonboarding");
    expect(locationAssignMock).toHaveBeenCalledWith("https://checkout.stripe.com/c/pay/cs_test_123");
  }, 15000);

  it("starts Paystack checkout for mobile money and redirects to Paystack URL", async () => {
    mocks.getCheckoutMode.mockReturnValue("paystack");
    mocks.getHostedCheckoutProviders.mockReturnValue(["stripe", "paystack"]);
    mocks.beginPaystackCheckout.mockResolvedValue({
      provider: "paystack",
      reference: "OVS-PAYSTACK-TEST",
      checkout_url: "https://checkout.paystack.com/OVS-PAYSTACK-TEST",
    });

    renderAt();

    fireEvent.click(await screen.findByRole("button", { name: /paystack/i }));
    fireEvent.click(await screen.findByRole("button", { name: /^mobile money/i }));
    expect(await screen.findByText(/source: configured fallback/i)).toBeTruthy();
    fireEvent.change(screen.getByLabelText(/billing email/i), {
      target: { value: "  PAYSTACK.TEST@EXAMPLE.COM " },
    });

    fireEvent.click(screen.getByRole("button", { name: /continue to paystack/i }));

    await waitFor(() => {
      expect(mocks.beginPaystackCheckout).toHaveBeenCalledTimes(1);
    });

    expect(mocks.beginPaystackCheckout).toHaveBeenCalledWith(
      expect.objectContaining({
        planId: "growth",
        planName: "Growth",
        billingCycle: "monthly",
        paymentMethod: "mobile_money",
        amountUsd: 399,
        customerEmail: "paystack.test@example.com",
      }),
    );

    const payload = mocks.beginPaystackCheckout.mock.calls[0][0] as {
      successUrl: string;
      cancelUrl: string;
    };
    expect(payload.successUrl).toContain("/billing/success?next=%2Forganization%2Fonboarding");
    expect(payload.cancelUrl).toContain("/billing/cancel?next=%2Forganization%2Fonboarding");
    expect(locationAssignMock).toHaveBeenCalledWith("https://checkout.paystack.com/OVS-PAYSTACK-TEST");
  }, 15000);

  it("blocks checkout when organization context is missing", async () => {
    mocks.useAuth.mockReturnValue({
      isAuthenticated: true,
      userType: "hr_manager",
      activeOrganizationId: null,
      canManageActiveOrganizationGovernance: false,
    });
    mocks.getCheckoutMode.mockReturnValue("paystack");
    mocks.getHostedCheckoutProviders.mockReturnValue(["stripe", "paystack"]);

    renderAt();

    const continueButton = await screen.findByRole("button", { name: /continue to stripe/i });
    expect((continueButton as HTMLButtonElement).disabled).toBe(true);
    expect(
      await screen.findByText(/no active organization context detected/i),
    ).toBeTruthy();
    expect(mocks.beginStripeCheckout).not.toHaveBeenCalled();
    expect(mocks.toastError).not.toHaveBeenCalled();
  });
});
