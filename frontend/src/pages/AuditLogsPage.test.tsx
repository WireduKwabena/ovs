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
    getByUser: vi.fn(),
    getById: vi.fn(),
    getEventCatalog: vi.fn(),
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
    mocks.auditService.getEventCatalog.mockResolvedValue([
      {
        key: "government_position_updated",
        entity_type: "GovernmentPosition",
        action: "update",
        description: "Government position updated.",
      },
    ]);
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
    mocks.auditService.getEventCatalog.mockResolvedValue([]);
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

  it("applies government entity type filter and refreshes rows", async () => {
    mocks.auditService.getEventCatalog.mockResolvedValue([
      {
        key: "government_position_updated",
        entity_type: "GovernmentPosition",
        action: "update",
        description: "Government position updated.",
      },
      {
        key: "personnel_record_deleted",
        entity_type: "PersonnelRecord",
        action: "delete",
        description: "Personnel record deleted.",
      },
      {
        key: "appointment_record_created",
        entity_type: "AppointmentRecord",
        action: "create",
        description: "Appointment record created.",
      },
    ]);
    mocks.auditService.list.mockImplementation(async (params?: { entity_type?: string }) => {
      const entityType = params?.entity_type;
      if (!entityType) {
        return [
          {
            id: "log-default",
            action: "create",
            action_display: "Create",
            entity_type: "VettingCase",
            entity_id: "case-001",
            changes: {},
            admin_user_name: "System Admin",
            created_at: "2026-03-03T01:00:00.000Z",
          },
        ];
      }

      const entityId =
        entityType === "GovernmentPosition"
          ? "POS-1"
          : entityType === "PersonnelRecord"
            ? "PER-1"
            : "APP-1";

      return [
        {
          id: `log-${entityType}`,
          action: "update",
          action_display: "Update",
          entity_type: entityType,
          entity_id: entityId,
          changes: { event: "filtered" },
          admin_user_name: "System Admin",
          created_at: "2026-03-03T01:00:00.000Z",
        },
      ];
    });
    mocks.auditService.getStatistics.mockResolvedValue({
      total_logs: 3,
      action_distribution: [{ action: "update", count: 3 }],
      entity_distribution: [
        { entity_type: "GovernmentPosition", count: 1 },
        { entity_type: "PersonnelRecord", count: 1 },
        { entity_type: "AppointmentRecord", count: 1 },
      ],
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

    const entityTypeInput = await screen.findByLabelText(/entity type/i);

    fireEvent.change(entityTypeInput, { target: { value: "GovernmentPosition" } });
    await waitFor(() => {
      expect(mocks.auditService.list).toHaveBeenLastCalledWith(
        expect.objectContaining({ entity_type: "GovernmentPosition" }),
      );
    });
    expect(await screen.findByText(/GovernmentPosition #POS-1/i)).toBeTruthy();

    fireEvent.change(entityTypeInput, { target: { value: "PersonnelRecord" } });
    await waitFor(() => {
      expect(mocks.auditService.list).toHaveBeenLastCalledWith(
        expect.objectContaining({ entity_type: "PersonnelRecord" }),
      );
    });
    expect(await screen.findByText(/PersonnelRecord #PER-1/i)).toBeTruthy();

    fireEvent.change(entityTypeInput, { target: { value: "AppointmentRecord" } });
    await waitFor(() => {
      expect(mocks.auditService.list).toHaveBeenLastCalledWith(
        expect.objectContaining({ entity_type: "AppointmentRecord" }),
      );
    });
    expect(await screen.findByText(/AppointmentRecord #APP-1/i)).toBeTruthy();
  });

  it("applies event key filter from backend catalog", async () => {
    mocks.auditService.getEventCatalog.mockResolvedValue([
      {
        key: "personnel_record_deleted",
        entity_type: "PersonnelRecord",
        action: "delete",
        description: "Personnel record deleted.",
      },
    ]);
    mocks.auditService.list.mockResolvedValue([
      {
        id: "log-personnel-record-deleted",
        action: "delete",
        action_display: "Delete",
        entity_type: "PersonnelRecord",
        entity_id: "PER-1",
        changes: { event: "personnel_record_deleted" },
        admin_user_name: "System Admin",
        created_at: "2026-03-03T01:00:00.000Z",
      },
    ]);
    mocks.auditService.getStatistics.mockResolvedValue({
      total_logs: 1,
      action_distribution: [{ action: "delete", count: 1 }],
      entity_distribution: [{ entity_type: "PersonnelRecord", count: 1 }],
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

    const eventKeyInput = await screen.findByLabelText(/event key/i);
    fireEvent.change(eventKeyInput, { target: { value: "personnel_record_deleted" } });

    await waitFor(() => {
      expect(mocks.auditService.list).toHaveBeenLastCalledWith(
        expect.objectContaining({ changes__event: "personnel_record_deleted" }),
      );
    });

    expect(await screen.findByText(/active filters/i)).toBeTruthy();
    fireEvent.click(await screen.findByRole("button", { name: /clear key filters/i }));

    await waitFor(() => {
      expect(mocks.auditService.list).toHaveBeenLastCalledWith(
        expect.objectContaining({ changes__event: undefined }),
      );
    });
    const eventKeyInputAfterClear = await screen.findByLabelText(/event key/i);
    expect((eventKeyInputAfterClear as HTMLInputElement).value).toBe("");
  });

  it("filters by actor using by_user endpoint when row action is clicked", async () => {
    mocks.auditService.getEventCatalog.mockResolvedValue([]);
    mocks.auditService.list.mockResolvedValue([
      {
        id: "log-with-actor",
        action: "update",
        action_display: "Update",
        entity_type: "AppointmentRecord",
        entity_id: "APP-100",
        user: "actor-uuid-1",
        user_name: "Actor One",
        changes: { event: "appointment_record_updated" },
        created_at: "2026-03-03T01:00:00.000Z",
      },
    ]);
    mocks.auditService.getByUser.mockResolvedValue([
      {
        id: "log-actor-result",
        action: "create",
        action_display: "Create",
        entity_type: "AppointmentRecord",
        entity_id: "APP-101",
        user: "actor-uuid-1",
        user_name: "Actor One",
        changes: { event: "appointment_record_created" },
        created_at: "2026-03-03T02:00:00.000Z",
      },
    ]);
    mocks.auditService.getStatistics.mockResolvedValue({
      total_logs: 1,
      action_distribution: [{ action: "update", count: 1 }],
      entity_distribution: [{ entity_type: "AppointmentRecord", count: 1 }],
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

    fireEvent.click(await screen.findByRole("button", { name: /filter actor/i }));

    await waitFor(() => {
      expect(mocks.auditService.getByUser).toHaveBeenCalledWith("actor-uuid-1");
    });
    expect(await screen.findByText(/AppointmentRecord #APP-101/i)).toBeTruthy();
    expect(await screen.findByText(/Actor filter active:/i)).toBeTruthy();

    fireEvent.click(await screen.findByRole("button", { name: /clear actor filter/i }));

    await waitFor(() => {
      expect(mocks.auditService.list).toHaveBeenCalledTimes(2);
    });
    const actorInput = await screen.findByLabelText(/actor user id/i);
    expect((actorInput as HTMLInputElement).value).toBe("");
  });

  it("hydrates filters from URL query and applies them to list request", async () => {
    mocks.auditService.getEventCatalog.mockResolvedValue([]);
    mocks.auditService.list.mockResolvedValue([
      {
        id: "log-url-hydrated",
        action: "update",
        action_display: "Update",
        entity_type: "PersonnelRecord",
        entity_id: "PER-100",
        changes: { event: "personnel_record_updated" },
        admin_user_name: "System Admin",
        created_at: "2026-03-03T01:00:00.000Z",
      },
    ]);
    mocks.auditService.getStatistics.mockResolvedValue({
      total_logs: 1,
      action_distribution: [{ action: "update", count: 1 }],
      entity_distribution: [{ entity_type: "PersonnelRecord", count: 1 }],
    });
    mocks.auditService.getRecentActivity.mockResolvedValue([]);

    render(
      <MemoryRouter
        initialEntries={[
          "/audit-logs?action=update&entity_type=PersonnelRecord&event_key=personnel_record_updated&entity_id=PER-100&search=personnel",
        ]}
      >
        <AuditLogsPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(mocks.auditService.list).toHaveBeenLastCalledWith(
        expect.objectContaining({
          action: "update",
          entity_type: "PersonnelRecord",
          changes__event: "personnel_record_updated",
          entity_id: "PER-100",
          search: "personnel",
        }),
      );
    });

    const entityTypeInput = await screen.findByLabelText(/entity type/i);
    const eventKeyInput = await screen.findByLabelText(/event key/i);
    const entityIdInput = await screen.findByLabelText(/entity id/i);
    const searchInput = await screen.findByLabelText(/search/i);

    expect((entityTypeInput as HTMLInputElement).value).toBe("PersonnelRecord");
    expect((eventKeyInput as HTMLInputElement).value).toBe("personnel_record_updated");
    expect((entityIdInput as HTMLInputElement).value).toBe("PER-100");
    expect((searchInput as HTMLInputElement).value).toBe("personnel");
  });
});
