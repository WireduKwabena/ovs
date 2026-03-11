import { afterEach, describe, expect, it, vi } from "vitest";

const apiGetMock = vi.hoisted(() => vi.fn());
const apiPostMock = vi.hoisted(() => vi.fn());

vi.mock("./api", () => ({
  default: {
    get: apiGetMock,
    post: apiPostMock,
  },
}));

import { authService } from "./auth.service";

describe("authService organization-context endpoints", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("requests profile with active organization query context", async () => {
    apiGetMock.mockResolvedValueOnce({
      data: {
        user: { id: "1", email: "ops@example.com" },
        user_type: "internal",
        organizations: [],
      },
    });

    await authService.getProfile({ activeOrganizationId: "org-123" });

    expect(apiGetMock).toHaveBeenCalledWith("/auth/profile/", {
      params: { active_organization_id: "org-123" },
    });
  });

  it("requests profile without organization query params when none are provided", async () => {
    apiGetMock.mockResolvedValueOnce({
      data: {
        user: { id: "1", email: "ops@example.com" },
        user_type: "internal",
      },
    });

    await authService.getProfile();

    expect(apiGetMock).toHaveBeenCalledWith("/auth/profile/", {
      params: undefined,
    });
  });

  it("posts active organization selection payload", async () => {
    apiPostMock.mockResolvedValueOnce({
      data: {
        message: "Active organization updated.",
        active_organization: {
          id: "org-123",
          code: "ORG123",
          name: "Registry Commission",
          organization_type: "agency",
        },
        active_organization_source: "session",
      },
    });

    await authService.setActiveOrganization({
      organization_id: "org-123",
      clear: false,
    });

    expect(apiPostMock).toHaveBeenCalledWith("/auth/profile/active-organization/", {
      organization_id: "org-123",
      clear: false,
    });
  });
});


