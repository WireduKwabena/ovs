import { afterEach, describe, expect, it, vi } from "vitest";

const apiGetMock = vi.hoisted(() => vi.fn());

vi.mock("./api", () => ({
  default: {
    get: apiGetMock,
  },
}));

import { candidateService } from "./candidate.service";

describe("candidateService error contract", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("surfaces DRF detail errors instead of generic fallback", async () => {
    apiGetMock.mockRejectedValueOnce({
      response: {
        data: {
          detail: "You cannot create enrollments for another manager's campaign.",
        },
      },
    });

    await expect(candidateService.listCandidates()).rejects.toThrow(
      "You cannot create enrollments for another manager's campaign.",
    );
  });
});
