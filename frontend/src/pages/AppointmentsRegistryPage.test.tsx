// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import AppointmentsRegistryPage from "./AppointmentsRegistryPage";

const authHookState = vi.hoisted(() => ({
  isAdmin: false,
  isInternalOrAdmin: false,
  canManageRegistry: false,
  canManageRegistryInActiveOrganization: false,
  canAdvanceAppointmentStage: true,
  canFinalizeAppointment: false,
  canPublishAppointment: false,
  canViewAppointmentStageActions: false,
  activeOrganization: {
    id: "org-1",
    code: "ORG1",
    name: "Org One",
    organization_type: "agency",
  } as { id: string; code: string; name: string; organization_type: string } | null,
  activeOrganizationId: "org-1" as string | null,
  hasCommitteeMembership: vi.fn(),
}));

const serviceMocks = vi.hoisted(() => ({
  listAppointments: vi.fn(),
  listPositions: vi.fn(),
  listPersonnel: vi.fn(),
  listCampaignsForAppointments: vi.fn(),
  listApprovalStageTemplates: vi.fn(),
  listApprovalStages: vi.fn(),
  getAppointmentPublication: vi.fn(),
  createAppointment: vi.fn(),
  createApprovalStageTemplate: vi.fn(),
  createApprovalStage: vi.fn(),
  appoint: vi.fn(),
  reject: vi.fn(),
  advanceAppointmentStage: vi.fn(),
  ensureVettingLinkage: vi.fn(),
  publishAppointment: vi.fn(),
  revokeAppointmentPublication: vi.fn(),
  listStageActions: vi.fn(),
}));

vi.mock("@/hooks/useAuth", () => ({
  useAuth: () => authHookState,
}));

vi.mock("@/services/government.service", () => ({
  governmentService: {
    listAppointments: serviceMocks.listAppointments,
    listPositions: serviceMocks.listPositions,
    listPersonnel: serviceMocks.listPersonnel,
    listCampaignsForAppointments: serviceMocks.listCampaignsForAppointments,
    listApprovalStageTemplates: serviceMocks.listApprovalStageTemplates,
    listApprovalStages: serviceMocks.listApprovalStages,
    getAppointmentPublication: serviceMocks.getAppointmentPublication,
    createAppointment: serviceMocks.createAppointment,
    createApprovalStageTemplate: serviceMocks.createApprovalStageTemplate,
    createApprovalStage: serviceMocks.createApprovalStage,
    appoint: serviceMocks.appoint,
    reject: serviceMocks.reject,
    advanceAppointmentStage: serviceMocks.advanceAppointmentStage,
    ensureVettingLinkage: serviceMocks.ensureVettingLinkage,
    publishAppointment: serviceMocks.publishAppointment,
    revokeAppointmentPublication: serviceMocks.revokeAppointmentPublication,
    listStageActions: serviceMocks.listStageActions,
  },
  isRecentAuthRequiredError: () => false,
}));

const appointmentRecord = {
  id: "appointment-1",
  organization: "org-1",
  organization_name: "Org One",
  committee: "committee-1",
  committee_name: "Appointments Committee",
  position: "position-1",
  position_title: "Minister of Finance",
  nominee: "personnel-1",
  nominee_name: "Jane Doe",
  appointment_exercise: "campaign-1",
  nominated_by_user: null,
  nominated_by_display: "President",
  nominated_by_org: "Office of the President",
  nomination_date: "2026-03-01",
  vetting_case: "case-1",
  status: "under_vetting",
  committee_recommendation: "",
  final_decision_by_user: null,
  final_decision_by_display: "",
  appointment_date: null,
  gazette_number: "",
  gazette_date: null,
  exit_date: null,
  exit_reason: "",
  is_public: false,
  created_at: "2026-03-01T00:00:00Z",
  updated_at: "2026-03-01T00:00:00Z",
} as const;

const baseTemplate = {
  id: "template-1",
  organization: "org-1",
  organization_name: "Org One",
  name: "Ministerial Chain",
  exercise_type: "ministerial",
  created_by: "user-1",
  created_at: "2026-03-01T00:00:00Z",
  stages: [],
} as const;

const baseStage = {
  id: "stage-1",
  template: "template-1",
  order: 1,
  name: "Committee Review",
  required_role: "committee_member",
  is_required: true,
  maps_to_status: "under_vetting",
  committee: "committee-1",
  committee_name: "Appointments Committee",
} as const;

const configureBaseServiceResponses = () => {
  serviceMocks.listAppointments.mockResolvedValue([appointmentRecord]);
  serviceMocks.listPositions.mockResolvedValue([
    {
      id: "position-1",
      organization: "org-1",
      title: "Minister of Finance",
      branch: "executive",
      institution: "Ministry of Finance",
      appointment_authority: "President",
      confirmation_required: true,
      constitutional_basis: "Article 1",
      term_length_years: null,
      required_qualifications: "",
      is_vacant: true,
      is_public: true,
      current_holder: null,
      rubric: null,
      created_at: "2026-03-01T00:00:00Z",
      updated_at: "2026-03-01T00:00:00Z",
    },
  ]);
  serviceMocks.listPersonnel.mockResolvedValue([
    {
      id: "personnel-1",
      organization: "org-1",
      full_name: "Jane Doe",
      date_of_birth: null,
      nationality: "Ghanaian",
      national_id_hash: "",
      national_id_encrypted: "",
      gender: "F",
      contact_email: "jane@example.com",
      contact_phone: "",
      bio_summary: "",
      academic_qualifications: [],
      professional_history: [],
      is_active_officeholder: false,
      is_public: true,
      linked_candidate: null,
      created_at: "2026-03-01T00:00:00Z",
      updated_at: "2026-03-01T00:00:00Z",
    },
  ]);
  serviceMocks.listCampaignsForAppointments.mockResolvedValue([
    {
      id: "campaign-1",
      name: "Appointment Exercise 2026",
      status: "active",
      approval_template: "template-1",
      exercise_type: "ministerial",
      required_document_types: [],
      review_due_days: 30,
      applicants_count: 0,
      initiated_by_email: "",
      created_at: "2026-03-01T00:00:00Z",
      updated_at: "2026-03-01T00:00:00Z",
    },
  ]);
  serviceMocks.listApprovalStageTemplates.mockResolvedValue([baseTemplate]);
  serviceMocks.listApprovalStages.mockResolvedValue([baseStage]);
  serviceMocks.getAppointmentPublication.mockRejectedValue(new Error("not found"));
};

describe("AppointmentsRegistryPage org + committee visibility", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
    authHookState.hasCommitteeMembership.mockReturnValue(false);
    authHookState.canManageRegistry = false;
    authHookState.canManageRegistryInActiveOrganization = false;
    authHookState.activeOrganization = {
      id: "org-1",
      code: "ORG1",
      name: "Org One",
      organization_type: "agency",
    };
    authHookState.activeOrganizationId = "org-1";
  });

  it("hides lifecycle transition controls for committee-bound records when actor lacks committee membership", async () => {
    configureBaseServiceResponses();
    authHookState.hasCommitteeMembership.mockReturnValue(false);

    render(
      <MemoryRouter>
        <AppointmentsRegistryPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(serviceMocks.listAppointments).toHaveBeenCalledTimes(1);
    });

    expect(await screen.findByText("Office Appointment Workflow")).toBeTruthy();
    expect(screen.queryByRole("button", { name: /apply transition/i })).toBeNull();
    expect(screen.getByText(/restricted to authorized stage actors/i)).toBeTruthy();
  });

  it("shows lifecycle transition controls for committee members in scope", async () => {
    configureBaseServiceResponses();
    authHookState.hasCommitteeMembership.mockReturnValue(true);

    render(
      <MemoryRouter>
        <AppointmentsRegistryPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(serviceMocks.listAppointments).toHaveBeenCalledTimes(1);
    });

    expect(await screen.findByText("Office Appointment Workflow")).toBeTruthy();
    expect(screen.getByRole("button", { name: /apply transition/i })).toBeTruthy();
  });

  it("hides nomination and approval-chain authoring controls for non-registry actors", async () => {
    configureBaseServiceResponses();
    authHookState.canManageRegistry = false;
    authHookState.canManageRegistryInActiveOrganization = false;
    authHookState.hasCommitteeMembership.mockReturnValue(false);

    render(
      <MemoryRouter>
        <AppointmentsRegistryPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(serviceMocks.listAppointments).toHaveBeenCalledTimes(1);
    });

    expect(screen.queryByText(/Initialize Approval Chain/i)).toBeNull();
    expect(screen.queryByText(/Create Nomination Record/i)).toBeNull();
    expect(
      await screen.findByText(/Nomination creation and approval-chain setup are restricted to registry administrators./i),
    ).toBeTruthy();
    expect(serviceMocks.listPositions).not.toHaveBeenCalled();
    expect(serviceMocks.listPersonnel).not.toHaveBeenCalled();
  });

  it("does not query registry-only datasets when registry capability exists but active organization scope is missing", async () => {
    configureBaseServiceResponses();
    authHookState.canManageRegistry = true;
    authHookState.canManageRegistryInActiveOrganization = false;
    authHookState.activeOrganization = null;
    authHookState.activeOrganizationId = null;

    render(
      <MemoryRouter>
        <AppointmentsRegistryPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(serviceMocks.listAppointments).toHaveBeenCalledTimes(1);
    });

    expect(serviceMocks.listPositions).not.toHaveBeenCalled();
    expect(serviceMocks.listPersonnel).not.toHaveBeenCalled();
  });

  it("renders committee-focused heading when opened in committee view mode", async () => {
    configureBaseServiceResponses();
    authHookState.canManageRegistry = false;
    authHookState.canManageRegistryInActiveOrganization = false;

    render(
      <MemoryRouter initialEntries={["/government/appointments?view=committee"]}>
        <AppointmentsRegistryPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(serviceMocks.listAppointments).toHaveBeenCalledTimes(1);
    });

    expect(await screen.findByText("Committee Review Queue")).toBeTruthy();
    expect(screen.queryByText(/Create Nomination Record/i)).toBeNull();
  });

  it("uses the updated laptop-friendly stats and template grid classes", async () => {
    configureBaseServiceResponses();
    authHookState.canManageRegistry = true;
    authHookState.canManageRegistryInActiveOrganization = true;

    render(
      <MemoryRouter>
        <AppointmentsRegistryPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(serviceMocks.listAppointments).toHaveBeenCalledTimes(1);
    });

    const statsSection = screen.getByText("Total Records").closest("section");
    expect(statsSection).toBeTruthy();
    expect(statsSection?.className).toContain("sm:grid-cols-2");
    expect(statsSection?.className).toContain("xl:grid-cols-4");

    const templateHeading = screen.getAllByText("Create Route Template")[0];
    const templateForm = templateHeading.closest("form");
    const templateGrid = templateForm?.parentElement;
    expect(templateGrid).toBeTruthy();
    expect(templateGrid?.className).toContain("xl:grid-cols-2");
  });
});

