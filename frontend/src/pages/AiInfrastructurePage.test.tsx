// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

const mocks = vi.hoisted(() => ({
  health: vi.fn(),
  toastError: vi.fn(),
}));

vi.mock("@/services/aiMonitor.service", () => ({
  aiMonitorService: { health: mocks.health },
}));
vi.mock("react-toastify", () => ({ toast: { error: mocks.toastError } }));

const { AiInfrastructurePage } =
  await import("./platform-admin/AiInfrastructurePage");

describe("AiInfrastructurePage", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("calls aiMonitorService.health on mount", async () => {
    mocks.health.mockResolvedValue({ monitor: { enabled: true } });
    render(
      <MemoryRouter>
        <AiInfrastructurePage />
      </MemoryRouter>,
    );
    await waitFor(() => expect(mocks.health).toHaveBeenCalled());
  });

  it("renders the AI Infrastructure heading", async () => {
    mocks.health.mockResolvedValue({ monitor: { enabled: true } });
    render(
      <MemoryRouter>
        <AiInfrastructurePage />
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(screen.getByText(/ai infrastructure/i)).toBeTruthy(),
    );
  });

  it("shows toast when health fetch fails", async () => {
    mocks.health.mockRejectedValue(new Error("timeout"));
    render(
      <MemoryRouter>
        <AiInfrastructurePage />
      </MemoryRouter>,
    );
    await waitFor(() => expect(mocks.toastError).toHaveBeenCalled());
  });
});
