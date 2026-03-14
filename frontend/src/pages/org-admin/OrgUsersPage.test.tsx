// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import OrgUsersPage from "./OrgUsersPage";

const mocks = vi.hoisted(() => ({
  adminService: {
    getOrgUsers: vi.fn(),
    updateOrgUser: vi.fn(),
  },
}));

vi.mock("@/services/admin.service", () => ({
  adminService: mocks.adminService,
}));

vi.mock("react-toastify", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

describe("OrgUsersPage filters", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("hydrates URL filters and clears active user filters", async () => {
    mocks.adminService.getOrgUsers.mockResolvedValue({
      results: [
        {
          id: "user-1",
          email: "alice@example.com",
          first_name: "Alice",
          last_name: "Admin",
          full_name: "Alice Admin",
          user_type: "internal",
          is_active: true,
          is_staff: false,
          is_superuser: false,
          is_two_factor_enabled: true,
          last_login: null,
          created_at: "2026-03-01T10:00:00Z",
          updated_at: "2026-03-01T10:00:00Z",
        },
      ],
      count: 1,
      page: 1,
      page_size: 20,
      total_pages: 1,
      ordering: "-created_at",
    });

    render(
      <MemoryRouter initialEntries={["/admin/org/org-1/users?q=alice&user_type=internal&is_active=true"]}>
        <Routes>
          <Route path="/admin/org/:orgId/users" element={<OrgUsersPage />} />
        </Routes>
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(mocks.adminService.getOrgUsers).toHaveBeenCalledWith(
        "org-1",
        expect.objectContaining({
          q: "alice",
          user_type: "internal",
          is_active: true,
        }),
      );
    });

    expect(await screen.findByText(/active filters/i)).toBeTruthy();
    expect(await screen.findByRole("button", { name: /clear user filters/i })).toBeTruthy();

    fireEvent.click(await screen.findByRole("button", { name: /clear user filters/i }));

    await waitFor(() => {
      expect(mocks.adminService.getOrgUsers).toHaveBeenLastCalledWith(
        "org-1",
        expect.objectContaining({
          q: undefined,
          user_type: undefined,
          is_active: undefined,
        }),
      );
    });

    const searchInput = await screen.findByLabelText(/search/i);
    expect((searchInput as HTMLInputElement).value).toBe("");

    await waitFor(() => {
      expect(screen.queryByText(/active filters/i)).toBeNull();
    });
  }, 10000);
});

