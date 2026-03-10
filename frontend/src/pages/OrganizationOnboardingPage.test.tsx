// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import OrganizationOnboardingPage from "./OrganizationOnboardingPage";

const mocks = vi.hoisted(() => ({
  useAuth: vi.fn(),
  getOnboardingTokenState: vi.fn(),
  getSubscriptionManagement: vi.fn(),
  generateOnboardingToken: vi.fn(),
  revokeOnboardingToken: vi.fn(),
  toastError: vi.fn(),
  toastSuccess: vi.fn(),
}));

vi.mock("@/hooks/useAuth", () => ({
  useAuth: () => mocks.useAuth(),
}));

vi.mock("@/services/billing.service", () => ({
  billingService: {
    getOnboardingTokenState: mocks.getOnboardingTokenState,
    getSubscriptionManagement: mocks.getSubscriptionManagement,
    generateOnboardingToken: mocks.generateOnboardingToken,
    revokeOnboardingToken: mocks.revokeOnboardingToken,
  },
}));

vi.mock("react-toastify", () => ({
  toast: {
    error: mocks.toastError,
    success: mocks.toastSuccess,
  },
}));

describe("OrganizationOnboardingPage", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("renders onboarding token state for org-admin users", async () => {
    mocks.useAuth.mockReturnValue({
      userType: "hr_manager",
      activeOrganization: { id: "org-1", code: "ORG1", name: "Org One", organization_type: "agency" },
      activeOrganizationId: "org-1",
      canManageActiveOrganizationGovernance: true,
    });
    mocks.getOnboardingTokenState.mockResolvedValue({
      status: "ok",
      organization_id: "org-1",
      organization_name: "Org One",
      subscription_id: "sub-1",
      subscription_active: true,
      has_active_token: true,
      token: {
        id: "tok-1",
        subscription_id: "sub-1",
        token_preview: "onb_1234",
        is_active: true,
        expires_at: null,
        max_uses: 25,
        uses: 2,
        remaining_uses: 23,
        allowed_email_domain: "",
        last_used_at: null,
        revoked_at: null,
        revoked_reason: "",
        created_at: "2026-01-01T00:00:00Z",
        updated_at: "2026-01-01T00:00:00Z",
      },
      organization_seat_limit: 25,
      organization_seat_used: 2,
      organization_seat_remaining: 23,
    });
    mocks.getSubscriptionManagement.mockResolvedValue({
      status: "ok",
      subscription: {
        id: "sub-1",
        provider: "paystack",
        status: "active",
        payment_status: "paid",
        plan_id: "growth",
        plan_name: "Growth",
        billing_cycle: "monthly",
        amount_usd: "399.00",
        payment_method: { type: "card", display: "Card", brand: "visa", last4: "4242", exp_month: 1, exp_year: 2030 },
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
        updated_at: "2026-01-01T00:00:00Z",
      },
    });

    render(
      <MemoryRouter>
        <OrganizationOnboardingPage />
      </MemoryRouter>,
    );

    expect(await screen.findByText(/manage member invite link/i)).toBeTruthy();
    expect(await screen.findByText(/preview:/i)).toBeTruthy();

    await waitFor(() => {
      expect(mocks.getOnboardingTokenState).toHaveBeenCalledTimes(1);
      expect(mocks.getSubscriptionManagement).toHaveBeenCalledTimes(1);
    });
  });
});

