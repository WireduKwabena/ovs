// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { ApplicationDetailPage } from "./ApplicationDetailPage";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mocks = vi.hoisted(() => ({
  loadApplication: vi.fn(),
  update: vi.fn(),
  canManage: true,
  currentCase: null as Record<string, unknown> | null,
  loading: false,
  toastSuccess: vi.fn(),
  toastError: vi.fn(),
  toastInfo: vi.fn(),
}));

vi.mock("@/hooks/useApplications", () => ({
  useApplications: () => ({
    currentCase: mocks.currentCase,
    loading: mocks.loading,
    loadApplication: mocks.loadApplication,
  }),
}));

vi.mock("@/services/application.service", () => ({
  applicationService: { update: mocks.update },
}));

vi.mock("@/hooks/useAuth", () => ({
  useAuth: () => ({ canManageActiveOrganizationGovernance: mocks.canManage }),
}));

vi.mock("react-toastify", () => ({
  toast: {
    success: mocks.toastSuccess,
    error: mocks.toastError,
    info: mocks.toastInfo,
  },
}));

// StatusBadge only renders a span with the status text — no special setup needed.

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const makeCase = (
  overrides: Record<string, unknown> = {},
): Record<string, unknown> => ({
  id: "case-uuid-1",
  case_id: "CASE-0001",
  status: "pending",
  priority: "medium",
  application_type: "appointment",
  office_title: "Director General",
  position_applied: null,
  appointment_exercise_name: null,
  appointment_exercise_id: null,
  applicant: { full_name: "Jane Doe", email: "jane@example.com" },
  applicant_email: "jane@example.com",
  applicant_name: "Jane Doe",
  notes: "",
  created_at: "2026-03-01T10:00:00Z",
  updated_at: "2026-03-15T10:00:00Z",
  documents: [],
  consistency_result: null,
  fraud_result: null,
  ...overrides,
});

const renderPage = () =>
  render(
    <MemoryRouter initialEntries={["/applications/CASE-0001"]}>
      <Routes>
        <Route
          path="/applications/:caseId"
          element={<ApplicationDetailPage />}
        />
        <Route
          path="/workspace/applications"
          element={<div>Applications list</div>}
        />
        <Route path="/applications" element={<div>Applications index</div>} />
      </Routes>
    </MemoryRouter>,
  );

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("ApplicationDetailPage", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
    mocks.currentCase = null;
    mocks.loading = false;
    mocks.canManage = true;
  });

  it("shows a loader while the case is being fetched", () => {
    mocks.loading = true;
    renderPage();
    // The case heading is absent while loading
    expect(screen.queryByText("CASE-0001")).toBeNull();
    // loadApplication is called with the route param
    expect(mocks.loadApplication).toHaveBeenCalledWith("CASE-0001");
  });

  it("shows not-found message when case resolves to null", () => {
    mocks.currentCase = null;
    mocks.loading = false;
    renderPage();
    expect(screen.getByText(/vetting dossier not found/i)).toBeTruthy();
  });

  it("renders case ID and office title when loaded", () => {
    mocks.currentCase = makeCase();
    renderPage();
    expect(screen.getByText("CASE-0001")).toBeTruthy();
    expect(screen.getByText(/Director General/)).toBeTruthy();
  });

  it("calls applicationService.update with approved status on Approve click", async () => {
    mocks.currentCase = makeCase();
    mocks.update.mockResolvedValue({});
    renderPage();

    fireEvent.click(screen.getByRole("button", { name: /approve case/i }));

    await waitFor(() => {
      expect(mocks.update).toHaveBeenCalledWith(
        "CASE-0001",
        expect.objectContaining({ status: "approved" }),
      );
    });
    expect(mocks.toastSuccess).toHaveBeenCalledWith(
      "Case approved successfully",
    );
  });

  it("blocks rejection without notes and shows toast error", async () => {
    mocks.currentCase = makeCase();
    renderPage();

    fireEvent.click(screen.getByRole("button", { name: /reject case/i }));

    await waitFor(() => {
      expect(mocks.toastError).toHaveBeenCalledWith(
        "Please provide a reason for rejection",
      );
    });
    expect(mocks.update).not.toHaveBeenCalled();
  });

  it("hides decision actions when user cannot manage governance", () => {
    mocks.canManage = false;
    mocks.currentCase = makeCase();
    renderPage();
    expect(screen.queryByRole("button", { name: /approve case/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /reject case/i })).toBeNull();
  });
});
