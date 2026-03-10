import { afterEach, describe, expect, it, vi } from "vitest";

const apiGetMock = vi.hoisted(() => vi.fn());

vi.mock("./api", () => ({
  default: {
    get: apiGetMock,
  },
}));

import { auditService } from "./audit.service";

describe("auditService.list API contract", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("normalizes paginated payloads to results array", async () => {
    apiGetMock.mockResolvedValueOnce({
      data: {
        count: 2,
        results: [
          { id: "log-1", action: "create", entity_type: "GovernmentPosition" },
          { id: "log-2", action: "update", entity_type: "PersonnelRecord" },
        ],
      },
    });

    const rows = await auditService.list({ entity_type: "GovernmentPosition" });

    expect(apiGetMock).toHaveBeenCalledWith("/audit/logs/", {
      params: { entity_type: "GovernmentPosition" },
    });
    expect(rows).toHaveLength(2);
    expect(rows[0]).toMatchObject({ id: "log-1" });
    expect(rows[1]).toMatchObject({ id: "log-2" });
  });

  it("returns raw array payloads as-is", async () => {
    apiGetMock.mockResolvedValueOnce({
      data: [{ id: "log-3", action: "delete", entity_type: "AppointmentRecord" }],
    });

    const rows = await auditService.list({ action: "delete" });

    expect(apiGetMock).toHaveBeenCalledWith("/audit/logs/", {
      params: { action: "delete" },
    });
    expect(rows).toEqual([{ id: "log-3", action: "delete", entity_type: "AppointmentRecord" }]);
  });

  it("returns empty list when payload has no results array", async () => {
    apiGetMock.mockResolvedValueOnce({
      data: { count: 1, results: null },
    });

    const rows = await auditService.list();

    expect(rows).toEqual([]);
  });

  it("surfaces backend error message when list fails", async () => {
    apiGetMock.mockRejectedValueOnce({
      response: { data: { message: "Audit service unavailable" } },
    });

    await expect(auditService.list()).rejects.toThrow("Audit service unavailable");
  });
});

describe("auditService.getEventCatalog API contract", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("normalizes paginated catalog payloads to results array", async () => {
    apiGetMock.mockResolvedValueOnce({
      data: {
        count: 1,
        results: [
          {
            key: "appointment_record_created",
            entity_type: "AppointmentRecord",
            action: "create",
            description: "Appointment record created.",
          },
        ],
      },
    });

    const catalog = await auditService.getEventCatalog();

    expect(apiGetMock).toHaveBeenCalledWith("/audit/logs/event-catalog/");
    expect(catalog).toHaveLength(1);
    expect(catalog[0]).toMatchObject({ key: "appointment_record_created" });
  });

  it("surfaces backend error message when catalog fetch fails", async () => {
    apiGetMock.mockRejectedValueOnce({
      response: { data: { message: "Catalog unavailable" } },
    });

    await expect(auditService.getEventCatalog()).rejects.toThrow("Catalog unavailable");
  });
});

describe("auditService.getByUser API contract", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("returns actor-specific logs array", async () => {
    apiGetMock.mockResolvedValueOnce({
      data: [{ id: "log-user-1", action: "update", entity_type: "AppointmentRecord" }],
    });

    const rows = await auditService.getByUser("actor-uuid-1");

    expect(apiGetMock).toHaveBeenCalledWith("/audit/logs/by-user/", {
      params: { user_id: "actor-uuid-1" },
    });
    expect(rows).toEqual([{ id: "log-user-1", action: "update", entity_type: "AppointmentRecord" }]);
  });

  it("surfaces backend error message when by-user fetch fails", async () => {
    apiGetMock.mockRejectedValueOnce({
      response: { data: { message: "Actor filter unavailable" } },
    });

    await expect(auditService.getByUser("actor-uuid-1")).rejects.toThrow("Actor filter unavailable");
  });
});

describe("auditService action route compatibility", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("uses hyphenated by-entity action route", async () => {
    apiGetMock.mockResolvedValueOnce({ data: [] });

    await auditService.getByEntity("AppointmentRecord", "app-1");

    expect(apiGetMock).toHaveBeenCalledWith("/audit/logs/by-entity/", {
      params: { entity_type: "AppointmentRecord", entity_id: "app-1" },
    });
  });

  it("uses hyphenated recent-activity action route", async () => {
    apiGetMock.mockResolvedValueOnce({ data: [] });

    await auditService.getRecentActivity();

    expect(apiGetMock).toHaveBeenCalledWith("/audit/logs/recent-activity/");
  });
});
