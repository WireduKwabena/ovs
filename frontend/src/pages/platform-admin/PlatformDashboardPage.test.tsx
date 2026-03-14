// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import PlatformDashboardPage from "./PlatformDashboardPage";

const mocks = vi.hoisted(() => ({
  listPlatformOrganizations: vi.fn(),
  updatePlatformOrganizationStatus: vi.fn(),
  toastSuccess: vi.fn(),
  toastError: vi.fn(),
}));

vi.mock("@/services/governance.service", () => ({
  governanceService: {
    listPlatformOrganizations: mocks.listPlatformOrganizations,
    updatePlatformOrganizationStatus: mocks.updatePlatformOrganizationStatus,
  },
}));

vi.mock("@/components/admin/BillingHealthCard", () => ({
  default: () => <div>Mock Billing Health</div>,
}));

vi.mock("react-toastify", () => ({
  toast: {
    success: mocks.toastSuccess,
    error: mocks.toastError,
  },
}));

describe("PlatformDashboardPage", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("renders organization subscription oversight rows", async () => {
    mocks.listPlatformOrganizations.mockResolvedValue({
      count: 2,
      results: [
        {
          id: "org-1",
          code: "ORG1",
          name: "Org One",
          organization_type: "agency",
          is_active: true,
          active_member_count: 5,
          subscription: {
            id: "sub-1",
            source: "active",
            provider: "stripe",
            status: "complete",
            payment_status: "paid",
            plan_id: "growth",
            plan_name: "Growth",
            billing_cycle: "monthly",
            payment_method: "card",
            amount_usd: "399.00",
            current_period_end: null,
            cancel_at_period_end: false,
            updated_at: "2026-03-01T10:00:00Z",
          },
        },
        {
          id: "org-2",
          code: "ORG2",
          name: "Org Two",
          organization_type: "ministry",
          is_active: false,
          active_member_count: 1,
          subscription: null,
        },
      ],
    });

    render(
      <MemoryRouter>
        <PlatformDashboardPage />
      </MemoryRouter>,
    );

    expect(await screen.findByText("Org One")).toBeTruthy();
    expect(screen.getByText("Org Two")).toBeTruthy();
    expect(screen.getByText("Mock Billing Health")).toBeTruthy();
    expect(screen.getByText(/active subscriptions/i)).toBeTruthy();
    expect(screen.getByText(/needs attention/i)).toBeTruthy();
  });

  it("toggles organization active status", async () => {
    mocks.listPlatformOrganizations.mockResolvedValue({
      count: 1,
      results: [
        {
          id: "org-1",
          code: "ORG1",
          name: "Org One",
          organization_type: "agency",
          is_active: true,
          active_member_count: 5,
          subscription: null,
        },
      ],
    });
    mocks.updatePlatformOrganizationStatus.mockResolvedValue({
      id: "org-1",
      code: "ORG1",
      name: "Org One",
      organization_type: "agency",
      is_active: false,
      active_member_count: 5,
      subscription: null,
    });

    render(
      <MemoryRouter>
        <PlatformDashboardPage />
      </MemoryRouter>,
    );

    fireEvent.click(await screen.findByRole("button", { name: /deactivate organization/i }));

    await waitFor(() => {
      expect(mocks.updatePlatformOrganizationStatus).toHaveBeenCalledWith("org-1", {
        is_active: false,
      });
    });

    const reactivateButtons = await screen.findAllByRole("button", {
      name: /reactivate organization/i,
    });
    expect(reactivateButtons.length).toBeGreaterThan(0);
    expect(mocks.toastSuccess).toHaveBeenCalled();
  });
});
