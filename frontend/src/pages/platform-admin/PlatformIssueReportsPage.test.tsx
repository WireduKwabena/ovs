// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { configureStore } from "@reduxjs/toolkit";
import { Provider } from "react-redux";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { cleanup, render, screen, waitFor } from "@testing-library/react";

import PlatformIssueReportsPage from "./PlatformIssueReportsPage";

const mocks = vi.hoisted(() => ({
  listIssues: vi.fn(),
  reportIssue: vi.fn(),
  updateIssue: vi.fn(),
}));

vi.mock("@/services/admin.service", () => ({
  adminService: {
    listIssues: mocks.listIssues,
    reportIssue: mocks.reportIssue,
    updateIssue: mocks.updateIssue,
  },
}));

const renderPage = (
  route = "/admin/platform/issues",
  userOverrides?: Record<string, unknown>,
) => {
  const preloadedState = {
    auth: {
      user: {
        id: "user-1",
        email: "user@example.com",
        user_type: "internal",
        is_superuser: false,
        is_staff: false,
        ...userOverrides,
      },
    },
  };

  const store = configureStore({
    reducer: (state = preloadedState) => state,
    preloadedState,
  });

  return render(
    <Provider store={store}>
      <MemoryRouter initialEntries={[route]}>
        <Routes>
          <Route
            path="/admin/platform/issues"
            element={<PlatformIssueReportsPage />}
          />
        </Routes>
      </MemoryRouter>
    </Provider>,
  );
};

describe("PlatformIssueReportsPage", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("shows only the issue report experience for non-superusers", async () => {
    renderPage();

    expect(
      screen.getByRole("heading", { name: /issue reports/i }),
    ).toBeTruthy();
    expect(screen.getByRole("button", { name: /issues report/i })).toBeTruthy();
    expect(
      screen.getByRole("heading", { name: /report new issue/i }),
    ).toBeTruthy();
    expect(
      screen.queryByRole("button", { name: /view submitted issues/i }),
    ).toBeNull();
    expect(screen.queryByText(/submitted issues \(admin view\)/i)).toBeNull();
    expect(mocks.listIssues).not.toHaveBeenCalled();
  });

  it("shows only the submitted-issues admin view for superusers", async () => {
    mocks.listIssues.mockResolvedValue({
      results: [
        {
          id: "issue-1",
          title: "Broken filter",
          description: "Filtering crashes on apply.",
          reporter_email: "reporter@example.com",
          severity: "high",
          status: "open",
          created_at: "2026-05-01T10:00:00Z",
        },
      ],
    });

    renderPage("/admin/platform/issues?tab=submitted", {
      email: "root@example.com",
      is_superuser: true,
      is_staff: true,
      user_type: "platform_admin",
    });

    await waitFor(() => {
      expect(mocks.listIssues).toHaveBeenCalledTimes(1);
    });

    expect(
      screen.getByRole("heading", { name: /view submitted issues/i }),
    ).toBeTruthy();
    expect(
      screen.getByRole("button", { name: /view submitted issues/i }),
    ).toBeTruthy();
    expect(screen.getByText(/submitted issues \(admin view\)/i)).toBeTruthy();
    expect(
      screen.queryByRole("heading", { name: /report new issue/i }),
    ).toBeNull();
    expect(screen.queryByRole("button", { name: /issues report/i })).toBeNull();
    expect(screen.getByText(/broken filter/i)).toBeTruthy();
  });
});
