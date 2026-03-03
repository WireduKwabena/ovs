// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";

import { downloadJsonFile, toJsonBlob, toJsonString } from "./json";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("json utils", () => {
  it("serializes data to formatted JSON with trailing newline", () => {
    const json = toJsonString({ ok: true, count: 2 });
    expect(json).toBe('{\n  "ok": true,\n  "count": 2\n}\n');
  });

  it("supports custom spacing", () => {
    const json = toJsonString({ a: 1 }, 0);
    expect(json).toBe('{"a":1}\n');
  });

  it("creates JSON blob with expected mime type and payload", async () => {
    const blob = toJsonBlob({ name: "OVS", enabled: true });
    expect(blob.type).toBe("application/json;charset=utf-8;");
    await expect(blob.text()).resolves.toBe('{\n  "name": "OVS",\n  "enabled": true\n}\n');
  });

  it("downloads JSON file via object URL and revokes it", () => {
    const createObjectURL = vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:json-test");
    const revokeObjectURL = vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => {});
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});

    downloadJsonFile({ sample: 1 }, "report.json");

    expect(createObjectURL).toHaveBeenCalledTimes(1);
    expect(clickSpy).toHaveBeenCalledTimes(1);
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:json-test");
  });
});
