// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import AdminOrganizationsPage from "./AdminOrganizationsPage";

const mocks = vi.hoisted(() => ({
  selectActiveOrganization: vi.fn(),
  refreshProfile: vi.fn(),
  toastSuccess: vi.fn(),
  toastError: vi.fn(),
}));

const authState = vi.hoisted(() => ({
  organizations: [] as Array<{
    id: string;
    code: string;
    name: string;
    organization_type: string;
  }>,
  organizationMemberships: [] as Array<{
    id: string;
    organization_id: string;
    organization_name: string;
    organization_code: string;
    organization_type: string;
    membership_role: string;
    title: string;
    is_default: boolean;
    is_active: boolean;
  }>,
  activeOrganizationId: null as string | null,
  switchingActiveOrganization: false,
}));

vi.mock("react-toastify", () => ({
  toast: {
    success: mocks.toastSuccess,
    error: mocks.toastError,
  },
}));

vi.mock("@/hooks/useAuth", () => ({
  useAuth: () => ({
    organizations: authState.organizations,
    organizationMemberships: authState.organizationMemberships,
    activeOrganizationId: authState.activeOrganizationId,
    switchingActiveOrganization: authState.switchingActiveOrganization,
    selectActiveOrganization: mocks.selectActiveOrganization,
    refreshProfile: mocks.refreshProfile,
  }),
}));

const renderPage = () =>
  render(
    <MemoryRouter initialEntries={["/admin/organizations"]}>
      <Routes>
        <Route path="/admin/organizations" element={<AdminOrganizationsPage />} />
        <Route path="/organization/dashboard" element={<div>Organization Dashboard Route</div>} />
        <Route path="/admin/dashboard" element={<div>Platform Dashboard Route</div>} />
      </Routes>
    </MemoryRouter>,
  );

describe("AdminOrganizationsPage", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
    authState.organizations = [];
    authState.organizationMemberships = [];
    authState.activeOrganizationId = null;
    authState.switchingActiveOrganization = false;
  });

  it("enters selected organization context and redirects to organization dashboard", async () => {
    authState.organizations = [
      {
        id: "org-1",
        code: "PSC",
        name: "Public Service Commission",
        organization_type: "agency",
      },
    ];
    mocks.selectActiveOrganization.mockResolvedValue(undefined);

    renderPage();

    fireEvent.click(await screen.findByRole("button", { name: /enter organization/i }));

    await waitFor(() => {
      expect(mocks.selectActiveOrganization).toHaveBeenCalledWith("org-1");
    });
    expect(await screen.findByText("Organization Dashboard Route")).toBeTruthy();
  });

  it("returns to platform scope by clearing active organization", async () => {
    authState.organizations = [
      {
        id: "org-1",
        code: "PSC",
        name: "Public Service Commission",
        organization_type: "agency",
      },
    ];
    authState.activeOrganizationId = "org-1";
    mocks.selectActiveOrganization.mockResolvedValue(undefined);

    renderPage();

    fireEvent.click(await screen.findByRole("button", { name: /return to platform/i }));

    await waitFor(() => {
      expect(mocks.selectActiveOrganization).toHaveBeenCalledWith(null);
    });
    expect(await screen.findByText("Platform Dashboard Route")).toBeTruthy();
  });
});

