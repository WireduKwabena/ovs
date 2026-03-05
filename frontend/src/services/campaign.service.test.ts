import { afterEach, describe, expect, it, vi } from "vitest";

const apiPostMock = vi.hoisted(() => vi.fn());

vi.mock("./api", () => ({
  default: {
    post: apiPostMock,
  },
}));

import { campaignService } from "./campaign.service";

describe("campaignService.importCandidates API contract", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("preserves DRF detail/code/quota fields on quota errors", async () => {
    const drfErrorPayload = {
      detail: "Monthly candidate import quota exceeded.",
      code: "quota_exceeded",
      quota: {
        plan: "starter",
        period_start: "2026-03-01T00:00:00Z",
        period_end: "2026-03-31T23:59:59Z",
        limit: 50,
        used: 50,
        remaining: 0,
      },
    };

    const drfError = {
      isAxiosError: true,
      message: "Request failed with status code 400",
      response: {
        status: 400,
        data: drfErrorPayload,
      },
    };

    apiPostMock.mockRejectedValueOnce(drfError);

    const requestPayload = {
      candidates: [{ first_name: "Ada", email: "ada@example.com" }],
      send_invites: true,
    };

    let rejected: unknown;
    try {
      await campaignService.importCandidates("campaign-uuid-123", requestPayload);
    } catch (error: unknown) {
      rejected = error;
    }

    expect(apiPostMock).toHaveBeenCalledWith(
      "/campaigns/campaign-uuid-123/candidates/import/",
      requestPayload,
    );
    expect(rejected).toBe(drfError);
    const rejectedAxiosError = rejected as typeof drfError;
    expect(rejectedAxiosError.response.data).toEqual(drfErrorPayload);
    expect(rejectedAxiosError.response.data).toMatchObject({
      detail: "Monthly candidate import quota exceeded.",
      code: "quota_exceeded",
      quota: {
        limit: 50,
        used: 50,
        remaining: 0,
      },
    });
  });
});
