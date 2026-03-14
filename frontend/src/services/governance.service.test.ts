import { afterEach, describe, expect, it, vi } from "vitest";

const apiGetMock = vi.hoisted(() => vi.fn());
const apiPatchMock = vi.hoisted(() => vi.fn());

vi.mock("./api", () => ({
  default: {
    get: apiGetMock,
    patch: apiPatchMock,
  },
}));

import { governanceService } from "./governance.service";

describe("governanceService platform oversight API contract", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("loads platform organization oversight records", async () => {
    apiGetMock.mockResolvedValueOnce({
      data: {
        count: 1,
        results: [
          {
            id: "org-1",
            code: "ORG1",
            name: "Org One",
            organization_type: "agency",
            is_active: true,
            active_member_count: 3,
            subscription: null,
          },
        ],
      },
    });

    const payload = await governanceService.listPlatformOrganizations({
      search: "Org",
      is_active: true,
    });

    expect(apiGetMock).toHaveBeenCalledWith("/governance/platform/organizations/", {
      params: {
        search: "Org",
        is_active: true,
      },
    });
    expect(payload.count).toBe(1);
  });

  it("patches organization active status from the platform oversight endpoint", async () => {
    apiPatchMock.mockResolvedValueOnce({
      data: {
        id: "org-1",
        code: "ORG1",
        name: "Org One",
        organization_type: "agency",
        is_active: false,
        active_member_count: 3,
        subscription: null,
      },
    });

    await governanceService.updatePlatformOrganizationStatus("org-1", {
      is_active: false,
    });

    expect(apiPatchMock).toHaveBeenCalledWith(
      "/governance/platform/organizations/org-1/",
      { is_active: false },
    );
  });
});
