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

vi.mock("./pages/DashboardPage", () => ({
  __esModule: true,
  DashboardPage: () => <div>Mock Dashboard Page</div>,
  default: () => <div>Mock Dashboard Page</div>,
}));

type AuthUserType = "applicant" | "hr_manager" | "admin" | null;

const buildStore = (userType: AuthUserType) => {
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

const renderAppAt = (path: string, userType: AuthUserType) => {
  window.history.pushState({}, "", path);
  const store = buildStore(userType);
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

  it("allows hr_manager to access government appointments route", async () => {
    renderAppAt("/government/appointments", "hr_manager");
    expect(await screen.findByText("Mock Appointments Registry Page")).toBeTruthy();
  });

  it("redirects applicant away from government appointments route", async () => {
    renderAppAt("/government/appointments", "applicant");
    expect(await screen.findByText("Mock Dashboard Page")).toBeTruthy();
  });
});
