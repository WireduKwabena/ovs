// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import AiMonitorPage from "./AiMonitorPage";

const mocks = vi.hoisted(() => ({
  health: vi.fn(),
  classifyDocument: vi.fn(),
  checkSocialProfiles: vi.fn(),
  toastSuccess: vi.fn(),
  toastError: vi.fn(),
}));

vi.mock("@/services/aiMonitor.service", () => ({
  aiMonitorService: {
    health: mocks.health,
    classifyDocument: mocks.classifyDocument,
    checkSocialProfiles: mocks.checkSocialProfiles,
  },
}));

vi.mock("react-toastify", () => ({
  toast: {
    success: mocks.toastSuccess,
    error: mocks.toastError,
  },
}));

describe("AiMonitorPage processing-error trace links", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("shows processing error notification link when model health fails", async () => {
    mocks.health.mockRejectedValue(new Error("Runtime backend unavailable"));
    mocks.classifyDocument.mockResolvedValue({});
    mocks.checkSocialProfiles.mockResolvedValue({});

    render(
      <MemoryRouter>
        <AiMonitorPage />
      </MemoryRouter>,
    );

    expect(await screen.findByText("Runtime backend unavailable")).toBeTruthy();
    const traceLink = screen.getByRole("link", {
      name: /open processing errors/i,
    });
    expect(traceLink.getAttribute("href")).toBe(
      "/notifications?channel=all&event_type=processing_error",
    );
  });

  it("shows processing error notification link when document classification fails", async () => {
    mocks.health.mockResolvedValue({
      model_name: "default",
      status: "ok",
      timestamp: "2026-03-14T00:00:00Z",
      monitor: {
        enabled: true,
        backend: "memory",
        redis_configured: false,
        use_redis: false,
      },
    });
    mocks.classifyDocument.mockRejectedValue(new Error("Classifier pipeline unavailable"));
    mocks.checkSocialProfiles.mockResolvedValue({});

    render(
      <MemoryRouter>
        <AiMonitorPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(mocks.health).toHaveBeenCalledTimes(1);
    });

    const fileInput = screen.getByLabelText(/file/i) as HTMLInputElement;
    const testFile = new File(["test"], "sample.png", { type: "image/png" });
    fireEvent.change(fileInput, { target: { files: [testFile] } });
    fireEvent.click(screen.getByRole("button", { name: /classify document/i }));

    expect(await screen.findByText("Classifier pipeline unavailable")).toBeTruthy();
    const traceLinks = screen.getAllByRole("link", {
      name: /open processing errors/i,
    });
    expect(
      traceLinks.some(
        (link) =>
          link.getAttribute("href") ===
          "/notifications?channel=all&event_type=processing_error",
      ),
    ).toBe(true);
  });

  it("shows processing error notification link when social profile check fails", async () => {
    mocks.health.mockResolvedValue({
      model_name: "default",
      status: "ok",
      timestamp: "2026-03-14T00:00:00Z",
      monitor: {
        enabled: true,
        backend: "memory",
        redis_configured: false,
        use_redis: false,
      },
    });
    mocks.classifyDocument.mockResolvedValue({});
    mocks.checkSocialProfiles.mockRejectedValue(new Error("Social verification backend unavailable"));

    render(
      <MemoryRouter>
        <AiMonitorPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(mocks.health).toHaveBeenCalledTimes(1);
    });

    fireEvent.change(screen.getAllByPlaceholderText("url")[0], {
      target: { value: "https://linkedin.com/in/test-user" },
    });
    fireEvent.click(screen.getByRole("button", { name: /run social check/i }));

    expect(await screen.findByText("Social verification backend unavailable")).toBeTruthy();
    const traceLinks = screen.getAllByRole("link", {
      name: /open processing errors/i,
    });
    expect(
      traceLinks.some(
        (link) =>
          link.getAttribute("href") ===
          "/notifications?channel=all&event_type=processing_error",
      ),
    ).toBe(true);
  });
});
