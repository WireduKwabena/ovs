// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

const mocks = vi.hoisted(() => ({
  getReminderHealth: vi.fn(),
  toastError: vi.fn(),
}));

vi.mock("@/services/videoCall.service", () => ({
  videoCallService: { getReminderHealth: mocks.getReminderHealth },
}));
vi.mock("react-toastify", () => ({ toast: { error: mocks.toastError } }));

const { SystemHealthPage } = await import("./platform-admin/SystemHealthPage");

describe("SystemHealthPage", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("calls getReminderHealth on mount", async () => {
    mocks.getReminderHealth.mockResolvedValue({ status: "healthy" });
    render(
      <MemoryRouter>
        <SystemHealthPage />
      </MemoryRouter>,
    );
    await waitFor(() => expect(mocks.getReminderHealth).toHaveBeenCalled());
  });

  it("renders System Health heading", async () => {
    mocks.getReminderHealth.mockResolvedValue({ status: "healthy" });
    render(
      <MemoryRouter>
        <SystemHealthPage />
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(screen.getByText(/system health/i)).toBeTruthy(),
    );
  });

  it("shows toast on fetch error", async () => {
    mocks.getReminderHealth.mockRejectedValue(new Error("error"));
    render(
      <MemoryRouter>
        <SystemHealthPage />
      </MemoryRouter>,
    );
    await waitFor(() => expect(mocks.toastError).toHaveBeenCalled());
  });
});
