// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import OrganizationCommitteesPage from "./OrganizationCommitteesPage";

const mocks = vi.hoisted(() => ({
  useAuth: vi.fn(),
  listCommittees: vi.fn(),
  getGovernanceChoices: vi.fn(),
  createCommittee: vi.fn(),
  updateCommittee: vi.fn(),
  deactivateCommittee: vi.fn(),
  toastError: vi.fn(),
  toastSuccess: vi.fn(),
}));

vi.mock("@/hooks/useAuth", () => ({
  useAuth: () => mocks.useAuth(),
}));

vi.mock("@/services/governance.service", () => ({
  governanceService: {
    listCommittees: mocks.listCommittees,
    getGovernanceChoices: mocks.getGovernanceChoices,
    createCommittee: mocks.createCommittee,
    updateCommittee: mocks.updateCommittee,
    deactivateCommittee: mocks.deactivateCommittee,
  },
}));

vi.mock("react-toastify", () => ({
  toast: {
    error: mocks.toastError,
    success: mocks.toastSuccess,
  },
}));

describe("OrganizationCommitteesPage", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("renders committee registry and workspace links", async () => {
    mocks.useAuth.mockReturnValue({
      userType: "hr_manager",
      activeOrganization: { id: "org-1", code: "ORG1", name: "Org One", organization_type: "agency" },
      activeOrganizationId: "org-1",
      canManageActiveOrganizationGovernance: true,
    });
    mocks.getGovernanceChoices.mockResolvedValue({
      organization_types: [{ value: "agency", label: "Agency" }],
      committee_types: [
        { value: "screening", label: "Screening" },
        { value: "vetting", label: "Vetting" },
      ],
      committee_roles: [
        { value: "chair", label: "Chair" },
        { value: "member", label: "Member" },
      ],
    });
    mocks.listCommittees.mockResolvedValue({
      count: 1,
      next: null,
      previous: null,
      results: [
        {
          id: "c-1",
          organization: "org-1",
          organization_name: "Org One",
          code: "vetting-main",
          name: "Vetting Committee",
          committee_type: "vetting",
          description: "Core vetting committee",
          is_active: true,
          created_by: "u-1",
          created_by_email: "registry.admin@example.com",
          created_at: "2026-01-01T00:00:00Z",
          updated_at: "2026-01-01T00:00:00Z",
        },
      ],
    });

    render(
      <MemoryRouter>
        <OrganizationCommitteesPage />
      </MemoryRouter>,
    );

    expect(await screen.findByText(/committee registry/i)).toBeTruthy();
    const committeeNameInputs = await screen.findAllByDisplayValue(/vetting committee/i);
    expect(committeeNameInputs.length).toBeGreaterThan(0);
    expect(await screen.findByRole("link", { name: /workspace/i })).toBeTruthy();

    await waitFor(() => {
      expect(mocks.listCommittees).toHaveBeenCalledTimes(1);
    });
  });
});
