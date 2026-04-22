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

import OrgDashboardPage from "./OrgDashboardPage";

const mocks = vi.hoisted(() => ({
  navigate: vi.fn(),
  useAuth: vi.fn(),
  adminService: {
    getDashboard: vi.fn(),
  },
  governanceService: {
    getOrganizationSummary: vi.fn(),
  },
  billingService: {
    getOnboardingTokenState: vi.fn(),
    getSubscriptionManagement: vi.fn(),
  },
}));

vi.mock("react-router-dom", async () => {
  const actual =
    await vi.importActual<typeof import("react-router-dom")>(
      "react-router-dom",
    );
  return {
    ...actual,
    useNavigate: () => mocks.navigate,
  };
});

vi.mock("@/hooks/useAuth", () => ({
  useAuth: mocks.useAuth,
}));

vi.mock("@/services/admin.service", () => ({
  adminService: mocks.adminService,
}));

vi.mock("@/services/governance.service", () => ({
  governanceService: mocks.governanceService,
}));

vi.mock("@/services/billing.service", () => ({
  billingService: mocks.billingService,
}));

describe("OrgDashboardPage pipeline navigation", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("navigates to workspace applications with status filter when pulse is clicked", async () => {
    mocks.useAuth.mockReturnValue({
      activeOrganization: {
        id: "org-1",
        name: "Org One",
        organization_type: "ministry",
        tier: "growth",
      },
      activeOrganizationId: "org-1",
    });

    mocks.adminService.getDashboard.mockResolvedValue({
      total_applications: 3,
      pending: 1,
      under_review: 1,
      approved: 1,
      rejected: 0,
      recent_applications: [],
    });

    mocks.governanceService.getOrganizationSummary.mockResolvedValue({
      stats: {
        members_active: 0,
        committees_active: 0,
        active_chairs: 0,
        committee_memberships_active: 0,
      },
      committee_health: {
        compliance_rate: 0,
      },
    });

    mocks.billingService.getOnboardingTokenState.mockResolvedValue({
      token: null,
      organization_seat_remaining: 0,
      organization_seat_limit: 0,
    });

    mocks.billingService.getSubscriptionManagement.mockResolvedValue({
      subscription: null,
    });

    render(
      <MemoryRouter>
        <OrgDashboardPage />
      </MemoryRouter>,
    );

    const underReviewButton = await screen.findByRole("button", {
      name: /Under Review/i,
    });

    fireEvent.click(underReviewButton);

    await waitFor(() => {
      expect(mocks.navigate).toHaveBeenCalledWith(
        "/workspace/applications?status=under_review",
      );
    });
  });
});
