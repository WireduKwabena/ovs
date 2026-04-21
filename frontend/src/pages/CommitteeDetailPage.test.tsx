// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

const mocks = vi.hoisted(() => ({
  getCommittee: vi.fn(),
  listCommitteeMemberships: vi.fn(),
  listMemberOptions: vi.fn(),
  getGovernanceChoices: vi.fn(),
  userType: "staff" as string,
  canManage: true as boolean,
}));

vi.mock("@/services/governance.service", () => ({
  governanceService: {
    getCommittee: mocks.getCommittee,
    listCommitteeMemberships: mocks.listCommitteeMemberships,
    listMemberOptions: mocks.listMemberOptions,
    getGovernanceChoices: mocks.getGovernanceChoices,
  },
}));
vi.mock("@/hooks/useAuth", () => ({
  useAuth: () => ({
    userType: mocks.userType,
    activeOrganizationId: "org-1",
    canManageActiveOrganizationGovernance: mocks.canManage,
  }),
}));
vi.mock("react-toastify", () => ({
  toast: { error: vi.fn(), success: vi.fn() },
}));

const { default: CommitteeDetailPage } = await import("./CommitteeDetailPage");

const renderWithId = (committeeId = "com-1") =>
  render(
    <MemoryRouter initialEntries={[`/committees/${committeeId}`]}>
      <Routes>
        <Route
          path="/committees/:committeeId"
          element={<CommitteeDetailPage />}
        />
      </Routes>
    </MemoryRouter>,
  );

describe("CommitteeDetailPage", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("shows no committee when user cannot manage governance", async () => {
    mocks.canManage = false;
    renderWithId();
    await waitFor(() =>
      expect(
        screen.getByText(/organization admin access required/i),
      ).toBeTruthy(),
    );
    expect(mocks.getCommittee).not.toHaveBeenCalled();
    mocks.canManage = true;
  });

  it("fetches committee data on mount when user can manage", async () => {
    mocks.getCommittee.mockResolvedValue({
      id: "com-1",
      name: "Finance Committee",
      is_active: true,
    });
    mocks.listCommitteeMemberships.mockResolvedValue([]);
    mocks.listMemberOptions.mockResolvedValue([]);
    mocks.getGovernanceChoices.mockResolvedValue({ committee_roles: [] });

    renderWithId("com-1");

    await waitFor(() =>
      expect(mocks.getCommittee).toHaveBeenCalledWith("com-1"),
    );
    await waitFor(() =>
      expect(screen.getByText(/Finance Committee/)).toBeTruthy(),
    );
  });
});
