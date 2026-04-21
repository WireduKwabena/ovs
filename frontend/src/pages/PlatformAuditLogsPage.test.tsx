// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

const mocks = vi.hoisted(() => ({
  list: vi.fn(),
  getEventCatalog: vi.fn(),
  toastError: vi.fn(),
}));

vi.mock("@/services/audit.service", () => ({
  auditService: { list: mocks.list, getEventCatalog: mocks.getEventCatalog },
}));
vi.mock("react-toastify", () => ({ toast: { error: mocks.toastError } }));

const { PlatformAuditLogsPage } =
  await import("./platform-admin/PlatformAuditLogsPage");

describe("PlatformAuditLogsPage", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("fetches audit logs and catalog on mount", async () => {
    mocks.list.mockResolvedValue([]);
    mocks.getEventCatalog.mockResolvedValue([]);
    render(
      <MemoryRouter>
        <PlatformAuditLogsPage />
      </MemoryRouter>,
    );
    await waitFor(() => expect(mocks.list).toHaveBeenCalled());
    await waitFor(() => expect(mocks.getEventCatalog).toHaveBeenCalled());
  });

  it("renders the page heading", async () => {
    mocks.list.mockResolvedValue([]);
    mocks.getEventCatalog.mockResolvedValue([]);
    render(
      <MemoryRouter>
        <PlatformAuditLogsPage />
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(screen.getByText(/platform audit logs/i)).toBeTruthy(),
    );
  });

  it("shows toast on fetch error", async () => {
    mocks.list.mockRejectedValue(new Error("fail"));
    mocks.getEventCatalog.mockRejectedValue(new Error("fail"));
    render(
      <MemoryRouter>
        <PlatformAuditLogsPage />
      </MemoryRouter>,
    );
    await waitFor(() => expect(mocks.toastError).toHaveBeenCalled());
  });
});
