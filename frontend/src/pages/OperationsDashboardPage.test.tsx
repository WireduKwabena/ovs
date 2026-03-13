// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import OperationsDashboardPage from "./OperationsDashboardPage";

const mocks = vi.hoisted(() => ({
  list: vi.fn(),
  getDashboard: vi.fn(),
  useAuth: vi.fn(),
}));

vi.mock("@/services/campaign.service", () => ({
  campaignService: {
    list: mocks.list,
    getDashboard: mocks.getDashboard,
  },
}));

vi.mock("@/hooks/useAuth", () => ({
  useAuth: () => mocks.useAuth(),
}));

vi.mock("@/components/admin/OperationsDashboardChartsSection", () => ({
  default: () => <div>Charts</div>,
}));

vi.mock("react-toastify", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
  },
}));

const renderOperationsDashboardAt = (path: string) =>
  render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/workspace" element={<OperationsDashboardPage />} />
        <Route path="/government/appointments" element={<div>Operations Appointments Route</div>} />
        <Route path="/government/positions" element={<div>Operations Positions Route</div>} />
        <Route path="/government/personnel" element={<div>Operations Personnel Route</div>} />
        <Route path="/applications" element={<div>Operations Applications Route</div>} />
        <Route path="/audit-logs" element={<div>Operations Audit Route</div>} />
      </Routes>
    </MemoryRouter>,
  );

const renderOperationsDashboard = () => renderOperationsDashboardAt("/workspace");

describe("OperationsDashboardPage government quick actions", () => {
  const baseUser = {
    id: "user-1",
    email: "hr@example.com",
    first_name: "Internal",
    last_name: "Manager",
    full_name: "Operations User",
    phone_number: "",
    profile_picture_url: "",
    avatar_url: "",
    date_of_birth: "",
    is_active: true,
    created_at: "2026-01-01T00:00:00Z",
  };

  const mockHrContext = (overrides: Record<string, unknown> = {}) => {
    mocks.useAuth.mockReturnValue({
      user: baseUser,
      activeOrganizationId: "org-1",
      activeOrganization: {
        id: "org-1",
        code: "ORG1",
        name: "Demo Organization",
        organization_type: "agency",
      },
      canAccessCampaigns: true,
      canAccessVideoCalls: true,
      canAccessAppointments: true,
      canAccessApplications: true,
      canManageRegistry: true,
      canAccessInternalWorkflow: true,
      canManageActiveOrganizationGovernance: true,
      canFinalizeAppointment: false,
      canPublishAppointment: false,
      canViewAuditLogs: false,
      roles: [],
      canSwitchOrganization: true,
      committees: [],
      ...overrides,
    });
    mocks.list.mockResolvedValue([]);
    mocks.getDashboard.mockResolvedValue({
      total_candidates: 0,
      invited: 0,
      registered: 0,
      in_progress: 0,
      completed: 0,
      reviewed: 0,
      approved: 0,
      rejected: 0,
      escalated: 0,
    });
  };

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("navigates to government appointments", async () => {
    mockHrContext();
    renderOperationsDashboard();
    fireEvent.click(await screen.findByRole("button", { name: /appointment workflow/i }));
    expect(await screen.findByText("Operations Appointments Route")).toBeTruthy();
  });

  it("navigates to government positions", async () => {
    mockHrContext();
    renderOperationsDashboard();
    fireEvent.click(await screen.findByRole("button", { name: /manage government offices/i }));
    expect(await screen.findByText("Operations Positions Route")).toBeTruthy();
  });

  it("navigates to government personnel", async () => {
    mockHrContext();
    renderOperationsDashboard();
    fireEvent.click(await screen.findByRole("button", { name: /nominee and officeholder registry/i }));
    expect(await screen.findByText("Operations Personnel Route")).toBeTruthy();
  });

  it("hides registry actions when user lacks registry authority", async () => {
    mockHrContext({
      canManageRegistry: false,
    });
    renderOperationsDashboard();
    await screen.findByText(/quick actions/i);
    expect(screen.queryByRole("button", { name: /manage government offices/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /nominee and officeholder registry/i })).toBeNull();
  });

  it("shows org-scoped actions disabled when active organization is missing", async () => {
    mockHrContext({
      activeOrganizationId: null,
      activeOrganization: null,
      canAccessCampaigns: true,
      canAccessAppointments: true,
    });
    renderOperationsDashboard();
    const appointmentsButton = await screen.findByRole("button", { name: /appointment workflow/i });
    expect((appointmentsButton as HTMLButtonElement).disabled).toBe(true);
    expect(
      screen.getAllByText(/select an active organization from the navbar to enable organization-scoped actions/i)
        .length,
    ).toBeGreaterThan(0);
  });

  it("shows committee lane first in committee view mode", async () => {
    mockHrContext({
      roles: ["committee_member"],
      committees: [
        {
          id: "membership-1",
          committee_id: "committee-1",
          committee_code: "appointments",
          committee_name: "Appointments Committee",
          committee_type: "approval",
          organization_id: "org-1",
          organization_code: "ORG",
          organization_name: "Demo Organization",
          committee_role: "committee_member",
          can_vote: true,
        },
      ],
    });
    renderOperationsDashboardAt("/workspace?view=committee");
    expect(await screen.findByText(/committee-first priority order/i)).toBeTruthy();
    const lanes = await screen.findAllByTestId(/workspace-lane-/);
    expect(lanes[0].getAttribute("data-testid")).toBe("workspace-lane-committee");
  });

  it("shows vetting lane for vetting officers", async () => {
    mockHrContext({
      roles: ["vetting_officer"],
      canManageRegistry: false,
      canAccessCampaigns: false,
      canAccessAppointments: false,
    });
    renderOperationsDashboard();
    expect(await screen.findByTestId("workspace-lane-vetting")).toBeTruthy();
    expect(screen.getByRole("link", { name: /open vetting dossiers/i })).toBeTruthy();
  });

  it("shows approval lane for appointing authority", async () => {
    mockHrContext({
      roles: ["appointing_authority"],
      canManageRegistry: false,
      canAccessCampaigns: false,
      canFinalizeAppointment: true,
    });
    renderOperationsDashboard();
    expect(await screen.findByTestId("workspace-lane-approval")).toBeTruthy();
    expect(screen.getByRole("link", { name: /open approval queue/i })).toBeTruthy();
  });

  it("shows publication lane for publication officers", async () => {
    mockHrContext({
      roles: ["publication_officer"],
      canManageRegistry: false,
      canAccessCampaigns: false,
      canPublishAppointment: true,
    });
    renderOperationsDashboard();
    expect(await screen.findByTestId("workspace-lane-publication")).toBeTruthy();
    expect(screen.getByRole("link", { name: /open publication queue/i })).toBeTruthy();
  });

  it("shows auditor lane with audit CTA", async () => {
    mockHrContext({
      roles: ["auditor"],
      canManageRegistry: false,
      canAccessCampaigns: false,
      canAccessAppointments: false,
      canAccessApplications: false,
      canViewAuditLogs: true,
    });
    renderOperationsDashboard();
    expect(await screen.findByTestId("workspace-lane-audit")).toBeTruthy();
    fireEvent.click(screen.getByRole("link", { name: /open audit logs/i }));
    expect(await screen.findByText("Operations Audit Route")).toBeTruthy();
  });

  it("stacks mixed-role lanes in priority order", async () => {
    mockHrContext({
      roles: ["vetting_officer", "committee_member", "publication_officer"],
      canManageRegistry: false,
      canAccessCampaigns: false,
      canPublishAppointment: true,
      committees: [
        {
          id: "membership-1",
          committee_id: "committee-1",
          committee_code: "appointments",
          committee_name: "Appointments Committee",
          committee_type: "approval",
          organization_id: "org-1",
          organization_code: "ORG",
          organization_name: "Demo Organization",
          committee_role: "committee_member",
          can_vote: true,
        },
      ],
    });
    renderOperationsDashboard();
    const lanes = await screen.findAllByTestId(/workspace-lane-/);
    const orderedIds = lanes.map((lane) => lane.getAttribute("data-testid"));
    expect(orderedIds.slice(0, 3)).toEqual([
      "workspace-lane-vetting",
      "workspace-lane-committee",
      "workspace-lane-publication",
    ]);
  });
});

