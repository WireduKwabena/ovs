// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { AdminDashboard } from "./Dashboard";

const mocks = vi.hoisted(() => ({
  getDashboard: vi.fn(),
}));

vi.mock("@/services/admin.service", () => ({
  adminService: {
    getDashboard: mocks.getDashboard,
  },
}));

vi.mock("@/components/admin/BillingHealthCard", () => ({
  default: () => <div>Billing Health</div>,
}));

vi.mock("@/components/admin/ReminderHealthCard", () => ({
  default: () => <div>Reminder Health</div>,
}));

const renderAdminDashboard = () =>
  render(
    <MemoryRouter initialEntries={["/admin/dashboard"]}>
      <Routes>
        <Route path="/admin/dashboard" element={<AdminDashboard />} />
        <Route path="/admin/organizations" element={<div>Organizations Route</div>} />
        <Route path="/admin/users" element={<div>Organization Admins Route</div>} />
        <Route path="/admin/analytics" element={<div>Analytics Route</div>} />
        <Route path="/video-calls" element={<div>Runtime Route</div>} />
        <Route path="/audit-logs" element={<div>Audit Route</div>} />
        <Route path="/fraud-insights" element={<div>Risk Signals Route</div>} />
      </Routes>
    </MemoryRouter>,
  );

describe("AdminDashboard platform quick actions", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  const buildDashboardPayload = () => ({
    total_applications: 8,
    pending: 2,
    under_review: 1,
    approved: 4,
    rejected: 1,
    recent_applications: [],
  });

  it("navigates to organizations setup", async () => {
    mocks.getDashboard.mockResolvedValue(buildDashboardPayload());

    renderAdminDashboard();

    fireEvent.click(await screen.findByRole("button", { name: /organizations/i }));
    expect(await screen.findByText("Organizations Route")).toBeTruthy();
  });

  it("navigates to organization-admin management", async () => {
    mocks.getDashboard.mockResolvedValue(buildDashboardPayload());

    renderAdminDashboard();

    fireEvent.click(await screen.findByRole("button", { name: /organization admins/i }));
    expect(await screen.findByText("Organization Admins Route")).toBeTruthy();
  });

  it("navigates to runtime", async () => {
    mocks.getDashboard.mockResolvedValue(buildDashboardPayload());

    renderAdminDashboard();

    fireEvent.click(await screen.findByRole("button", { name: /open runtime/i }));
    expect(await screen.findByText("Runtime Route")).toBeTruthy();
  });

  it("renders platform quick action buttons", async () => {
    mocks.getDashboard.mockResolvedValue({
      ...buildDashboardPayload(),
    });

    renderAdminDashboard();

    expect(await screen.findByRole("button", { name: /organizations/i })).toBeTruthy();
    expect(screen.getByRole("button", { name: /organization admins/i })).toBeTruthy();
    expect(screen.getByRole("button", { name: /analytics/i })).toBeTruthy();
    expect(screen.getByRole("button", { name: /open runtime/i })).toBeTruthy();
    expect(screen.getByRole("button", { name: /open audit logs/i })).toBeTruthy();
    expect(screen.getByRole("button", { name: /risk signals/i })).toBeTruthy();
  });
});
