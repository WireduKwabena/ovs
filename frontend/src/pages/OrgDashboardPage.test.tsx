// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

const mocks = vi.hoisted(() => ({
  getOrganizationSummary: vi.fn(),
  getOnboardingTokenState: vi.fn(),
  getSubscriptionManagement: vi.fn(),
  getDashboard: vi.fn(),
  toastError: vi.fn(),
  navigate: vi.fn(),
}));

vi.mock("@/services/governance.service", () => ({
  governanceService: { getOrganizationSummary: mocks.getOrganizationSummary },
}));
vi.mock("@/services/billing.service", () => ({
  billingService: {
    getOnboardingTokenState: mocks.getOnboardingTokenState,
    getSubscriptionManagement: mocks.getSubscriptionManagement,
  },
}));
vi.mock("@/services/admin.service", () => ({
  adminService: { getDashboard: mocks.getDashboard },
}));
vi.mock("@/hooks/useAuth", () => ({
  useAuth: () => ({
    activeOrganization: { name: "Test Org", id: "org-1" },
    activeOrganizationId: "org-1",
  }),
}));
vi.mock("react-toastify", () => ({ toast: { error: mocks.toastError } }));
vi.mock("react-router-dom", async (importOriginal) => {
  const actual = (await importOriginal()) as Record<string, unknown>;
  return { ...actual, useNavigate: () => mocks.navigate };
});
vi.mock("@/utils/notificationTrace", () => ({
  buildBillingPaymentFailureNotificationTraceHref: () => "#",
  buildBillingProcessingErrorNotificationTraceHref: () => "#",
}));
vi.mock("@/utils/helper", () => ({ formatRelativeTime: (d: string) => d }));

const { default: OrgDashboardPage } =
  await import("./org-admin/OrgDashboardPage");

const buildSummary = () => ({
  stats: {
    members_active: 5,
    committees_active: 2,
    active_chairs: 1,
    committee_memberships_active: 3,
  },
});

const buildOnboarding = () => ({
  token: null,
  organization_seat_remaining: 0,
  organization_seat_limit: 0,
});

const buildDashboard = () => ({
  total_applications: 8,
  pending: 2,
  under_review: 3,
  approved: 2,
  rejected: 1,
  recent_applications: [],
});

describe("OrgDashboardPage", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("calls all required services on mount", async () => {
    mocks.getOrganizationSummary.mockResolvedValue(buildSummary());
    mocks.getOnboardingTokenState.mockResolvedValue(buildOnboarding());
    mocks.getSubscriptionManagement.mockResolvedValue({ subscription: null });
    mocks.getDashboard.mockResolvedValue(buildDashboard());

    render(
      <MemoryRouter>
        <OrgDashboardPage />
      </MemoryRouter>,
    );

    await waitFor(() =>
      expect(mocks.getOrganizationSummary).toHaveBeenCalled(),
    );
    expect(mocks.getOnboardingTokenState).toHaveBeenCalled();
    expect(mocks.getSubscriptionManagement).toHaveBeenCalled();
  });

  it("shows org name when data loads", async () => {
    mocks.getOrganizationSummary.mockResolvedValue(buildSummary());
    mocks.getOnboardingTokenState.mockResolvedValue(buildOnboarding());
    mocks.getSubscriptionManagement.mockResolvedValue({ subscription: null });
    mocks.getDashboard.mockResolvedValue(buildDashboard());

    render(
      <MemoryRouter>
        <OrgDashboardPage />
      </MemoryRouter>,
    );

    await waitFor(() => expect(screen.getByText(/Test Org/)).toBeTruthy());
  });
});
