// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";
import { configureStore } from "@reduxjs/toolkit";
import { Provider } from "react-redux";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { cleanup, render, screen } from "@testing-library/react";

import { ProtectedRoute } from "./ProtectedRoute";

type GuardAuthState = {
  isAuthenticated: boolean;
  userType: "applicant" | "hr_manager" | "admin" | null;
  user: { is_staff?: boolean; is_superuser?: boolean } | null;
  roles: string[];
  capabilities: string[];
  organizationMemberships: Array<{
    id: string;
    organization_id: string;
    membership_role: string;
    is_active: boolean;
  }>;
  activeOrganization: { id: string } | null;
  twoFactorRequired: boolean;
  twoFactorToken: string | null;
};

type GuardState = {
  auth: GuardAuthState;
  _persist?: { rehydrated: boolean };
};

const createGuardState = (auth: Partial<GuardAuthState> = {}): GuardState => ({
  auth: {
    isAuthenticated: false,
    userType: null,
    user: null,
      roles: [],
      capabilities: [],
      organizationMemberships: [],
      activeOrganization: null,
      twoFactorRequired: false,
      twoFactorToken: null,
      ...auth,
  },
  _persist: { rehydrated: true },
});

const renderWithState = (
  state: GuardState,
  route:
    | "/private"
    | "/admin-private"
    | "/no-applicant"
    | "/applications"
    | "/applications/case-001"
    | "/campaigns"
    | "/campaigns/campaign-001"
    | "/rubrics"
    | "/rubrics/new"
    | "/government/positions"
    | "/government/personnel"
    | "/government/appointments"
    | "/audit-logs"
    | "/organization/dashboard" = "/private",
) => {
  const store = configureStore({
    reducer: (currentState: GuardState = state) => currentState,
    preloadedState: state,
  });

  render(
    <Provider store={store}>
      <MemoryRouter initialEntries={[route]}>
        <Routes>
          <Route path="/login" element={<div>Login page</div>} />
          <Route path="/login/2fa" element={<div>2FA page</div>} />
          <Route path="/dashboard" element={<div>Dashboard page</div>} />
          <Route path="/organization/setup" element={<div>Organization setup page</div>} />
          <Route
            path="/private"
            element={
              <ProtectedRoute>
                <div>Private page</div>
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin-private"
            element={
              <ProtectedRoute adminOnly>
                <div>Admin private page</div>
              </ProtectedRoute>
            }
          />
          <Route
            path="/no-applicant"
            element={
              <ProtectedRoute disallowUserTypes={["applicant"]}>
                <div>No applicant page</div>
              </ProtectedRoute>
            }
          />
          <Route
            path="/applications"
            element={
              <ProtectedRoute
                disallowUserTypes={["applicant"]}
                requiredCapabilities={[
                  "gams.registry.manage",
                  "gams.appointment.stage",
                  "gams.appointment.decide",
                  "gams.appointment.publish",
                  "gams.appointment.view_internal",
                ]}
                legacyUserTypeFallback={["hr_manager", "admin"]}
              >
                <div>Applications page</div>
              </ProtectedRoute>
            }
          />
          <Route
            path="/applications/:caseId"
            element={
              <ProtectedRoute
                disallowUserTypes={["applicant"]}
                requiredCapabilities={[
                  "gams.registry.manage",
                  "gams.appointment.stage",
                  "gams.appointment.decide",
                  "gams.appointment.publish",
                  "gams.appointment.view_internal",
                ]}
                legacyUserTypeFallback={["hr_manager", "admin"]}
              >
                <div>Application detail page</div>
              </ProtectedRoute>
            }
          />
          <Route
            path="/campaigns"
            element={
              <ProtectedRoute
                disallowUserTypes={["applicant"]}
                requiredCapabilities={[
                  "gams.registry.manage",
                  "gams.appointment.stage",
                  "gams.appointment.decide",
                  "gams.appointment.publish",
                  "gams.appointment.view_internal",
                ]}
                legacyUserTypeFallback={["hr_manager", "admin"]}
              >
                <div>Campaigns page</div>
              </ProtectedRoute>
            }
          />
          <Route
            path="/campaigns/:campaignId"
            element={
              <ProtectedRoute
                disallowUserTypes={["applicant"]}
                requiredCapabilities={[
                  "gams.registry.manage",
                  "gams.appointment.stage",
                  "gams.appointment.decide",
                  "gams.appointment.publish",
                  "gams.appointment.view_internal",
                ]}
                legacyUserTypeFallback={["hr_manager", "admin"]}
              >
                <div>Campaign workspace page</div>
              </ProtectedRoute>
            }
          />
          <Route
            path="/rubrics"
            element={
              <ProtectedRoute
                disallowUserTypes={["applicant"]}
                requiredCapabilities={[
                  "gams.registry.manage",
                  "gams.appointment.stage",
                  "gams.appointment.decide",
                ]}
                legacyUserTypeFallback={["hr_manager", "admin"]}
              >
                <div>Rubrics page</div>
              </ProtectedRoute>
            }
          />
          <Route
            path="/rubrics/new"
            element={
              <ProtectedRoute
                disallowUserTypes={["applicant"]}
                requiredCapabilities={[
                  "gams.registry.manage",
                  "gams.appointment.stage",
                  "gams.appointment.decide",
                ]}
                legacyUserTypeFallback={["hr_manager", "admin"]}
              >
                <div>Rubric builder page</div>
              </ProtectedRoute>
            }
          />
          <Route
            path="/government/positions"
            element={
              <ProtectedRoute
                disallowUserTypes={["applicant"]}
                requiredCapabilities={["gams.registry.manage"]}
                legacyUserTypeFallback={["hr_manager", "admin"]}
              >
                <div>Government positions page</div>
              </ProtectedRoute>
            }
          />
          <Route
            path="/government/personnel"
            element={
              <ProtectedRoute
                disallowUserTypes={["applicant"]}
                requiredCapabilities={["gams.registry.manage"]}
                legacyUserTypeFallback={["hr_manager", "admin"]}
              >
                <div>Government personnel page</div>
              </ProtectedRoute>
            }
          />
          <Route
            path="/government/appointments"
            element={
              <ProtectedRoute
                disallowUserTypes={["applicant"]}
                requiredCapabilities={[
                  "gams.registry.manage",
                  "gams.appointment.stage",
                  "gams.appointment.decide",
                  "gams.appointment.publish",
                  "gams.appointment.view_internal",
                ]}
                legacyUserTypeFallback={["hr_manager", "admin"]}
              >
                <div>Government appointments page</div>
              </ProtectedRoute>
            }
          />
          <Route
            path="/organization/dashboard"
            element={
              <ProtectedRoute
                disallowUserTypes={["applicant"]}
                requireOrganizationGovernance
                requireActiveOrganization
              >
                <div>Organization dashboard page</div>
              </ProtectedRoute>
            }
          />
          <Route
            path="/audit-logs"
            element={
              <ProtectedRoute
                requiredCapabilities={["gams.audit.view"]}
                legacyUserTypeFallback={["admin"]}
              >
                <div>Audit logs page</div>
              </ProtectedRoute>
            }
          />
        </Routes>
      </MemoryRouter>
    </Provider>,
  );
};

afterEach(() => {
  cleanup();
});

describe("ProtectedRoute integration", () => {
  it("redirects unauthenticated users to login", () => {
    renderWithState(createGuardState(), "/private");
    expect(screen.getByText("Login page")).toBeTruthy();
  });

  it("redirects active 2FA challenges to two-factor page", () => {
    renderWithState(
      createGuardState({
        twoFactorRequired: true,
        twoFactorToken: "challenge-token",
      }),
      "/private",
    );
    expect(screen.getByText("2FA page")).toBeTruthy();
  });

  it("renders children when authenticated", () => {
    renderWithState(
      createGuardState({
        isAuthenticated: true,
        userType: "hr_manager",
      }),
      "/private",
    );
    expect(screen.getByText("Private page")).toBeTruthy();
  });

  it("redirects non-admin users from admin-only routes", () => {
    renderWithState(
      createGuardState({
        isAuthenticated: true,
        userType: "hr_manager",
      }),
      "/admin-private",
    );
    expect(screen.getByText("Dashboard page")).toBeTruthy();
  });

  it("does not allow staff-only users on admin-only routes", () => {
    renderWithState(
      createGuardState({
        isAuthenticated: true,
        userType: "hr_manager",
        user: { is_staff: true, is_superuser: false },
      }),
      "/admin-private",
    );
    expect(screen.getByText("Dashboard page")).toBeTruthy();
  });

  it("allows users with admin role on admin-only routes", () => {
    renderWithState(
      createGuardState({
        isAuthenticated: true,
        userType: "hr_manager",
        roles: ["admin"],
      }),
      "/admin-private",
    );
    expect(screen.getByText("Admin private page")).toBeTruthy();
  });

  it("redirects disallowed user types to dashboard", () => {
    renderWithState(
      createGuardState({
        isAuthenticated: true,
        userType: "applicant",
      }),
      "/no-applicant",
    );
    expect(screen.getByText("Dashboard page")).toBeTruthy();
  });

  it("shows loader while rehydration is incomplete", () => {
    const state = createGuardState({
      isAuthenticated: true,
      userType: "admin",
    });
    state._persist = { rehydrated: false };

    renderWithState(state, "/private");
    expect(screen.queryByText("Private page")).toBeNull();
    expect(screen.queryByText("Login page")).toBeNull();
    expect(screen.queryByText("2FA page")).toBeNull();
  });

  it("allows admin users on /applications", () => {
    renderWithState(
      createGuardState({
        isAuthenticated: true,
        userType: "admin",
      }),
      "/applications",
    );
    expect(screen.getByText("Applications page")).toBeTruthy();
  });

  it("allows hr_manager users on /applications", () => {
    renderWithState(
      createGuardState({
        isAuthenticated: true,
        userType: "hr_manager",
      }),
      "/applications",
    );
    expect(screen.getByText("Applications page")).toBeTruthy();
  });

  it("redirects applicants away from /applications", () => {
    renderWithState(
      createGuardState({
        isAuthenticated: true,
        userType: "applicant",
      }),
      "/applications",
    );
    expect(screen.getByText("Dashboard page")).toBeTruthy();
  });

  it("allows admin users on /applications/:caseId routes", () => {
    renderWithState(
      createGuardState({
        isAuthenticated: true,
        userType: "admin",
      }),
      "/applications/case-001",
    );
    expect(screen.getByText("Application detail page")).toBeTruthy();
  });

  it("redirects applicants away from /campaigns", () => {
    renderWithState(
      createGuardState({
        isAuthenticated: true,
        userType: "applicant",
      }),
      "/campaigns",
    );
    expect(screen.getByText("Dashboard page")).toBeTruthy();
  });

  it("redirects applicants away from /campaigns/:campaignId", () => {
    renderWithState(
      createGuardState({
        isAuthenticated: true,
        userType: "applicant",
      }),
      "/campaigns/campaign-001",
    );
    expect(screen.getByText("Dashboard page")).toBeTruthy();
  });

  it("allows hr_manager on /campaigns", () => {
    renderWithState(
      createGuardState({
        isAuthenticated: true,
        userType: "hr_manager",
      }),
      "/campaigns",
    );
    expect(screen.getByText("Campaigns page")).toBeTruthy();
  });

  it("allows admin on /campaigns", () => {
    renderWithState(
      createGuardState({
        isAuthenticated: true,
        userType: "admin",
      }),
      "/campaigns",
    );
    expect(screen.getByText("Campaigns page")).toBeTruthy();
  });

  it("redirects applicants away from /rubrics", () => {
    renderWithState(
      createGuardState({
        isAuthenticated: true,
        userType: "applicant",
      }),
      "/rubrics",
    );
    expect(screen.getByText("Dashboard page")).toBeTruthy();
  });

  it("redirects applicants away from /rubrics/new", () => {
    renderWithState(
      createGuardState({
        isAuthenticated: true,
        userType: "applicant",
      }),
      "/rubrics/new",
    );
    expect(screen.getByText("Dashboard page")).toBeTruthy();
  });

  it("redirects applicants away from /government/* routes", () => {
    const routes: Array<"/government/positions" | "/government/personnel" | "/government/appointments"> = [
      "/government/positions",
      "/government/personnel",
      "/government/appointments",
    ];

    routes.forEach((route) => {
      renderWithState(
        createGuardState({
          isAuthenticated: true,
          userType: "applicant",
        }),
        route,
      );
      expect(screen.getByText("Dashboard page")).toBeTruthy();
      cleanup();
    });
  });

  it("allows hr_manager on /government/appointments", () => {
    renderWithState(
      createGuardState({
        isAuthenticated: true,
        userType: "hr_manager",
        capabilities: ["gams.appointment.stage"],
      }),
      "/government/appointments",
    );
    expect(screen.getByText("Government appointments page")).toBeTruthy();
  });

  it("allows admin on /government/appointments", () => {
    renderWithState(
      createGuardState({
        isAuthenticated: true,
        userType: "admin",
        capabilities: ["gams.appointment.stage"],
      }),
      "/government/appointments",
    );
    expect(screen.getByText("Government appointments page")).toBeTruthy();
  });

  it("allows hr_manager on /government/appointments even when capabilities are stale", () => {
    renderWithState(
      createGuardState({
        isAuthenticated: true,
        userType: "hr_manager",
        capabilities: [],
      }),
      "/government/appointments",
    );
    expect(screen.getByText("Government appointments page")).toBeTruthy();
  });

  it("blocks hr_manager users when capability payload exists but lacks required permission", () => {
    renderWithState(
      createGuardState({
        isAuthenticated: true,
        userType: "hr_manager",
        capabilities: ["gams.audit.view"],
      }),
      "/government/positions",
    );
    expect(screen.getByText("Dashboard page")).toBeTruthy();
  });

  it("allows users with gams.audit.view capability on /audit-logs", () => {
    renderWithState(
      createGuardState({
        isAuthenticated: true,
        userType: "hr_manager",
        capabilities: ["gams.audit.view"],
      }),
      "/audit-logs",
    );
    expect(screen.getByText("Audit logs page")).toBeTruthy();
  });

  it("blocks users without gams.audit.view capability from /audit-logs", () => {
    renderWithState(
      createGuardState({
        isAuthenticated: true,
        userType: "hr_manager",
      }),
      "/audit-logs",
    );
    expect(screen.getByText("Dashboard page")).toBeTruthy();
  });

  it("allows admin on /audit-logs even when capabilities are stale", () => {
    renderWithState(
      createGuardState({
        isAuthenticated: true,
        userType: "admin",
        capabilities: [],
      }),
      "/audit-logs",
    );
    expect(screen.getByText("Audit logs page")).toBeTruthy();
  });

  it("allows hr_manager with active org-admin membership on governance routes", () => {
    renderWithState(
      createGuardState({
        isAuthenticated: true,
        userType: "hr_manager",
        organizationMemberships: [
          {
            id: "m-1",
            organization_id: "org-1",
            membership_role: "registry_admin",
            is_active: true,
          },
        ],
        activeOrganization: { id: "org-1" },
      }),
      "/organization/dashboard",
    );
    expect(screen.getByText("Organization dashboard page")).toBeTruthy();
  });

  it("redirects governance actors to organization setup when active organization is missing", () => {
    renderWithState(
      createGuardState({
        isAuthenticated: true,
        userType: "hr_manager",
        organizationMemberships: [
          {
            id: "m-1",
            organization_id: "org-1",
            membership_role: "registry_admin",
            is_active: true,
          },
        ],
        activeOrganization: null,
      }),
      "/organization/dashboard",
    );
    expect(screen.getByText("Organization setup page")).toBeTruthy();
  });

  it("blocks hr_manager without governance membership on governance routes", () => {
    renderWithState(
      createGuardState({
        isAuthenticated: true,
        userType: "hr_manager",
        organizationMemberships: [],
        activeOrganization: { id: "org-1" },
      }),
      "/organization/dashboard",
    );
    expect(screen.getByText("Dashboard page")).toBeTruthy();
  });

  it("allows platform admin on governance routes", () => {
    renderWithState(
      createGuardState({
        isAuthenticated: true,
        userType: "admin",
        activeOrganization: { id: "org-1" },
      }),
      "/organization/dashboard",
    );
    expect(screen.getByText("Organization dashboard page")).toBeTruthy();
  });
});
