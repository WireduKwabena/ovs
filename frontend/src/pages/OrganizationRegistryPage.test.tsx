// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

const mocks = vi.hoisted(() => ({
  listPlatformOrganizations: vi.fn(),
  updatePlatformOrganizationStatus: vi.fn(),
  toastError: vi.fn(),
  toastSuccess: vi.fn(),
}));

vi.mock("@/services/governance.service", () => ({
  governanceService: {
    listPlatformOrganizations: mocks.listPlatformOrganizations,
    updatePlatformOrganizationStatus: mocks.updatePlatformOrganizationStatus,
  },
}));
vi.mock("react-toastify", () => ({
  toast: { error: mocks.toastError, success: mocks.toastSuccess },
}));
vi.mock("@/utils/appPaths", () => ({
  getOrgAdminPath: (id: string, p: string) => `/admin/org/${id}/${p}`,
}));

const { OrganizationRegistryPage } =
  await import("./platform-admin/OrganizationRegistryPage");

describe("OrganizationRegistryPage", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("calls listPlatformOrganizations on mount", async () => {
    mocks.listPlatformOrganizations.mockResolvedValue({ results: [] });
    render(
      <MemoryRouter>
        <OrganizationRegistryPage />
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(mocks.listPlatformOrganizations).toHaveBeenCalled(),
    );
  });

  it("renders the Organization Registry heading", async () => {
    mocks.listPlatformOrganizations.mockResolvedValue({ results: [] });
    render(
      <MemoryRouter>
        <OrganizationRegistryPage />
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(screen.getByText(/organization registry/i)).toBeTruthy(),
    );
  });

  it("shows fetched organizations", async () => {
    mocks.listPlatformOrganizations.mockResolvedValue({
      results: [
        {
          id: "org-1",
          name: "Ministry of Finance",
          code: "MOF",
          is_active: true,
        },
      ],
    });
    render(
      <MemoryRouter>
        <OrganizationRegistryPage />
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(screen.getByText("Ministry of Finance")).toBeTruthy(),
    );
  });
});
