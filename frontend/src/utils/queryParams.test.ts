import { describe, expect, it } from "vitest";

import { applyQueryUpdates, normalizeQueryValue } from "./queryParams";

describe("queryParams utils", () => {
  it("normalizes nullable query values", () => {
    expect(normalizeQueryValue(null)).toBe("");
    expect(normalizeQueryValue("  hello  ")).toBe("hello");
  });

  it("applies updates, removes empty/all values, and resets page by default", () => {
    const current = new URLSearchParams("page=3&q=alice&status=pending");
    const next = applyQueryUpdates(
      current,
      {
        q: "",
        status: "all",
        priority: "high",
      },
      { keepPage: false },
    );

    expect(next.get("q")).toBeNull();
    expect(next.get("status")).toBeNull();
    expect(next.get("priority")).toBe("high");
    expect(next.get("page")).toBe("1");
  });

  it("keeps page when requested", () => {
    const current = new URLSearchParams("page=5&user_type=admin");
    const next = applyQueryUpdates(
      current,
      { user_type: null },
      { keepPage: true },
    );

    expect(next.get("user_type")).toBeNull();
    expect(next.get("page")).toBe("5");
  });
});
