// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import BackgroundChecksPage from "./BackgroundChecksPage";

const mocks = vi.hoisted(() => ({
  toastSuccess: vi.fn(),
  toastError: vi.fn(),
  toastInfo: vi.fn(),
  backgroundCheckService: {
    list: vi.fn(),
    create: vi.fn(),
    refresh: vi.fn(),
    getEvents: vi.fn(),
    retry: vi.fn(),
  },
  applicationService: {
    getAll: vi.fn(),
  },
}));

vi.mock("@/services/backgroundCheck.service", () => ({
  backgroundCheckService: mocks.backgroundCheckService,
}));

vi.mock("@/services/application.service", () => ({
  applicationService: mocks.applicationService,
}));

vi.mock("react-toastify", () => ({
  toast: {
    success: mocks.toastSuccess,
    error: mocks.toastError,
    info: mocks.toastInfo,
  },
}));

const buildCheck = (overrides: Record<string, unknown> = {}) => ({
  id: "bg-check-1",
  case: "1",
  case_id: "CASE-123",
  applicant_email: "candidate@example.com",
  check_type: "criminal",
  provider_key: "mock",
  status: "in_progress",
  external_reference: "ext-1",
  score: 0.5,
  risk_level: "medium",
  recommendation: "review",
  request_payload: {},
  response_payload: {},
  result_summary: {},
  consent_evidence: {},
  submitted_by: null,
  submitted_by_email: "",
  error_code: "",
  error_message: "",
  submitted_at: null,
  last_polled_at: null,
  webhook_received_at: null,
  completed_at: null,
  created_at: "2026-03-05T12:00:00.000Z",
  updated_at: "2026-03-05T12:00:00.000Z",
  refresh_queued: false,
  ...overrides,
});

const buildCase = (overrides: Record<string, unknown> = {}) => ({
  id: "1",
  case_id: "CASE-123",
  status: "pending",
  ...overrides,
});

describe("BackgroundChecksPage filter behavior", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("hydrates from URL filters and clears all active filters", async () => {
    mocks.backgroundCheckService.list.mockResolvedValue([buildCheck()]);
    mocks.applicationService.getAll.mockResolvedValue([buildCase()]);

    render(
      <MemoryRouter
        initialEntries={[
          "/background-checks?case_id=CASE-123&check_type=criminal&status=in_progress",
        ]}
      >
        <BackgroundChecksPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(mocks.backgroundCheckService.list).toHaveBeenCalledWith({
        case_id: "CASE-123",
        check_type: "criminal",
        status: "in_progress",
      });
    });

    expect(await screen.findByText(/active filters/i)).toBeTruthy();
    expect(
      await screen.findByRole("button", { name: /clear check filters/i }),
    ).toBeTruthy();

    fireEvent.click(
      await screen.findByRole("button", { name: /clear check filters/i }),
    );

    await waitFor(() => {
      expect(mocks.backgroundCheckService.list).toHaveBeenLastCalledWith({
        case_id: undefined,
        check_type: "all",
        status: "all",
      });
    });
    await waitFor(() => {
      expect(screen.queryByText(/active filters/i)).toBeNull();
    });
  });

  it("preselects the dossier case for submit when opened with a case filter", async () => {
    mocks.backgroundCheckService.list.mockResolvedValue([]);
    mocks.backgroundCheckService.create.mockResolvedValue(
      buildCheck({ status: "submitted" }),
    );
    mocks.applicationService.getAll.mockResolvedValue([buildCase()]);

    render(
      <MemoryRouter initialEntries={["/background-checks?case_id=CASE-123"]}>
        <BackgroundChecksPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(mocks.applicationService.getAll).toHaveBeenCalled();
    });

    fireEvent.click(
      await screen.findByRole("button", { name: /submit check/i }),
    );

    await waitFor(() => {
      expect(mocks.backgroundCheckService.create).toHaveBeenCalledWith(
        expect.objectContaining({
          case: 1,
          check_type: "criminal",
          provider_key: "mock",
          run_async: true,
        }),
      );
    });
  });

  it("renders a canonical case link and retries failed checks", async () => {
    mocks.backgroundCheckService.list.mockResolvedValue([
      buildCheck({ id: "failed-check", status: "failed" }),
    ]);
    mocks.backgroundCheckService.retry.mockResolvedValue(
      buildCheck({ id: "failed-check", status: "submitted" }),
    );
    mocks.applicationService.getAll.mockResolvedValue([buildCase()]);

    render(
      <MemoryRouter initialEntries={["/background-checks"]}>
        <BackgroundChecksPage />
      </MemoryRouter>,
    );

    const openCaseLink = await screen.findByRole("link", {
      name: /open case/i,
    });
    expect(openCaseLink.getAttribute("href")).toBe(
      "/workspace/applications/CASE-123",
    );

    fireEvent.click(
      await screen.findByRole("button", { name: /retry check/i }),
    );

    await waitFor(() => {
      expect(mocks.backgroundCheckService.retry).toHaveBeenCalledWith(
        "failed-check",
      );
    });
    expect(mocks.toastSuccess).toHaveBeenCalledWith(
      "Background check retry submitted successfully.",
    );
  });
});
