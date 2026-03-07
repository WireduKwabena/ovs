// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { cleanup, render, screen } from "@testing-library/react";

import { DashboardPage } from "./DashboardPage";

const mockUseAuth = vi.fn();

vi.mock("@/hooks/useAuth", () => ({
  useAuth: () => mockUseAuth(),
}));

vi.mock("@/hooks/useApplications", () => ({
  useApplications: () => ({
    applications: [],
    loading: false,
    refetch: vi.fn(),
  }),
}));

vi.mock("@/pages/OperationsDashboardPage", () => ({
  default: () => <div>Operations Dashboard Page</div>,
}));

describe("DashboardPage role routing", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("redirects admins to /admin/dashboard", async () => {
    mockUseAuth.mockReturnValue({ userType: "admin" });

    render(
      <MemoryRouter initialEntries={["/dashboard"]}>
        <Routes>
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/admin/dashboard" element={<div>Admin Dashboard Page</div>} />
        </Routes>
      </MemoryRouter>,
    );

    expect(await screen.findByText("Admin Dashboard Page")).toBeTruthy();
  });

  it("renders operations dashboard when user type is hr_manager", async () => {
    mockUseAuth.mockReturnValue({ userType: "hr_manager" });

    render(
      <MemoryRouter initialEntries={["/dashboard"]}>
        <Routes>
          <Route path="/dashboard" element={<DashboardPage />} />
        </Routes>
      </MemoryRouter>,
    );

    expect(await screen.findByText("Operations Dashboard Page")).toBeTruthy();
  });

  it("redirects applicant users to candidate access", async () => {
    mockUseAuth.mockReturnValue({ userType: "applicant" });

    render(
      <MemoryRouter initialEntries={["/dashboard"]}>
        <Routes>
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/candidate/access" element={<div>Candidate Access Page</div>} />
        </Routes>
      </MemoryRouter>,
    );

    expect(await screen.findByText("Candidate Access Page")).toBeTruthy();
  });
});

