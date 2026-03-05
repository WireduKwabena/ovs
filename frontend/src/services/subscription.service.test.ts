import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  publicGet: vi.fn(),
  publicPost: vi.fn(),
  apiPost: vi.fn(),
}));

vi.mock("axios", () => ({
  default: {
    create: () => ({
      get: mocks.publicGet,
      post: mocks.publicPost,
    }),
  },
}));

vi.mock("./api", () => ({
  default: {
    post: mocks.apiPost,
  },
}));

describe("subscriptionService exchange-rate contract", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("calls backend exchange-rate endpoint and returns payload", async () => {
    mocks.publicGet.mockResolvedValue({
      data: {
        status: "ok",
        base: "USD",
        target: "GHS",
        rate: 19.5,
        source: "api_cache",
      },
    });

    const { subscriptionService } = await import("./subscription.service");
    const result = await subscriptionService.getPaystackExchangeRate();

    expect(mocks.publicGet).toHaveBeenCalledWith("/billing/exchange-rate/");
    expect(result).toEqual({
      status: "ok",
      base: "USD",
      target: "GHS",
      rate: 19.5,
      source: "api_cache",
    });
  });
});

