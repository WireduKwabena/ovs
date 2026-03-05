// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import UserSettingsPage from "./UserSettingsPage";

const mocks = vi.hoisted(() => ({
  getSubscriptionManagement: vi.fn(),
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

  it("shows add subscription action when subscription is missing", async () => {
    mocks.useAuth.mockReturnValue({
      userType: "hr_manager",
      user: {
        id: "user-1",
        email: "hr@example.com",
        first_name: "HR",
        last_name: "Manager",
        full_name: "HR Manager",
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
      await screen.findByRole("button", { name: /add subscription & payment method/i }),
    ).toBeTruthy();
  });
});
