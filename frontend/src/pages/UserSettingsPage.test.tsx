// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import UserSettingsPage from "./UserSettingsPage";

const mocks = vi.hoisted(() => ({
  getSubscriptionManagement: vi.fn(),
  getOnboardingTokenState: vi.fn(),
  useAuth: vi.fn(),
  dispatch: vi.fn(() => ({ unwrap: vi.fn() })),
}));

vi.mock("react-redux", async () => {
  const actual = await vi.importActual<typeof import("react-redux")>("react-redux");
  return {
    ...actual,
    useDispatch: () => mocks.dispatch,
  };
});

vi.mock("@/hooks/useAuth", () => ({
  useAuth: () => mocks.useAuth(),
}));

vi.mock("@/services/billing.service", () => ({
  billingService: {
    getSubscriptionManagement: mocks.getSubscriptionManagement,
    getOnboardingTokenState: mocks.getOnboardingTokenState,
    generateOnboardingToken: vi.fn(),
    revokeOnboardingToken: vi.fn(),
    updatePaymentMethod: vi.fn(),
    scheduleSubscriptionCancellation: vi.fn(),
    createPaymentMethodUpdateSession: vi.fn(),
    retrySubscription: vi.fn(),
  },
}));

vi.mock("@/store/authSlice", () => ({
  fetchProfile: vi.fn(() => ({ type: "auth/fetchProfile/pending" })),
  updateUserProfile: vi.fn(() => ({ type: "auth/updateUserProfile/pending" })),
}));

vi.mock("react-toastify", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

describe("UserSettingsPage billing empty-state", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("shows read-only subscription guidance for non-org-admin users when subscription is missing", async () => {
    mocks.useAuth.mockReturnValue({
      userType: "internal",
      canManageActiveOrganizationGovernance: false,
      organizations: [],
      activeOrganization: null,
      activeOrganizationId: null,
      user: {
        id: "user-1",
        email: "hr@example.com",
        first_name: "Internal",
        last_name: "Manager",
        full_name: "Operations User",
        phone_number: "",
        organization: "Acme",
        department: "Ops",
        profile_picture_url: "",
        avatar_url: "",
        date_of_birth: "",
        profile: null,
        is_active: true,
        created_at: "2026-01-01T00:00:00Z",
      },
    });
    mocks.getSubscriptionManagement.mockResolvedValue({
      status: "ok",
      message: "No subscription record found for this workspace.",
      subscription: null,
    });

    render(
      <MemoryRouter>
        <UserSettingsPage />
      </MemoryRouter>,
    );

    expect(
      await screen.findByText(/subscription management is restricted to organization admins/i),
    ).toBeTruthy();
    expect(screen.queryByRole("button", { name: /open organization billing/i })).toBeNull();
  });

  it("shows organization administration links for authorized org admins", async () => {
    mocks.useAuth.mockReturnValue({
      userType: "internal",
      canManageActiveOrganizationGovernance: true,
      organizations: [{ id: "org-1", code: "ORG1", name: "Org One", organization_type: "agency" }],
      activeOrganization: { id: "org-1", code: "ORG1", name: "Org One", organization_type: "agency" },
      activeOrganizationId: "org-1",
      user: {
        id: "user-1",
        email: "registry@example.com",
        first_name: "Registry",
        last_name: "Admin",
        full_name: "Registry Admin",
        phone_number: "",
        organization: "Org One",
        department: "Registry",
        profile_picture_url: "",
        avatar_url: "",
        date_of_birth: "",
        profile: null,
        is_active: true,
        created_at: "2026-01-01T00:00:00Z",
      },
    });
    mocks.getSubscriptionManagement.mockResolvedValue({
      status: "ok",
      message: "No subscription record found for this workspace.",
      subscription: null,
    });
    render(
      <MemoryRouter>
        <UserSettingsPage />
      </MemoryRouter>,
    );

    expect(await screen.findByRole("button", { name: /open organization billing/i })).toBeTruthy();
    expect(await screen.findByText(/organization administration/i)).toBeTruthy();
    expect(await screen.findByRole("button", { name: /open organization dashboard/i })).toBeTruthy();
  });
});

