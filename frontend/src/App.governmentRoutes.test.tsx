// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { configureStore } from "@reduxjs/toolkit";
import { Provider } from "react-redux";

import App from "./App";

vi.mock("./store/authSlice", () => ({
  fetchProfile: vi.fn(() => ({ type: "auth/fetchProfile/pending" })),
}));

vi.mock("./components/common/Navbar", () => ({
  Navbar: () => <div>Mock Navbar</div>,
}));

vi.mock("./pages/AppointmentsRegistryPage", () => ({
  default: () => <div>Mock Appointments Registry Page</div>,
}));

vi.mock("./pages/GovernmentPositionsPage", () => ({
  default: () => <div>Mock Government Positions Page</div>,
}));

vi.mock("./pages/GovernmentPersonnelPage", () => ({
  default: () => <div>Mock Government Personnel Page</div>,
}));

vi.mock("./pages/OrganizationDashboardPage", () => ({
  default: () => <div>Mock Organization Dashboard Page</div>,
}));

vi.mock("./pages/DashboardPage", () => ({
  __esModule: true,
  DashboardPage: () => <div>Mock Dashboard Page</div>,
  default: () => <div>Mock Dashboard Page</div>,
}));

type AuthUserType = "applicant" | "internal" | "admin" | null;

const buildStore = (
  userType: AuthUserType,
  capabilitiesOverride?: string[],
  options?: {
    activeOrganizationId?: string | null;
    organizationMemberships?: Array<{
      id: string;
      organization_id: string;
      membership_role: string;
      is_active: boolean;
    }>;
  },
) => {
  const defaultCapabilities =
    userType === "admin"
      ? [
          "gams.registry.manage",
          "gams.appointment.stage",
          "gams.appointment.decide",
          "gams.appointment.publish",
          "gams.appointment.view_internal",
        ]
      : [];
  const capabilities = Array.isArray(capabilitiesOverride) ? capabilitiesOverride : defaultCapabilities;
  const preloadedState = {
    auth: {
      user: {
        id: "user-1",
        email: "user@example.com",
        full_name: "Test User",
        phone_number: "",
        profile_picture_url: "",
        avatar_url: "",
        date_of_birth: "",
        is_active: true,
        created_at: "2026-01-01T00:00:00Z",
      },
      tokens: null,
      isAuthenticated: true,
      userType,
      roles: [],
      capabilities,
      organizations: [],
      organizationMemberships: options?.organizationMemberships || [],
      committees: [],
      activeOrganization: options?.activeOrganizationId
        ? { id: options.activeOrganizationId, code: "ORG", name: "Org", organization_type: "agency" }
        : null,
      activeOrganizationSource: options?.activeOrganizationId ? "header" : "none",
      invalidRequestedOrganizationId: "",
      loading: false,
      error: null,
      twoFactorRequired: false,
      twoFactorToken: null,
    },
    notifications: {
      unreadCount: 0,
      notifications: [],
      loading: false,
      error: null,
    },
    _persist: {
      rehydrated: true,
    },
  };

  return configureStore({
    reducer: (state = preloadedState) => state,
    preloadedState,
  });
};

const renderAppAt = (
  path: string,
  userType: AuthUserType,
  capabilitiesOverride?: string[],
  options?: {
    activeOrganizationId?: string | null;
    organizationMemberships?: Array<{
      id: string;
      organization_id: string;
      membership_role: string;
      is_active: boolean;
    }>;
  },
) => {
  window.history.pushState({}, "", path);
  const store = buildStore(userType, capabilitiesOverride, options);
  return render(
    <Provider store={store}>
      <App />
    </Provider>,
  );
};

describe("App government route access", () => {
  afterEach(() => {
    cleanup();
    window.history.pushState({}, "", "/");
  });

  it("redirects internal without role/capability grants away from government appointments route", async () => {
    renderAppAt("/government/appointments", "internal");
    expect(await screen.findByText("Mock Dashboard Page")).toBeTruthy();
  });

  it("redirects internal with stale capability payload away from government appointments route", async () => {
    renderAppAt("/government/appointments", "internal", []);
    expect(await screen.findByText("Mock Dashboard Page")).toBeTruthy();
  });

  it("allows explicit capability-bearing users to access government appointments route", async () => {
    renderAppAt("/government/appointments", "internal", ["gams.appointment.view_internal"]);
    expect(await screen.findByText("Mock Appointments Registry Page", {}, { timeout: 5000 })).toBeTruthy();
  });

  it("redirects applicant away from government appointments route", async () => {
    renderAppAt("/government/appointments", "applicant");
    expect(await screen.findByText("Mock Dashboard Page")).toBeTruthy();
  });

  it("allows org-admin scoped internal users to access organization dashboard route", async () => {
    renderAppAt(
      "/organization/dashboard",
      "internal",
      [],
      {
        activeOrganizationId: "org-1",
        organizationMemberships: [
          {
            id: "m-1",
            organization_id: "org-1",
            membership_role: "registry_admin",
            is_active: true,
          },
        ],
      },
    );
    expect(await screen.findByText("Mock Organization Dashboard Page")).toBeTruthy();
  });

  it("redirects non-org-admin internal users away from organization dashboard route", async () => {
    renderAppAt(
      "/organization/dashboard",
      "internal",
      [],
      {
        activeOrganizationId: "org-1",
        organizationMemberships: [],
      },
    );
    expect(await screen.findByText("Mock Dashboard Page")).toBeTruthy();
  });

  it("redirects capability-only internal users away from organization dashboard route", async () => {
    renderAppAt(
      "/organization/dashboard",
      "internal",
      ["gams.registry.manage"],
      {
        activeOrganizationId: "org-1",
        organizationMemberships: [
          {
            id: "m-2",
            organization_id: "org-1",
            membership_role: "member",
            is_active: true,
          },
        ],
      },
    );
    expect(await screen.findByText("Mock Dashboard Page")).toBeTruthy();
  });

  it("allows platform admin to access organization dashboard route", async () => {
    renderAppAt("/organization/dashboard", "admin", [], {
      activeOrganizationId: "org-1",
      organizationMemberships: [],
    });
    expect(await screen.findByText("Mock Organization Dashboard Page")).toBeTruthy();
  });
});

