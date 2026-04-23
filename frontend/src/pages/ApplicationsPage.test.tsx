// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";

import { ApplicationsPage } from "./ApplicationsPage";

const mocks = vi.hoisted(() => ({
  useApplications: vi.fn(),
  useAuth: vi.fn(),
}));

vi.mock("@/hooks/useApplications", () => ({
  useApplications: () => mocks.useApplications(),
}));

vi.mock("@/hooks/useAuth", () => ({
  useAuth: () => mocks.useAuth(),
}));

const makeApplication = (overrides: Record<string, unknown> = {}) => ({
  id: "case-1",
  case_id: "VET-2026-001",
  applicant: {
    full_name: "Jane Candidate",
    email: "jane@example.com",
  },
  applicant_email: "jane@example.com",
  office_title: "Policy Analyst",
  position_applied: "Policy Analyst",
  application_type: "appointment",
  appointment_exercise_id: "exercise-1",
  status: "under_review",
  priority: "medium",
  created_at: "2026-04-01T10:00:00Z",
  updated_at: "2026-04-01T11:00:00Z",
  notes: "Initial review",
  ...overrides,
});

const renderPage = (route = "/applications") => {
  return render(
    <MemoryRouter initialEntries={[route]}>
      <ApplicationsPage />
    </MemoryRouter>,
  );
};

describe("ApplicationsPage scope fetching", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("fetches all scope for governance/admin users", async () => {
    const refetch = vi.fn();
    mocks.useApplications.mockReturnValue({
      applications: [makeApplication()],
      loading: false,
      refetch,
    });
    mocks.useAuth.mockReturnValue({
      isAdmin: false,
      canManageActiveOrganizationGovernance: true,
    });

    renderPage("/applications");

    await waitFor(() => {
      expect(refetch).toHaveBeenCalledWith({ scope: "all" });
    });
  });

  it("fetches assigned scope for regular internal users", async () => {
    const refetch = vi.fn();
    mocks.useApplications.mockReturnValue({
      applications: [makeApplication()],
      loading: false,
      refetch,
    });
    mocks.useAuth.mockReturnValue({
      isAdmin: false,
      canManageActiveOrganizationGovernance: false,
    });

    renderPage("/applications");

    await waitFor(() => {
      expect(refetch).toHaveBeenCalledWith({ scope: "assigned" });
    });
  });

  it("respects explicit all scope for regular internal users", async () => {
    const refetch = vi.fn();
    mocks.useApplications.mockReturnValue({
      applications: [makeApplication()],
      loading: false,
      refetch,
    });
    mocks.useAuth.mockReturnValue({
      isAdmin: false,
      canManageActiveOrganizationGovernance: false,
    });

    renderPage("/applications?scope=all");

    await waitFor(() => {
      expect(refetch).toHaveBeenCalledWith({ scope: "all" });
    });
  });

  it("forces all scope on admin routes even for non-admin auth state", async () => {
    const refetch = vi.fn();
    mocks.useApplications.mockReturnValue({
      applications: [makeApplication()],
      loading: false,
      refetch,
    });
    mocks.useAuth.mockReturnValue({
      isAdmin: false,
      canManageActiveOrganizationGovernance: false,
    });

    renderPage("/admin/cases?scope=assigned");

    await waitFor(() => {
      expect(refetch).toHaveBeenCalledWith({ scope: "all" });
    });
  });

  it("falls back to assigned scope when scope query is invalid", async () => {
    const refetch = vi.fn();
    mocks.useApplications.mockReturnValue({
      applications: [makeApplication()],
      loading: false,
      refetch,
    });
    mocks.useAuth.mockReturnValue({
      isAdmin: false,
      canManageActiveOrganizationGovernance: false,
    });

    renderPage("/applications?scope=everything");

    await waitFor(() => {
      expect(refetch).toHaveBeenCalledWith({ scope: "assigned" });
    });
  });

  it("treats under_review filter as active pipeline statuses", async () => {
    const refetch = vi.fn();
    mocks.useApplications.mockReturnValue({
      applications: [
        makeApplication({
          id: "a",
          case_id: "VET-A",
          status: "document_analysis",
        }),
        makeApplication({ id: "b", case_id: "VET-B", status: "on_hold" }),
        makeApplication({ id: "c", case_id: "VET-C", status: "approved" }),
      ],
      loading: false,
      refetch,
    });
    mocks.useAuth.mockReturnValue({
      isAdmin: false,
      canManageActiveOrganizationGovernance: false,
    });

    renderPage("/applications?status=under_review");

    expect(await screen.findByText("VET-A")).toBeTruthy();
    expect(await screen.findByText("VET-B")).toBeTruthy();
    expect(screen.queryByText("VET-C")).toBeNull();
  });

  it("clears q, office, and exercise context filters", async () => {
    const refetch = vi.fn();
    mocks.useApplications.mockReturnValue({
      applications: [
        makeApplication({
          id: "ctx-a",
          case_id: "VET-ALPHA",
          office_title: "Policy Analyst",
          appointment_exercise_id: "exercise-1",
          applicant: {
            full_name: "Jane Candidate",
            email: "jane@example.com",
          },
        }),
        makeApplication({
          id: "ctx-b",
          case_id: "VET-BETA",
          office_title: "Finance Officer",
          appointment_exercise_id: "exercise-2",
          applicant: {
            full_name: "John Reviewer",
            email: "john@example.com",
          },
        }),
      ],
      loading: false,
      refetch,
    });
    mocks.useAuth.mockReturnValue({
      isAdmin: false,
      canManageActiveOrganizationGovernance: false,
    });

    renderPage("/applications?q=jane&office=policy&exercise=exercise-1");

    expect(await screen.findByText("Office: policy")).toBeTruthy();
    expect(
      await screen.findByText("Appointment exercise context active"),
    ).toBeTruthy();
    expect(await screen.findByText("Search: jane")).toBeTruthy();
    expect(await screen.findByText("VET-ALPHA")).toBeTruthy();
    expect(screen.queryByText("VET-BETA")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Clear Context" }));

    await waitFor(() => {
      expect(screen.queryByText("Search: jane")).toBeNull();
    });
    expect(screen.queryByText("Office: policy")).toBeNull();
    expect(
      screen.queryByText("Appointment exercise context active"),
    ).toBeNull();
    expect(await screen.findByText("VET-BETA")).toBeTruthy();
  });

  it("applies combined query filters for status, priority, type, office, and exercise", async () => {
    const refetch = vi.fn();
    mocks.useApplications.mockReturnValue({
      applications: [
        makeApplication({
          id: "combo-a",
          case_id: "VET-900",
          office_title: "Finance Office",
          appointment_exercise_id: "exercise-9",
          status: "approved",
          priority: "high",
          application_type: "contract",
        }),
        makeApplication({
          id: "combo-b",
          case_id: "VET-901",
          office_title: "Finance Office",
          appointment_exercise_id: "exercise-9",
          status: "approved",
          priority: "medium",
          application_type: "contract",
        }),
        makeApplication({
          id: "combo-c",
          case_id: "VET-902",
          office_title: "Policy Office",
          appointment_exercise_id: "exercise-3",
          status: "under_review",
          priority: "high",
          application_type: "employment",
        }),
      ],
      loading: false,
      refetch,
    });
    mocks.useAuth.mockReturnValue({
      isAdmin: false,
      canManageActiveOrganizationGovernance: false,
    });

    renderPage(
      "/applications?status=approved&priority=high&application_type=contract&office=finance&exercise=exercise-9&q=vet-9",
    );

    expect(await screen.findByText("VET-900")).toBeTruthy();
    expect(screen.queryByText("VET-901")).toBeNull();
    expect(screen.queryByText("VET-902")).toBeNull();
  });

  it("ignores invalid status query and behaves like all statuses", async () => {
    const refetch = vi.fn();
    mocks.useApplications.mockReturnValue({
      applications: [
        makeApplication({
          id: "status-a",
          case_id: "VET-100",
          status: "approved",
        }),
        makeApplication({
          id: "status-b",
          case_id: "VET-101",
          status: "on_hold",
        }),
      ],
      loading: false,
      refetch,
    });
    mocks.useAuth.mockReturnValue({
      isAdmin: false,
      canManageActiveOrganizationGovernance: false,
    });

    renderPage("/applications?status=unknown_status");

    expect(await screen.findByText("VET-100")).toBeTruthy();
    expect(await screen.findByText("VET-101")).toBeTruthy();
  });

  it("uses admin case detail links on admin routes", async () => {
    const refetch = vi.fn();
    mocks.useApplications.mockReturnValue({
      applications: [makeApplication({ case_id: "VET-777" })],
      loading: false,
      refetch,
    });
    mocks.useAuth.mockReturnValue({
      isAdmin: false,
      canManageActiveOrganizationGovernance: false,
    });

    renderPage("/admin/cases");

    const caseLink = await screen.findByRole("link", { name: /VET-777/i });
    expect((caseLink as HTMLAnchorElement).getAttribute("href")).toBe(
      "/admin/cases/VET-777",
    );
  });

  it("uses standard application detail links on non-admin routes", async () => {
    const refetch = vi.fn();
    mocks.useApplications.mockReturnValue({
      applications: [makeApplication({ case_id: "VET-888" })],
      loading: false,
      refetch,
    });
    mocks.useAuth.mockReturnValue({
      isAdmin: false,
      canManageActiveOrganizationGovernance: false,
    });

    renderPage("/applications");

    const caseLink = await screen.findByRole("link", { name: /VET-888/i });
    expect((caseLink as HTMLAnchorElement).getAttribute("href")).toBe(
      "/applications/VET-888",
    );
  });
});
