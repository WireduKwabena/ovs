// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";

import { downloadCsvFile, isoDateStamp, toCsvBlob, toCsvString } from "./csv";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("csv utils", () => {
  it("serializes header and rows with CSV escaping", () => {
    const csv = toCsvString(
      ["name", "note", "score", "active"],
      [
        ['Jane "JJ"', "Line 1\nLine 2", 98.5, true],
        ["Doe, John", "", null, false],
      ],
    );

    expect(csv).toBe(
      [
        '"name","note","score","active"',
        '"Jane ""JJ""","Line 1\nLine 2","98.5","true"',
        '"Doe, John","","","false"',
      ].join("\n"),
    );
  });

  it("formats Date cells as ISO strings", () => {
    const date = new Date("2026-03-03T10:20:30.000Z");
    const csv = toCsvString(["created_at"], [[date]]);
    expect(csv).toBe(`"created_at"\n"${date.toISOString()}"`);
  });

  it("creates a CSV blob with expected mime type and content", async () => {
    const blob = toCsvBlob(["id", "value"], [[1, "ok"]]);
    expect(blob.type).toBe("text/csv;charset=utf-8;");
    await expect(blob.text()).resolves.toBe('"id","value"\n"1","ok"');
  });

  it("downloads csv files via object URL and revokes url", () => {
    const createObjectURL = vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:csv-test");
    const revokeObjectURL = vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => {});
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});

    downloadCsvFile(["x"], [[123]], "report.csv");

    expect(createObjectURL).toHaveBeenCalledTimes(1);
    expect(clickSpy).toHaveBeenCalledTimes(1);
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:csv-test");
  });

  it("returns YYYY-MM-DD for date stamps", () => {
    expect(isoDateStamp(new Date("2026-03-03T18:44:01.000Z"))).toBe("2026-03-03");
  });
});
