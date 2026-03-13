// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import AdminUsersPage from "./AdminUsersPage";

const mocks = vi.hoisted(() => ({
  adminService: {
    getUsers: vi.fn(),
    updateUser: vi.fn(),
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

describe("AdminUsersPage filters", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("hydrates URL filters and clears active user filters", async () => {
    mocks.adminService.getUsers.mockResolvedValue({
      results: [
        {
          id: "user-1",
          email: "alice@example.com",
          first_name: "Alice",
          last_name: "Admin",
          full_name: "Alice Admin",
          user_type: "internal",
          group_roles: ["registry_admin"],
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
      <MemoryRouter initialEntries={["/admin/users?q=alice&user_type=internal&is_active=true"]}>
        <AdminUsersPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(mocks.adminService.getUsers).toHaveBeenCalledWith(
        expect.objectContaining({
          q: "alice",
          is_active: true,
        }),
      );
    });

    expect(await screen.findByText(/active filters/i)).toBeTruthy();
    expect(await screen.findByRole("button", { name: /clear user filters/i })).toBeTruthy();

    fireEvent.click(await screen.findByRole("button", { name: /clear user filters/i }));

    await waitFor(() => {
      expect(mocks.adminService.getUsers).toHaveBeenLastCalledWith(
        expect.objectContaining({
          q: undefined,
          is_active: undefined,
        }),
      );
    });

    const searchInput = await screen.findByLabelText(/search/i);
    expect((searchInput as HTMLInputElement).value).toBe("");

    await waitFor(() => {
      expect(screen.queryByText(/active filters/i)).toBeNull();
    });
  });
});

