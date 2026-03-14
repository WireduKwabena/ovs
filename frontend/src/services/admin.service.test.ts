import { afterEach, describe, expect, it, vi } from "vitest";

const apiGetMock = vi.hoisted(() => vi.fn());
const apiPatchMock = vi.hoisted(() => vi.fn());

vi.mock("./api", () => ({
  default: {
    get: apiGetMock,
    patch: apiPatchMock,
  },
}));

import { adminService } from "./admin.service";

describe("adminService org-scoped API contract", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("attaches the active-organization header when fetching org cases", async () => {
    apiGetMock.mockResolvedValueOnce({
      data: {
        results: [],
        count: 0,
        page: 1,
        page_size: 20,
        total_pages: 0,
      },
    });

    await adminService.getOrgCases("org-123", {
      status: "pending",
      page: 2,
    });

    expect(apiGetMock).toHaveBeenCalledWith("/admin/cases/", {
      params: {
        status: "pending",
        page: 2,
      },
      headers: {
        "X-Active-Organization-ID": "org-123",
      },
    });
  });

  it("attaches the active-organization header when fetching org users", async () => {
    apiGetMock.mockResolvedValueOnce({
      data: {
        results: [],
        count: 0,
        page: 1,
        page_size: 20,
        total_pages: 0,
      },
    });

    await adminService.getOrgUsers("org-987", {
      q: "alice",
      user_type: "internal",
      is_active: true,
    });

    expect(apiGetMock).toHaveBeenCalledWith("/admin/users/", {
      params: {
        q: "alice",
        user_type: "internal",
        is_active: true,
      },
      headers: {
        "X-Active-Organization-ID": "org-987",
      },
    });
  });

  it("attaches the active-organization header when updating an org user", async () => {
    apiPatchMock.mockResolvedValueOnce({
      data: {
        id: "user-1",
        email: "member@example.com",
      },
    });

    await adminService.updateOrgUser("org-555", "user-1", {
      is_active: false,
    });

    expect(apiPatchMock).toHaveBeenCalledWith(
      "/admin/users/user-1/",
      { is_active: false },
      {
        headers: {
          "X-Active-Organization-ID": "org-555",
        },
      },
    );
  });
});
