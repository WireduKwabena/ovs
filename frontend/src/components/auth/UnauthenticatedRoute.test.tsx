// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";
import { configureStore } from "@reduxjs/toolkit";
import { Provider } from "react-redux";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { cleanup, render, screen } from "@testing-library/react";

import { UnauthenticatedRoute } from "./UnauthenticatedRoute";

type PublicAuthState = {
  isAuthenticated: boolean;
  userType: "applicant" | "internal" | "admin" | null;
  twoFactorRequired: boolean;
  twoFactorToken: string | null;
};

type PublicState = {
  auth: PublicAuthState;
  _persist?: { rehydrated: boolean };
};

const createPublicState = (auth: Partial<PublicAuthState> = {}): PublicState => ({
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
  state: PublicState,
  route:
    | "/login"
    | "/register"
    | "/forgot-password"
    | "/reset-password/token"
    | "/login/2fa" = "/login",
) => {
  const store = configureStore({
    reducer: (currentState: PublicState = state) => currentState,
    preloadedState: state,
  });

  render(
    <Provider store={store}>
      <MemoryRouter initialEntries={[route]}>
        <Routes>
          <Route path="/dashboard" element={<div>Dashboard page</div>} />
          <Route path="/admin/platform/dashboard" element={<div>Platform dashboard page</div>} />
          <Route path="/candidate/home" element={<div>Candidate home page</div>} />

          <Route
            path="/login"
            element={
              <UnauthenticatedRoute>
                <div>Login page</div>
              </UnauthenticatedRoute>
            }
          />
          <Route
            path="/register"
            element={
              <UnauthenticatedRoute>
                <div>Register page</div>
              </UnauthenticatedRoute>
            }
          />
          <Route
            path="/forgot-password"
            element={
              <UnauthenticatedRoute>
                <div>Forgot password page</div>
              </UnauthenticatedRoute>
            }
          />
          <Route
            path="/reset-password/:token"
            element={
              <UnauthenticatedRoute>
                <div>Reset password page</div>
              </UnauthenticatedRoute>
            }
          />
          <Route
            path="/login/2fa"
            element={
              <UnauthenticatedRoute allowTwoFactorChallenge>
                <div>Two-factor challenge page</div>
              </UnauthenticatedRoute>
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

describe("UnauthenticatedRoute integration", () => {
  it("renders login page for unauthenticated users", () => {
    renderWithState(createPublicState(), "/login");
    expect(screen.getByText("Login page")).toBeTruthy();
  });

  it("redirects active two-factor challenge to /login/2fa on public routes", () => {
    renderWithState(
      createPublicState({
        twoFactorRequired: true,
        twoFactorToken: "challenge",
      }),
      "/register",
    );
    expect(screen.getByText("Two-factor challenge page")).toBeTruthy();
  });

  it("allows active challenge through on /login/2fa route", () => {
    renderWithState(
      createPublicState({
        twoFactorRequired: true,
        twoFactorToken: "challenge",
      }),
      "/login/2fa",
    );
    expect(screen.getByText("Two-factor challenge page")).toBeTruthy();
  });

  it("redirects authenticated internal users to shared workspace", () => {
    renderWithState(
      createPublicState({
        isAuthenticated: true,
        userType: "internal",
      }),
      "/forgot-password",
    );
    expect(screen.getByText("Dashboard page")).toBeTruthy();
  });

  it("redirects authenticated admins to the shared dashboard resolver", () => {
    renderWithState(
      createPublicState({
        isAuthenticated: true,
        userType: "admin",
      }),
      "/reset-password/token",
    );
    expect(screen.getByText("Platform dashboard page")).toBeTruthy();
  });

  it("redirects authenticated applicants to candidate home", () => {
    renderWithState(
      createPublicState({
        isAuthenticated: true,
        userType: "applicant",
      }),
      "/login",
    );
    expect(screen.getByText("Candidate home page")).toBeTruthy();
  });

  it("shows loader while auth state is still rehydrating", () => {
    const state = createPublicState();
    state._persist = { rehydrated: false };

    renderWithState(state, "/login");
    expect(screen.getByTestId("unauth-route-loader")).toBeTruthy();
    expect(screen.queryByText("Login page")).toBeNull();
  });
});

