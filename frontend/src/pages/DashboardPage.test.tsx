// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { cleanup, render, screen } from "@testing-library/react";

import { DashboardPage } from "./DashboardPage";

const mockUseAuth = vi.fn();

vi.mock("@/hooks/useAuth", () => ({
  useAuth: () => mockUseAuth(),
}));

describe("DashboardPage role routing", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("redirects admins to /admin/dashboard", async () => {
    mockUseAuth.mockReturnValue({ userType: "admin" });

    render(
      <MemoryRouter initialEntries={["/dashboard"]}>
        <Routes>
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/admin/dashboard" element={<div>Admin Dashboard Page</div>} />
        </Routes>
      </MemoryRouter>,
    );

    expect(await screen.findByText("Admin Dashboard Page")).toBeTruthy();
  });

  it("redirects org-admin users with active organization to organization dashboard", async () => {
    mockUseAuth.mockReturnValue({
      userType: "internal",
      canManageActiveOrganizationGovernance: true,
      activeOrganizationId: "org-1",
    });

    render(
      <MemoryRouter initialEntries={["/dashboard"]}>
        <Routes>
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/organization/dashboard" element={<div>Organization Dashboard</div>} />
        </Routes>
      </MemoryRouter>,
    );

    expect(await screen.findByText("Organization Dashboard")).toBeTruthy();
  });

  it("redirects org-admin users without active organization to setup", async () => {
    mockUseAuth.mockReturnValue({
      userType: "internal",
      canManageActiveOrganizationGovernance: true,
      activeOrganizationId: null,
    });

    render(
      <MemoryRouter initialEntries={["/dashboard"]}>
        <Routes>
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/organization/setup" element={<div>Organization Setup</div>} />
        </Routes>
      </MemoryRouter>,
    );

    expect(await screen.findByText("Organization Setup")).toBeTruthy();
  });

  it("routes committee actors to shared workspace", async () => {
    mockUseAuth.mockReturnValue({
      userType: "internal",
      canAccessInternalWorkflow: false,
      canAccessApplications: false,
      canAccessCampaigns: false,
      canAccessVideoCalls: false,
      hasAnyRole: vi.fn((roles: string[]) => roles.includes("committee_member")),
      canManageActiveOrganizationGovernance: false,
      activeOrganizationId: "org-1",
      canAccessAppointments: true,
      canManageRegistry: false,
      canViewAuditLogs: false,
    });

    render(
      <MemoryRouter initialEntries={["/dashboard"]}>
        <Routes>
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/workspace" element={<div>Workspace</div>} />
        </Routes>
      </MemoryRouter>,
    );

    expect(await screen.findByText("Workspace")).toBeTruthy();
  });

  it("routes internal workflow users to shared workspace", async () => {
    mockUseAuth.mockReturnValue({
      userType: "internal",
      canAccessInternalWorkflow: true,
      canAccessApplications: false,
      canAccessCampaigns: false,
      canAccessVideoCalls: false,
      hasAnyRole: vi.fn().mockReturnValue(false),
      canManageActiveOrganizationGovernance: false,
      activeOrganizationId: "org-1",
      canAccessAppointments: false,
      canManageRegistry: false,
      canViewAuditLogs: false,
    });

    render(
      <MemoryRouter initialEntries={["/dashboard"]}>
        <Routes>
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/workspace" element={<div>Workspace</div>} />
        </Routes>
      </MemoryRouter>,
    );

    expect(await screen.findByText("Workspace")).toBeTruthy();
  });

  it("redirects applicant users to candidate access", async () => {
    mockUseAuth.mockReturnValue({ userType: "applicant" });

    render(
      <MemoryRouter initialEntries={["/dashboard"]}>
        <Routes>
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/candidate/access" element={<div>Candidate Access Page</div>} />
        </Routes>
      </MemoryRouter>,
    );

    expect(await screen.findByText("Candidate Access Page")).toBeTruthy();
  });
});

