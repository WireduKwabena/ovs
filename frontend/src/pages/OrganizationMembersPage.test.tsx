// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import OrganizationMembersPage from "./OrganizationMembersPage";

const mocks = vi.hoisted(() => ({
  useAuth: vi.fn(),
  listOrganizationMembers: vi.fn(),
  updateOrganizationMember: vi.fn(),
  toastError: vi.fn(),
  toastSuccess: vi.fn(),
}));

vi.mock("@/hooks/useAuth", () => ({
  useAuth: () => mocks.useAuth(),
}));

vi.mock("@/services/governance.service", () => ({
  governanceService: {
    listOrganizationMembers: mocks.listOrganizationMembers,
    updateOrganizationMember: mocks.updateOrganizationMember,
  },
}));

vi.mock("react-toastify", () => ({
  toast: {
    error: mocks.toastError,
    success: mocks.toastSuccess,
  },
}));

describe("OrganizationMembersPage", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("renders member list for org-admin users", async () => {
    mocks.useAuth.mockReturnValue({
      userType: "hr_manager",
      activeOrganization: { id: "org-1", code: "ORG1", name: "Org One", organization_type: "agency" },
      activeOrganizationId: "org-1",
      canManageActiveOrganizationGovernance: true,
    });
    mocks.listOrganizationMembers.mockResolvedValue({
      count: 1,
      next: null,
      previous: null,
      results: [
        {
          id: "m-1",
          user: "user-1",
          user_email: "registry.admin@example.com",
          user_full_name: "Registry Admin",
          organization: "org-1",
          organization_name: "Org One",
          title: "Registry Lead",
          membership_role: "registry_admin",
          is_active: true,
          is_default: true,
          joined_at: "2026-01-01T00:00:00Z",
          left_at: null,
          created_at: "2026-01-01T00:00:00Z",
          updated_at: "2026-01-01T00:00:00Z",
        },
      ],
    });

    render(
      <MemoryRouter>
        <OrganizationMembersPage />
      </MemoryRouter>,
    );

    expect(await screen.findByText(/member registry/i)).toBeTruthy();
    expect(await screen.findByText(/registry.admin@example.com/i)).toBeTruthy();
    expect(await screen.findByDisplayValue(/registry_admin/i)).toBeTruthy();

    await waitFor(() => {
      expect(mocks.listOrganizationMembers).toHaveBeenCalledTimes(1);
    });
  });
});

