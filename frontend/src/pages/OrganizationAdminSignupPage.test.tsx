// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";

import OrganizationAdminSignupPage from "./OrganizationAdminSignupPage";

const mocks = vi.hoisted(() => ({
  registerOrganizationAdmin: vi.fn(),
  toastSuccess: vi.fn(),
  toastError: vi.fn(),
}));

vi.mock("@/services/auth.service", () => ({
  authService: {
    registerOrganizationAdmin: mocks.registerOrganizationAdmin,
  },
}));

vi.mock("react-toastify", () => ({
  toast: {
    success: mocks.toastSuccess,
    error: mocks.toastError,
  },
}));

const LoginProbe: React.FC = () => {
  const location = useLocation();
  return <div data-testid="login-location">{`${location.pathname}${location.search}`}</div>;
};

const renderAt = (route = "/organization/get-started") =>
  render(
    <MemoryRouter initialEntries={[route]}>
      <Routes>
        <Route path="/organization/get-started" element={<OrganizationAdminSignupPage />} />
        <Route path="/login" element={<LoginProbe />} />
      </Routes>
    </MemoryRouter>,
  );

const fillRequiredFields = () => {
  fireEvent.change(screen.getByLabelText(/first name/i), { target: { value: "Ada" } });
  fireEvent.change(screen.getByLabelText(/last name/i), { target: { value: "Mensah" } });
  fireEvent.change(screen.getByLabelText(/work email/i), {
    target: { value: "  ADA.MENSAH@EXAMPLE.COM " },
  });
  fireEvent.change(screen.getByLabelText(/phone number/i), { target: { value: "+12345678901" } });
  fireEvent.change(screen.getByLabelText(/^department$/i), { target: { value: " Registry " } });
  fireEvent.change(screen.getByLabelText(/^password$/i), { target: { value: "Pass1234!" } });
  fireEvent.change(screen.getByLabelText(/confirm password/i), { target: { value: "Pass1234!" } });
  fireEvent.change(screen.getByLabelText(/organization name/i), {
    target: { value: " Public Service Commission " },
  });
  fireEvent.change(screen.getByLabelText(/organization code/i), {
    target: { value: " public-service-commission " },
  });
};

describe("OrganizationAdminSignupPage", () => {
  beforeEach(() => {
    mocks.registerOrganizationAdmin.mockResolvedValue({
      message: "ok",
      user_type: "internal",
      user: {},
      organization: {},
      membership: {},
    });
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("uses next query path for login redirect after successful signup", async () => {
    renderAt("/organization/get-started?next=%2Forganization%2Fonboarding");
    fillRequiredFields();

    fireEvent.click(screen.getByRole("button", { name: /create organization account/i }));

    await waitFor(() => {
      expect(mocks.registerOrganizationAdmin).toHaveBeenCalledTimes(1);
    });

    expect(mocks.registerOrganizationAdmin).toHaveBeenCalledWith(
      expect.objectContaining({
        email: "ada.mensah@example.com",
        first_name: "Ada",
        last_name: "Mensah",
        department: "Registry",
        organization_name: "Public Service Commission",
        organization_code: "public-service-commission",
      }),
    );
    expect(mocks.toastSuccess).toHaveBeenCalled();
    await waitFor(() => {
      expect(screen.getByTestId("login-location")).toBeTruthy();
    });
    const loginLocation = String(screen.getByTestId("login-location").textContent || "");
    expect(loginLocation.startsWith("/login?")).toBe(true);
    const queryString = loginLocation.split("?")[1] || "";
    const nextValue = new URLSearchParams(queryString).get("next");
    expect(nextValue).toBe("/organization/onboarding");
  });

  it("falls back to /subscribe when next query is unsafe", () => {
    renderAt("/organization/get-started?next=https://example.com");
    expect(screen.getByText(/next step after sign-in:/i).textContent).toContain("/subscribe");
  });

  it("shows API error and does not navigate on failure", async () => {
    mocks.registerOrganizationAdmin.mockRejectedValueOnce(new Error("Organization account setup failed"));

    renderAt("/organization/get-started?next=%2Fsubscribe");
    fillRequiredFields();

    fireEvent.click(screen.getByRole("button", { name: /create organization account/i }));

    await waitFor(() => {
      expect(mocks.toastError).toHaveBeenCalled();
    });
    expect(screen.queryByTestId("login-location")).toBeNull();
  });
});
