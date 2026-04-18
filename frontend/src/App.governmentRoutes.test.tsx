// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { configureStore } from "@reduxjs/toolkit";
import { Provider } from "react-redux";

import App from "./App";

const FETCH_PROFILE_PENDING = "auth/fetchProfile/pending";
const SWITCH_ACTIVE_ORGANIZATION_PENDING = "/auth/profile/active-organization//pending";
const SWITCH_ACTIVE_ORGANIZATION_REJECTED = "/auth/profile/active-organization//rejected";

vi.mock("./store/authSlice", () => {
  const authReducer = (state = {}) => state;
  return {
    __esModule: true,
    default: authReducer,
    fetchProfile: vi.fn(() => ({ type: FETCH_PROFILE_PENDING })),
    switchActiveOrganization: vi.fn((organizationId: string) => async (dispatch: (action: unknown) => unknown) => {
      const meta = { arg: organizationId };
      dispatch({
        type: SWITCH_ACTIVE_ORGANIZATION_PENDING,
        meta,
      });
      const rejectedAction = {
        type: SWITCH_ACTIVE_ORGANIZATION_REJECTED,
        payload: { message: "Failed to update active organization" },
        meta,
        error: { message: "Rejected" },
      };
      dispatch(rejectedAction);
      return rejectedAction;
    }),
  };
});

vi.mock("./components/common/Navbar", () => ({
  Navbar: () => <div data-testid="mock-navbar">Mock Navbar</div>,
}));

vi.mock("./pages/HomePage", () => ({
  default: () => <div>Mock Home Page</div>,
}));

vi.mock("./pages/OrganizationSetupPage", () => ({
  default: () => <div>Mock Organization Setup Page</div>,
}));

vi.mock("./pages/AppointmentsRegistryPage", () => ({
  default: () => <div>Mock Appointments Registry Page</div>,
}));

vi.mock("./pages/platform-admin/PlatformDashboardPage", () => ({
  default: () => <div>Mock Platform Dashboard Page</div>,
}));

vi.mock("./pages/candidate/CandidateHomePage", () => ({
  default: () => <div>Mock Candidate Home Page</div>,
}));

vi.mock("./pages/GovernmentPositionsPage", () => ({
  default: () => <div>Mock Government Positions Page</div>,
}));

vi.mock("./pages/GovernmentPersonnelPage", () => ({
  default: () => <div>Mock Government Personnel Page</div>,
}));

vi.mock("./pages/org-admin/OrgDashboardPage", () => ({
  default: () => <div>Mock Organization Dashboard Page</div>,
}));

vi.mock("./pages/org-admin/OrgUsersPage", () => ({
  default: () => <div>Mock Organization Users Page</div>,
}));

vi.mock("./components/admin/CaseReview", () => ({
  CaseReview: () => <div>Mock Case Review Page</div>,
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
      switchingActiveOrganization: false,
      error: null,
      passwordResetEmailSent: false,
      twoFactorRequired: false,
      twoFactorToken: null,
      twoFactorSetupRequired: false,
      twoFactorProvisioningUri: null,
      twoFactorExpiresInSeconds: null,
      twoFactorMessage: null,
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
    reducer: {
      auth: (state = preloadedState.auth, action: { type: string; payload?: { message?: string } }) => {
        switch (action.type) {
          case SWITCH_ACTIVE_ORGANIZATION_PENDING:
            return {
              ...state,
              switchingActiveOrganization: true,
              error: null,
            };
          case SWITCH_ACTIVE_ORGANIZATION_REJECTED:
            return {
              ...state,
              switchingActiveOrganization: false,
              error: action.payload?.message || "Failed to update active organization",
            };
          default:
            return state;
        }
      },
      notifications: (state = preloadedState.notifications) => state,
      _persist: (state = preloadedState._persist) => state,
    },
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
    expect(await screen.findByText("Mock Candidate Home Page")).toBeTruthy();
  });

  it("allows org-admin scoped internal users to access organization dashboard route", async () => {
    renderAppAt(
      "/admin/org/org-1/dashboard",
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
      "/admin/org/org-1/dashboard",
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
      "/admin/org/org-1/dashboard",
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

  it("redirects legacy organization dashboard route to organization setup when active org is missing", async () => {
    renderAppAt("/organization/dashboard", "internal", [], {
      activeOrganizationId: null,
      organizationMemberships: [
        {
          id: "m-4",
          organization_id: "org-1",
          membership_role: "registry_admin",
          is_active: true,
        },
      ],
    });
    expect(await screen.findByText("Mock Organization Setup Page")).toBeTruthy();
  });

  it("fails closed to organization setup when org dashboard route orgId is mismatched", async () => {
    renderAppAt("/admin/org/org-2/dashboard", "internal", [], {
      activeOrganizationId: "org-1",
      organizationMemberships: [
        {
          id: "m-5",
          organization_id: "org-1",
          membership_role: "registry_admin",
          is_active: true,
        },
      ],
    });
    await waitFor(() => {
      expect(window.location.pathname).toBe("/organization/setup");
      expect(decodeURIComponent(window.location.search)).toContain(
        "next=/admin/org/org-2/dashboard",
      );
    });
  });

  it("redirects platform admin away from organization dashboard route", async () => {
    renderAppAt("/admin/org/org-1/dashboard", "admin", [], {
      activeOrganizationId: "org-1",
      organizationMemberships: [],
    });
    expect(await screen.findByText("Mock Platform Dashboard Page")).toBeTruthy();
  });

  it("redirects platform admin away from organization setup routes", async () => {
    renderAppAt("/organization/setup", "admin", [], {
      activeOrganizationId: "org-1",
      organizationMemberships: [],
    });
    expect(await screen.findByText("Mock Platform Dashboard Page")).toBeTruthy();
  });

  it("redirects platform admin away from appointment exercise routes", async () => {
    renderAppAt("/workspace/campaigns", "admin", [], {
      activeOrganizationId: "org-1",
      organizationMemberships: [],
    });
    expect(await screen.findByText("Mock Platform Dashboard Page")).toBeTruthy();
  });

  it("redirects platform admin away from appointment workflow routes", async () => {
    renderAppAt("/government/appointments", "admin", [], {
      activeOrganizationId: "org-1",
      organizationMemberships: [],
    });
    expect(await screen.findByText("Mock Platform Dashboard Page")).toBeTruthy();
  });

  it("redirects retired platform analytics routes back to the platform dashboard", async () => {
    renderAppAt("/admin/platform/analytics", "admin", [], {
      activeOrganizationId: "org-1",
      organizationMemberships: [],
    });
    expect(await screen.findByText("Mock Platform Dashboard Page")).toBeTruthy();
  });

  it("redirects retired platform registration routes back to the platform dashboard", async () => {
    renderAppAt("/admin/platform/register", "admin", [], {
      activeOrganizationId: "org-1",
      organizationMemberships: [],
    });
    expect(await screen.findByText("Mock Platform Dashboard Page")).toBeTruthy();
  });

  it("redirects legacy admin case routes away from platform admin and into org scope for org admins", async () => {
    renderAppAt("/admin/cases", "internal", [], {
      activeOrganizationId: "org-1",
      organizationMemberships: [
        {
          id: "m-6",
          organization_id: "org-1",
          membership_role: "registry_admin",
          is_active: true,
        },
      ],
    });

    await waitFor(() => {
      expect(window.location.pathname).toBe("/admin/org/org-1/cases");
    });
  });

  it("allows org-admin scoped internal users to access organization case review routes", async () => {
    renderAppAt("/admin/org/org-1/cases/case-001", "internal", [], {
      activeOrganizationId: "org-1",
      organizationMemberships: [
        {
          id: "m-7",
          organization_id: "org-1",
          membership_role: "registry_admin",
          is_active: true,
        },
      ],
    });
    expect(await screen.findByText("Mock Case Review Page")).toBeTruthy();
  });

  it("allows platform admins to access the platform-only organization users route", async () => {
    renderAppAt("/admin/org/org-1/users", "admin", [], {
      activeOrganizationId: "org-1",
      organizationMemberships: [],
    });

    expect(await screen.findByText("Mock Organization Users Page")).toBeTruthy();
  });

  it("redirects org-admin scoped internal users away from platform admin routes", async () => {
    renderAppAt("/admin/platform/dashboard", "internal", [], {
      activeOrganizationId: "org-1",
      organizationMemberships: [
        {
          id: "m-3",
          organization_id: "org-1",
          membership_role: "registry_admin",
          is_active: true,
        },
      ],
    });
    expect(await screen.findByText("Mock Dashboard Page")).toBeTruthy();
  });

  it("redirects org-admin scoped internal users away from the platform-only organization users route", async () => {
    renderAppAt("/admin/org/org-1/users", "internal", [], {
      activeOrganizationId: "org-1",
      organizationMemberships: [
        {
          id: "m-8",
          organization_id: "org-1",
          membership_role: "registry_admin",
          is_active: true,
        },
      ],
    });

    expect(await screen.findByText("Mock Dashboard Page")).toBeTruthy();
  });

  it("shows app navigation and content offset on internal dashboard routes", async () => {
    renderAppAt("/dashboard", "internal", ["gams.campaign.manage"]);

    expect(await screen.findByText("Mock Dashboard Page")).toBeTruthy();
    expect(screen.getByTestId("mock-navbar")).toBeTruthy();

    const main = screen.getByRole("main");
    expect(main.className).toContain("relative");
    expect(main.className).toContain("lg:pl-64");
    expect(main.className).toContain("xl:pl-72");
  });

  it("hides app navigation and shell offset on the homepage", async () => {
    renderAppAt("/", "internal", ["gams.campaign.manage"]);

    await waitFor(() => {
      expect(screen.queryByText("Mock Home Page")).toBeTruthy();
    });
    expect(screen.queryByTestId("mock-navbar")).toBeNull();

    const main = screen.getByRole("main");
    expect(main.className).not.toContain("relative");
    expect(main.className).not.toContain("lg:pl-64");
    expect(main.className).not.toContain("xl:pl-72");
  });
});

