// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

const mocks = vi.hoisted(() => ({
  getOrganizationSummary: vi.fn(),
  canManage: true as boolean,
  canAccessApplications: false as boolean,
  canAccessCampaigns: false as boolean,
  canViewAuditLogs: false as boolean,
  canAccessVideoCalls: false as boolean,
  canManageRegistry: false as boolean,
  isAdmin: false as boolean,
}));

vi.mock("@/services/governance.service", () => ({
  governanceService: { getOrganizationSummary: mocks.getOrganizationSummary },
}));
vi.mock("@/hooks/useAuth", () => ({
  useAuth: () => ({
    activeOrganization: { name: "Test Org" },
    canManageActiveOrganizationGovernance: mocks.canManage,
    canAccessApplications: mocks.canAccessApplications,
    canAccessCampaigns: mocks.canAccessCampaigns,
    canViewAuditLogs: mocks.canViewAuditLogs,
    canAccessVideoCalls: mocks.canAccessVideoCalls,
    canManageRegistry: mocks.canManageRegistry,
    isAdmin: mocks.isAdmin,
  }),
}));
vi.mock("react-toastify", () => ({ toast: { error: vi.fn() } }));
vi.mock("@/utils/appPaths", () => ({
  getWorkspacePath: (p: string) => `/workspace/${p}`,
}));

const { default: WorkspaceHomePage } =
  await import("./workspace/WorkspaceHomePage");

const buildSummary = () => ({
  stats: {
    members_active: 4,
    committees_active: 2,
    members_total: 7,
    active_chairs: 1,
  },
});

describe("WorkspaceHomePage", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("calls getOrganizationSummary when user can manage governance", async () => {
    mocks.getOrganizationSummary.mockResolvedValue(buildSummary());
    render(
      <MemoryRouter>
        <WorkspaceHomePage />
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(mocks.getOrganizationSummary).toHaveBeenCalled(),
    );
  });

  it("skips the API call when user cannot manage governance", () => {
    mocks.canManage = false;
    render(
      <MemoryRouter>
        <WorkspaceHomePage />
      </MemoryRouter>,
    );
    expect(mocks.getOrganizationSummary).not.toHaveBeenCalled();
    mocks.canManage = true;
  });

  it("renders org name in welcome section", async () => {
    mocks.getOrganizationSummary.mockResolvedValue(buildSummary());
    render(
      <MemoryRouter>
        <WorkspaceHomePage />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText(/Test Org/)).toBeTruthy());
  });
});
