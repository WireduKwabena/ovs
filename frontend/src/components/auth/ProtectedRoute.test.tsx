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
    | "/applications/new"
    | "/applications/case-001"
    | "/applications/case-001/upload"
    | "/campaigns"
    | "/campaigns/campaign-001"
    | "/rubrics"
    | "/rubrics/new" = "/private",
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
              <ProtectedRoute disallowUserTypes={["admin"]}>
                <div>Applications page</div>
              </ProtectedRoute>
            }
          />
          <Route
            path="/applications/new"
            element={
              <ProtectedRoute disallowUserTypes={["hr_manager", "admin"]}>
                <div>New application page</div>
              </ProtectedRoute>
            }
          />
          <Route
            path="/applications/:caseId"
            element={
              <ProtectedRoute disallowUserTypes={["admin"]}>
                <div>Application detail page</div>
              </ProtectedRoute>
            }
          />
          <Route
            path="/applications/:caseId/upload"
            element={
              <ProtectedRoute disallowUserTypes={["admin"]}>
                <div>Upload document page</div>
              </ProtectedRoute>
            }
          />
          <Route
            path="/campaigns"
            element={
              <ProtectedRoute disallowUserTypes={["applicant"]}>
                <div>Campaigns page</div>
              </ProtectedRoute>
            }
          />
          <Route
            path="/campaigns/:campaignId"
            element={
              <ProtectedRoute disallowUserTypes={["applicant"]}>
                <div>Campaign workspace page</div>
              </ProtectedRoute>
            }
          />
          <Route
            path="/rubrics"
            element={
              <ProtectedRoute disallowUserTypes={["applicant"]}>
                <div>Rubrics page</div>
              </ProtectedRoute>
            }
          />
          <Route
            path="/rubrics/new"
            element={
              <ProtectedRoute disallowUserTypes={["applicant"]}>
                <div>Rubric builder page</div>
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

  it("allows staff users on admin-only routes even when user_type is not admin", () => {
    renderWithState(
      createGuardState({
        isAuthenticated: true,
        userType: "hr_manager",
        user: { is_staff: true, is_superuser: false },
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

  it("redirects admin users away from /applications to dashboard", () => {
    renderWithState(
      createGuardState({
        isAuthenticated: true,
        userType: "admin",
      }),
      "/applications",
    );
    expect(screen.getByText("Dashboard page")).toBeTruthy();
  });

  it("blocks hr_manager from /applications/new", () => {
    renderWithState(
      createGuardState({
        isAuthenticated: true,
        userType: "hr_manager",
      }),
      "/applications/new",
    );
    expect(screen.getByText("Dashboard page")).toBeTruthy();
  });

  it("allows applicants to access /applications/new", () => {
    renderWithState(
      createGuardState({
        isAuthenticated: true,
        userType: "applicant",
      }),
      "/applications/new",
    );
    expect(screen.getByText("New application page")).toBeTruthy();
  });

  it("redirects admin users away from /applications/:caseId routes", () => {
    renderWithState(
      createGuardState({
        isAuthenticated: true,
        userType: "admin",
      }),
      "/applications/case-001",
    );
    expect(screen.getByText("Dashboard page")).toBeTruthy();
  });

  it("redirects admin users away from /applications/:caseId/upload", () => {
    renderWithState(
      createGuardState({
        isAuthenticated: true,
        userType: "admin",
      }),
      "/applications/case-001/upload",
    );
    expect(screen.getByText("Dashboard page")).toBeTruthy();
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
});
