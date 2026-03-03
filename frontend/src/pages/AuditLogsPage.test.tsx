// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import AuditLogsPage from "./AuditLogsPage";

const mocks = vi.hoisted(() => ({
  auditService: {
    list: vi.fn(),
    getStatistics: vi.fn(),
    getRecentActivity: vi.fn(),
    getById: vi.fn(),
  },
  downloadCsvFile: vi.fn(),
  downloadJsonFile: vi.fn(),
  toastInfo: vi.fn(),
  toastSuccess: vi.fn(),
  toastError: vi.fn(),
}));

vi.mock("@/services/audit.service", () => ({
  auditService: mocks.auditService,
}));

vi.mock("@/utils/csv", () => ({
  downloadCsvFile: mocks.downloadCsvFile,
  isoDateStamp: () => "2026-03-03",
}));

vi.mock("@/utils/json", () => ({
  downloadJsonFile: mocks.downloadJsonFile,
}));

vi.mock("react-toastify", () => ({
  toast: {
    info: mocks.toastInfo,
    success: mocks.toastSuccess,
    error: mocks.toastError,
  },
}));

describe("AuditLogsPage export actions", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("exports CSV and JSON when rows are available", async () => {
    mocks.auditService.list.mockResolvedValue([
      {
        id: "log-1",
        action: "create",
        action_display: "Create",
        entity_type: "VettingCase",
        entity_id: "case-123",
        changes: { status: ["pending", "approved"] },
        admin_user_name: "System Admin",
        created_at: "2026-03-03T01:00:00.000Z",
      },
    ]);
    mocks.auditService.getStatistics.mockResolvedValue({
      total_logs: 1,
      action_distribution: [{ action: "create", count: 1 }],
      entity_distribution: [{ entity_type: "VettingCase", count: 1 }],
    });
    mocks.auditService.getRecentActivity.mockResolvedValue([]);

    render(
      <MemoryRouter>
        <AuditLogsPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(mocks.auditService.list).toHaveBeenCalledTimes(1);
    });

    const exportCsvButton = await screen.findByRole("button", { name: /export csv/i });
    const exportJsonButton = await screen.findByRole("button", { name: /export json/i });

    fireEvent.click(exportCsvButton);
    fireEvent.click(exportJsonButton);

    expect(mocks.downloadCsvFile).toHaveBeenCalledTimes(1);
    expect(mocks.downloadCsvFile.mock.calls[0][2]).toBe("audit-logs-2026-03-03.csv");
    expect(mocks.downloadJsonFile).toHaveBeenCalledTimes(1);
    expect(mocks.downloadJsonFile.mock.calls[0][1]).toBe("audit-logs-2026-03-03.json");
  });

  it("does not export when there are no rows", async () => {
    mocks.auditService.list.mockResolvedValue([]);
    mocks.auditService.getStatistics.mockResolvedValue({
      total_logs: 0,
      action_distribution: [],
      entity_distribution: [],
    });
    mocks.auditService.getRecentActivity.mockResolvedValue([]);

    render(
      <MemoryRouter>
        <AuditLogsPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(mocks.auditService.list).toHaveBeenCalledTimes(1);
    });

    const exportCsvButton = await screen.findByRole("button", { name: /export csv/i });
    const exportJsonButton = await screen.findByRole("button", { name: /export json/i });

    expect((exportCsvButton as HTMLButtonElement).disabled).toBe(true);
    expect((exportJsonButton as HTMLButtonElement).disabled).toBe(true);
    expect(mocks.downloadCsvFile).not.toHaveBeenCalled();
    expect(mocks.downloadJsonFile).not.toHaveBeenCalled();
  });
});
