// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import GovernmentPositionsPage from "./GovernmentPositionsPage";

const authState = vi.hoisted(() => ({
  activeOrganization: null as { id: string; code: string; name: string; organization_type: string } | null,
  activeOrganizationId: null as string | null,
  isAdmin: false,
  canManageRegistry: false,
}));

const serviceMocks = vi.hoisted(() => ({
  listPositions: vi.fn(),
  createPosition: vi.fn(),
}));

vi.mock("@/hooks/useAuth", () => ({
  useAuth: () => authState,
}));

vi.mock("@/services/government.service", () => ({
  governmentService: {
    listPositions: serviceMocks.listPositions,
    createPosition: serviceMocks.createPosition,
  },
}));

describe("GovernmentPositionsPage authz visibility", () => {
  const renderPage = () =>
    render(
      <MemoryRouter>
        <GovernmentPositionsPage />
      </MemoryRouter>,
    );

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
    authState.activeOrganization = null;
    authState.activeOrganizationId = null;
    authState.isAdmin = false;
    authState.canManageRegistry = false;
  });

  it("shows read-only warning and disables create for non-registry users", async () => {
    serviceMocks.listPositions.mockResolvedValue([]);

    renderPage();

    await waitFor(() => {
      expect(serviceMocks.listPositions).toHaveBeenCalledTimes(1);
    });

    expect(await screen.findByText(/Only registry operators can create or edit offices./i)).toBeTruthy();
    expect((screen.getByRole("button", { name: /create office/i }) as HTMLButtonElement).disabled).toBe(true);
  });

  it("enables create controls for registry operators with active organization", async () => {
    authState.canManageRegistry = true;
    authState.activeOrganizationId = "org-1";
    authState.activeOrganization = {
      id: "org-1",
      code: "ORG1",
      name: "Org One",
      organization_type: "agency",
    };
    serviceMocks.listPositions.mockResolvedValue([]);

    renderPage();

    await waitFor(() => {
      expect(serviceMocks.listPositions).toHaveBeenCalledTimes(1);
    });

    expect(screen.queryByText(/Only registry operators can create or edit offices./i)).toBeNull();
    expect((screen.getByRole("button", { name: /create office/i }) as HTMLButtonElement).disabled).toBe(false);
  });
});
