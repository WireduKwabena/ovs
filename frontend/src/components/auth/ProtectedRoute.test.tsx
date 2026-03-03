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
    twoFactorRequired: false,
    twoFactorToken: null,
    ...auth,
  },
  _persist: { rehydrated: true },
});

const renderWithState = (
  state: GuardState,
  route: "/private" | "/admin-private" | "/no-applicant" = "/private",
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
});
