// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import OrganizationDashboardPage from "./OrganizationDashboardPage";

const mocks = vi.hoisted(() => ({
  useAuth: vi.fn(),
  getOrganizationSummary: vi.fn(),
  getSubscriptionManagement: vi.fn(),
  getOnboardingTokenState: vi.fn(),
  toastError: vi.fn(),
  toastSuccess: vi.fn(),
}));

vi.mock("@/hooks/useAuth", () => ({
  useAuth: () => mocks.useAuth(),
}));

vi.mock("@/services/governance.service", () => ({
  governanceService: {
    getOrganizationSummary: mocks.getOrganizationSummary,
  },
}));

vi.mock("@/services/billing.service", () => ({
  billingService: {
    getSubscriptionManagement: mocks.getSubscriptionManagement,
    getOnboardingTokenState: mocks.getOnboardingTokenState,
  },
}));

vi.mock("react-toastify", () => ({
  toast: {
    error: mocks.toastError,
    success: mocks.toastSuccess,
  },
}));

describe("OrganizationDashboardPage", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("renders org-admin summary cards and onboarding context", async () => {
    mocks.useAuth.mockReturnValue({
      userType: "hr_manager",
      activeOrganization: { id: "org-1", code: "ORG1", name: "Org One", organization_type: "agency" },
      activeOrganizationId: "org-1",
      canManageActiveOrganizationGovernance: true,
    });
    mocks.getOrganizationSummary.mockResolvedValue({
      organization: {
        id: "org-1",
        code: "ORG1",
        name: "Org One",
        organization_type: "agency",
        is_active: true,
      },
      actor: {
        is_platform_admin: false,
        can_manage_registry: true,
        active_membership_id: "m-1",
        active_membership_role: "registry_admin",
      },
      stats: {
        members_total: 5,
        members_active: 4,
        committees_total: 2,
        committees_active: 2,
        committee_memberships_active: 7,
        active_chairs: 2,
      },
      active_organization_source: "header",
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
        max_uses: 10,
        uses: 1,
        remaining_uses: 9,
        allowed_email_domain: "",
        last_used_at: null,
        revoked_at: null,
        revoked_reason: "",
        created_at: "2026-01-01T00:00:00Z",
        updated_at: "2026-01-01T00:00:00Z",
      },
      organization_seat_limit: 10,
      organization_seat_used: 4,
      organization_seat_remaining: 6,
    });

    render(
      <MemoryRouter>
        <OrganizationDashboardPage />
      </MemoryRouter>,
    );

    expect(await screen.findByText(/organization dashboard/i)).toBeTruthy();
    expect(await screen.findByText("4")).toBeTruthy();
    expect(await screen.findByText(/token preview/i)).toBeTruthy();
    expect(await screen.findByRole("button", { name: /manage onboarding/i })).toBeTruthy();
  });

  it("shows active organization requirement when context is missing", async () => {
    mocks.useAuth.mockReturnValue({
      userType: "hr_manager",
      activeOrganization: null,
      activeOrganizationId: null,
      canManageActiveOrganizationGovernance: true,
    });

    render(
      <MemoryRouter>
        <OrganizationDashboardPage />
      </MemoryRouter>,
    );

    expect(await screen.findByText(/active organization required/i)).toBeTruthy();
  });
});

