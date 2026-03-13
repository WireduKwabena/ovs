// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import CommitteeDashboardPage from "./CommitteeDashboardPage";

const mockUseAuth = vi.fn();

vi.mock("@/hooks/useAuth", () => ({
  useAuth: () => mockUseAuth(),
}));

describe("CommitteeDashboardPage", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("shows active-organization requirement when none is selected", async () => {
    mockUseAuth.mockReturnValue({
      userType: "internal",
      activeOrganization: null,
      activeOrganizationId: null,
      committees: [],
      canAccessAppointments: true,
      canAccessApplications: false,
      canViewAuditLogs: false,
    });

    render(
      <MemoryRouter initialEntries={["/organization/committee-dashboard"]}>
        <Routes>
          <Route path="/organization/committee-dashboard" element={<CommitteeDashboardPage />} />
        </Routes>
      </MemoryRouter>,
    );

    expect(await screen.findByText(/active organization required/i)).toBeTruthy();
  });

  it("renders scoped committee memberships", async () => {
    mockUseAuth.mockReturnValue({
      userType: "internal",
      activeOrganization: { id: "org-1", code: "org1", name: "Org One", organization_type: "agency" },
      activeOrganizationId: "org-1",
      committees: [
        {
          id: "m-1",
          committee_id: "c-1",
          committee_code: "vetting",
          committee_name: "Vetting Committee",
          committee_type: "vetting",
          organization_id: "org-1",
          organization_code: "org1",
          organization_name: "Org One",
          committee_role: "committee_member",
          can_vote: true,
        },
        {
          id: "m-2",
          committee_id: "c-2",
          committee_code: "approval",
          committee_name: "Approval Committee",
          committee_type: "approval",
          organization_id: "org-2",
          organization_code: "org2",
          organization_name: "Org Two",
          committee_role: "committee_member",
          can_vote: true,
        },
      ],
      canAccessAppointments: true,
      canAccessApplications: true,
      canViewAuditLogs: false,
    });

    render(
      <MemoryRouter initialEntries={["/organization/committee-dashboard"]}>
        <Routes>
          <Route path="/organization/committee-dashboard" element={<CommitteeDashboardPage />} />
        </Routes>
      </MemoryRouter>,
    );

    expect(await screen.findByText(/committee dashboard/i)).toBeTruthy();
    expect(screen.getByText("Vetting Committee")).toBeTruthy();
    expect(screen.queryByText("Approval Committee")).toBeNull();
  });
});

