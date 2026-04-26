// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

const mocks = vi.hoisted(() => ({
  navigate: vi.fn(),
  createOrganization: vi.fn(),
  toastError: vi.fn(),
  toastSuccess: vi.fn(),
  userType: "staff" as string,
  activeOrganizationId: null as string | null,
  refreshProfile: vi.fn(),
}));

vi.mock("react-router-dom", async (importOriginal) => {
  const actual = (await importOriginal()) as Record<string, unknown>;
  return {
    ...actual,
    useNavigate: () => mocks.navigate,
  };
});
vi.mock("@/services/governance.service", () => ({
  governanceService: { createOrganization: mocks.createOrganization },
}));
vi.mock("@/hooks/useAuth", () => ({
  useAuth: () => ({
    userType: mocks.userType,
    activeOrganizationId: mocks.activeOrganizationId,
    activeOrganization: null,
    refreshProfile: mocks.refreshProfile,
  }),
}));
vi.mock("react-toastify", () => ({
  toast: { error: mocks.toastError, success: mocks.toastSuccess },
}));

const { default: OrganizationSetupPage } =
  await import("./OrganizationSetupPage");

describe("OrganizationSetupPage", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("blocks applicant users with an unavailable message", () => {
    mocks.userType = "applicant";
    render(
      <MemoryRouter>
        <OrganizationSetupPage />
      </MemoryRouter>,
    );
    expect(screen.getByText(/organization setup unavailable/i)).toBeTruthy();
    mocks.userType = "staff";
  });

  it("renders the create organization form for staff users", () => {
    render(
      <MemoryRouter>
        <OrganizationSetupPage />
      </MemoryRouter>,
    );
    expect(
      screen.getByRole("button", { name: /create organization/i }),
    ).toBeTruthy();
  });
});
