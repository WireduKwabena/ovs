// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

const mocks = vi.hoisted(() => ({
  validateOnboardingToken: vi.fn(),
  toastError: vi.fn(),
}));

vi.mock("@/services/auth.service", () => ({
  authService: { validateOnboardingToken: mocks.validateOnboardingToken },
}));
vi.mock("react-toastify", () => ({
  toast: { error: mocks.toastError, success: vi.fn() },
}));
vi.mock("@/components/auth/RegisterForm", () => ({
  RegisterForm: ({ organizationName }: { organizationName?: string }) => (
    <div data-testid="register-form">{organizationName}</div>
  ),
}));

const { RegisterPage } = await import("./RegisterPage");

const renderWithToken = (token?: string, org?: string) => {
  const qs = token
    ? `?onboarding_token=${token}${org ? `&org=${org}` : ""}`
    : "";
  return render(
    <MemoryRouter initialEntries={[`/register${qs}`]}>
      <Routes>
        <Route path="/register" element={<RegisterPage />} />
      </Routes>
    </MemoryRouter>,
  );
};

describe("RegisterPage", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
    sessionStorage.clear();
  });

  it("shows a missing-token error when no onboarding_token param", async () => {
    renderWithToken();
    await waitFor(() =>
      expect(
        screen.getByText(/valid onboarding invitation link is required/i),
      ).toBeTruthy(),
    );
  });

  it("calls validateOnboardingToken when token is present", async () => {
    mocks.validateOnboardingToken.mockResolvedValue({
      valid: true,
      organization_name: "Ministry HQ",
    });
    renderWithToken("abc123", "min-hq");
    await waitFor(() =>
      expect(mocks.validateOnboardingToken).toHaveBeenCalledWith({
        token: "abc123",
      }),
    );
  });

  it("shows the RegisterForm on a valid token", async () => {
    mocks.validateOnboardingToken.mockResolvedValue({
      valid: true,
      organization_name: "Ministry HQ",
    });
    renderWithToken("abc123");
    await waitFor(() =>
      expect(screen.getByTestId("register-form")).toBeTruthy(),
    );
    expect(screen.getByText("Ministry HQ")).toBeTruthy();
  });

  it("shows an error message when token is invalid", async () => {
    mocks.validateOnboardingToken.mockResolvedValue({
      valid: false,
      reason: "expired",
    });
    renderWithToken("expired-tok");
    await waitFor(() => expect(screen.getByText(/expired/i)).toBeTruthy());
  });
});
