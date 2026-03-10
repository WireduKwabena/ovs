import React, { useCallback, useEffect, useMemo, useState } from "react";
import { CheckCircle2, Clock3, Plus, RefreshCw, ShieldAlert, Stamp, Workflow } from "lucide-react";
import { toast } from "react-toastify";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/hooks/useAuth";
import { governmentService, isRecentAuthRequiredError } from "@/services/government.service";
import type {
  ApprovalStage,
  ApprovalStageTemplate,
  AppointmentPublication,
  AppointmentRecord,
  AppointmentStageAction,
  AppointmentStatus,
  GovernmentPosition,
  PersonnelRecord,
  VettingCampaign,
} from "@/types";

const STATUS_OPTIONS: AppointmentStatus[] = [
  "nominated",
  "under_vetting",
  "committee_review",
  "confirmation_pending",
  "appointed",
  "rejected",
  "withdrawn",
  "serving",
  "exited",
];
const STATUS_LABELS: Record<AppointmentStatus, string> = {
  nominated: "Nominated",
  under_vetting: "Under Vetting",
  committee_review: "Committee Review",
  confirmation_pending: "Confirmation Pending",
  appointed: "Appointed",
  rejected: "Rejected",
  withdrawn: "Withdrawn",
  serving: "Serving",
  exited: "Exited",
};
const STATUS_TRANSITION_OPTIONS: Record<AppointmentStatus, AppointmentStatus[]> = {
  nominated: ["under_vetting", "withdrawn"],
  under_vetting: ["committee_review", "withdrawn"],
  committee_review: ["confirmation_pending", "appointed", "rejected", "withdrawn"],
  confirmation_pending: ["appointed", "withdrawn", "rejected"],
  appointed: ["serving"],
  rejected: [],
  withdrawn: [],
  serving: ["exited"],
  exited: [],
};
const PUBLICATION_LABELS: Record<"draft" | "published" | "revoked", string> = {
  draft: "Draft",
  published: "Published",
  revoked: "Revoked",
};

const EXERCISE_TYPE_OPTIONS = ["ministerial", "judicial", "board", "local_gov", "diplomatic", "security"];
const REQUIRED_ROLE_OPTIONS = [
  "vetting_officer",
  "committee_member",
  "committee_chair",
  "appointing_authority",
  "registry_admin",
  "publication_officer",
  "auditor",
];
const todayIso = new Date().toISOString().slice(0, 10);

type StageActionIntent = "note" | "approve" | "reject" | "return";

const STAGE_ACTION_INTENT_OPTIONS: Array<{ value: StageActionIntent; label: string }> = [
  { value: "note", label: "Note / progress" },
  { value: "approve", label: "Approve intent" },
  { value: "reject", label: "Reject intent" },
  { value: "return", label: "Return intent" },
];
const COMMITTEE_REQUIRED_ROLES = new Set(["committee_member", "committee_chair"]);

function parseEvidenceLinks(rawValue: string): string[] {
  if (!rawValue.trim()) {
    return [];
  }
  return rawValue
    .split(/[\n,]/g)
    .map((item) => item.trim())
    .filter((item) => Boolean(item));
}

function humanizeCode(value: string): string {
  if (!value) {
    return "";
  }
  return value
    .split("_")
    .map((part) => (part.length > 0 ? `${part[0].toUpperCase()}${part.slice(1)}` : part))
    .join(" ");
}

function statusLabel(status: AppointmentStatus): string {
  return STATUS_LABELS[status] || humanizeCode(status);
}

function publicationLabel(status: "draft" | "published" | "revoked"): string {
  return PUBLICATION_LABELS[status] || humanizeCode(status);
}

const RECENT_AUTH_REQUIRED_MESSAGE =
  "Recent authentication is required for this sensitive action. Please sign in again and retry.";
const SELECT_FIELD_CLASS =
  "h-10 w-full rounded-md border border-border bg-input px-3 text-sm text-foreground shadow-xs outline-none transition-[color,box-shadow] focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px] disabled:cursor-not-allowed disabled:opacity-60";
const SELECT_FIELD_COMPACT_CLASS =
  "h-10 rounded-md border border-border bg-input px-3 text-sm text-foreground shadow-xs outline-none transition-[color,box-shadow] focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px] disabled:cursor-not-allowed disabled:opacity-60";

const AppointmentsRegistryPage: React.FC = () => {
  const {
    isAdmin,
    canManageRegistry,
    canManageRegistryInActiveOrganization,
    canAdvanceAppointmentStage,
    canFinalizeAppointment,
    canPublishAppointment,
    canViewAppointmentStageActions,
    activeOrganization,
    activeOrganizationId,
    hasCommitteeMembership,
  } = useAuth();

  const [rows, setRows] = useState<AppointmentRecord[]>([]);
  const [positions, setPositions] = useState<GovernmentPosition[]>([]);
  const [personnel, setPersonnel] = useState<PersonnelRecord[]>([]);
  const [campaigns, setCampaigns] = useState<VettingCampaign[]>([]);
  const [stageTemplates, setStageTemplates] = useState<ApprovalStageTemplate[]>([]);
  const [stages, setStages] = useState<ApprovalStage[]>([]);
  const [publicationsByAppointment, setPublicationsByAppointment] = useState<Record<string, AppointmentPublication>>(
    {},
  );
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [statusFilter, setStatusFilter] = useState<string>("all");

  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({
    position: "",
    nominee: "",
    appointment_exercise: "",
    nominated_by_display: "",
    nominated_by_org: "",
    nomination_date: todayIso,
    is_public: false,
  });

  const [templateCreating, setTemplateCreating] = useState(false);
  const [templateForm, setTemplateForm] = useState({
    name: "",
    exercise_type: "ministerial",
  });
  const [stageCreating, setStageCreating] = useState(false);
  const [stageForm, setStageForm] = useState({
    template: "",
    order: 1,
    name: "",
    required_role: "vetting_officer",
    is_required: true,
    maps_to_status: "under_vetting" as AppointmentStatus,
  });

  const [rowActionLoadingKey, setRowActionLoadingKey] = useState<string | null>(null);
  const [rowActionStatus, setRowActionStatus] = useState<Record<string, AppointmentStatus>>({});
  const [rowActionStageId, setRowActionStageId] = useState<Record<string, string>>({});
  const [rowActionIntent, setRowActionIntent] = useState<Record<string, StageActionIntent>>({});
  const [rowActionReason, setRowActionReason] = useState<Record<string, string>>({});
  const [rowActionEvidence, setRowActionEvidence] = useState<Record<string, string>>({});
  const [publishDraftByAppointment, setPublishDraftByAppointment] = useState<Record<string, Record<string, string>>>(
    {},
  );
  const [revokeDraftByAppointment, setRevokeDraftByAppointment] = useState<
    Record<string, { reason: string; make_private: boolean }>
  >({});
  const [stageActions, setStageActions] = useState<Record<string, AppointmentStageAction[]>>({});
  const [openActionsFor, setOpenActionsFor] = useState<string | null>(null);

  const loadPublicationState = useCallback(async (appointments: AppointmentRecord[]) => {
    if (appointments.length === 0) {
      setPublicationsByAppointment({});
      return;
    }

    const entries = await Promise.all(
      appointments.map(async (row) => {
        try {
          const publication = await governmentService.getAppointmentPublication(row.id);
          return [row.id, publication] as const;
        } catch {
          return [row.id, null] as const;
        }
      }),
    );

    const nextMap: Record<string, AppointmentPublication> = {};
    for (const [appointmentId, publication] of entries) {
      if (publication) {
        nextMap[appointmentId] = publication;
      }
    }
    setPublicationsByAppointment(nextMap);
  }, []);

  const loadAll = useCallback(async () => {
    const [appointments, positionRows, personnelRows, campaignRows, templateRows, stageRows] = await Promise.all([
      governmentService.listAppointments({
        status: statusFilter === "all" ? undefined : statusFilter,
      }),
      governmentService.listPositions(),
      governmentService.listPersonnel(),
      governmentService.listCampaignsForAppointments(),
      governmentService.listApprovalStageTemplates(),
      governmentService.listApprovalStages(),
    ]);
    setRows(appointments);
    setPositions(positionRows);
    setPersonnel(personnelRows);
    setCampaigns(campaignRows);
    setStageTemplates(templateRows);
    setStages(stageRows);
    void loadPublicationState(appointments);
  }, [activeOrganizationId, loadPublicationState, statusFilter]);

  useEffect(() => {
    const run = async () => {
      setLoading(true);
      try {
        await loadAll();
      } catch (error) {
        toast.error(error instanceof Error ? error.message : "Failed to load appointment registry.");
      } finally {
        setLoading(false);
      }
    };
    void run();
  }, [loadAll]);

  useEffect(() => {
    if (!stageForm.template && stageTemplates.length > 0) {
      setStageForm((previous) => ({ ...previous, template: stageTemplates[0].id }));
    }
  }, [stageForm.template, stageTemplates]);

  const scopedPositions = useMemo(() => {
    if (!activeOrganizationId) {
      return positions;
    }
    return positions.filter(
      (item) => !item.organization || String(item.organization) === activeOrganizationId,
    );
  }, [activeOrganizationId, positions]);
  const scopedPersonnel = useMemo(() => {
    if (!activeOrganizationId) {
      return personnel;
    }
    return personnel.filter(
      (item) => !item.organization || String(item.organization) === activeOrganizationId,
    );
  }, [activeOrganizationId, personnel]);
  const scopedCampaigns = useMemo(() => {
    if (!activeOrganizationId) {
      return campaigns;
    }
    return campaigns.filter(
      (item) => !item.organization || String(item.organization) === activeOrganizationId,
    );
  }, [activeOrganizationId, campaigns]);

  useEffect(() => {
    if (scopedPositions.length === 0) {
      setForm((previous) => ({ ...previous, position: "" }));
      return;
    }
    if (!scopedPositions.some((row) => row.id === form.position)) {
      setForm((previous) => ({ ...previous, position: scopedPositions[0].id }));
    }
  }, [form.position, scopedPositions]);

  useEffect(() => {
    if (scopedPersonnel.length === 0) {
      setForm((previous) => ({ ...previous, nominee: "" }));
      return;
    }
    if (!scopedPersonnel.some((row) => row.id === form.nominee)) {
      setForm((previous) => ({ ...previous, nominee: scopedPersonnel[0].id }));
    }
  }, [form.nominee, scopedPersonnel]);

  useEffect(() => {
    if (!form.appointment_exercise) {
      return;
    }
    if (!scopedCampaigns.some((row) => row.id === form.appointment_exercise)) {
      setForm((previous) => ({ ...previous, appointment_exercise: "" }));
    }
  }, [form.appointment_exercise, scopedCampaigns]);

  useEffect(() => {
    setOpenActionsFor(null);
    setStageActions({});
  }, [activeOrganizationId]);

  const hasPositionOptions = scopedPositions.length > 0;
  const hasNomineeOptions = scopedPersonnel.length > 0;
  const canInitializeApprovalChain = canManageRegistryInActiveOrganization;
  const canCreateAppointment =
    canManageRegistryInActiveOrganization && hasPositionOptions && hasNomineeOptions;

  const isWithinActiveOrganization = useCallback(
    (organizationId: string | null | undefined): boolean => {
      if (isAdmin) {
        return true;
      }
      const normalizedOrganizationId = String(organizationId || "").trim();
      if (!activeOrganizationId) {
        return !normalizedOrganizationId;
      }
      if (!normalizedOrganizationId) {
        return true;
      }
      return normalizedOrganizationId === activeOrganizationId;
    },
    [activeOrganizationId, isAdmin],
  );

  const hasCommitteeAccess = useCallback(
    (committeeId: string | null | undefined): boolean => {
      const normalizedCommitteeId = String(committeeId || "").trim();
      if (!normalizedCommitteeId) {
        return true;
      }
      if (isAdmin) {
        return true;
      }
      return hasCommitteeMembership(normalizedCommitteeId);
    },
    [hasCommitteeMembership, isAdmin],
  );

  const canManagePublicationForRow = useCallback(
    (row: AppointmentRecord): boolean =>
      canPublishAppointment && isWithinActiveOrganization(row.organization),
    [canPublishAppointment, isWithinActiveOrganization],
  );

  const canViewStageActionsForRow = useCallback(
    (row: AppointmentRecord): boolean => {
      if (!canViewAppointmentStageActions || !isWithinActiveOrganization(row.organization)) {
        return false;
      }
      return hasCommitteeAccess(row.committee);
    },
    [canViewAppointmentStageActions, hasCommitteeAccess, isWithinActiveOrganization],
  );

  const canManageLifecycleForRow = useCallback(
    (
      row: AppointmentRecord,
      targetStatus: AppointmentStatus,
      stage: ApprovalStage | undefined,
    ): boolean => {
      if (!canAdvanceAppointmentStage || !isWithinActiveOrganization(row.organization)) {
        return false;
      }
      const stageRole = String(stage?.required_role || "")
        .trim()
        .toLowerCase();
      const committeeSensitiveTransition =
        targetStatus === "committee_review" || COMMITTEE_REQUIRED_ROLES.has(stageRole);
      if (!committeeSensitiveTransition) {
        return true;
      }
      const boundCommitteeId = stage?.committee || row.committee || null;
      return hasCommitteeAccess(boundCommitteeId);
    },
    [canAdvanceAppointmentStage, hasCommitteeAccess, isWithinActiveOrganization],
  );

  const canEnsureLinkageForRow = useCallback(
    (row: AppointmentRecord): boolean =>
      canAdvanceAppointmentStage && isWithinActiveOrganization(row.organization),
    [canAdvanceAppointmentStage, isWithinActiveOrganization],
  );

  const scopedRows = useMemo(() => {
    return rows.filter((row) => isWithinActiveOrganization(row.organization));
  }, [isWithinActiveOrganization, rows]);

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      await loadAll();
      toast.success("Appointment registry refreshed.");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Refresh failed.");
    } finally {
      setRefreshing(false);
    }
  };

  const handleCreate = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!canManageRegistryInActiveOrganization) {
      toast.error("Registry authority and active organization context are required to create nominations.");
      return;
    }
    if (!canCreateAppointment) {
      toast.error("Create at least one government position and one personnel record before nominating.");
      return;
    }
    if (!form.position || !form.nominee || !form.nominated_by_display.trim()) {
      toast.error("Position, nominee, and nominated by display are required.");
      return;
    }

    setCreating(true);
    try {
      await governmentService.createAppointment({
        position: form.position,
        nominee: form.nominee,
        appointment_exercise: form.appointment_exercise || null,
        nominated_by_display: form.nominated_by_display.trim(),
        nominated_by_org: form.nominated_by_org.trim(),
        nomination_date: form.nomination_date,
        is_public: form.is_public,
      });
      toast.success("Appointment record created.");
      setForm((previous) => ({
        ...previous,
        nominated_by_display: "",
        nominated_by_org: "",
        is_public: false,
      }));
      await loadAll();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to create appointment record.");
    } finally {
      setCreating(false);
    }
  };

  const handleCreateTemplate = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!templateForm.name.trim()) {
      toast.error("Template name is required.");
      return;
    }

    setTemplateCreating(true);
    try {
      const created = await governmentService.createApprovalStageTemplate({
        name: templateForm.name.trim(),
        exercise_type: templateForm.exercise_type,
      });
      setTemplateForm((previous) => ({ ...previous, name: "" }));
      setStageForm((previous) => ({ ...previous, template: created.id }));
      toast.success("Approval template created.");
      await loadAll();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to create approval template.");
    } finally {
      setTemplateCreating(false);
    }
  };

  const handleCreateStage = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!stageForm.template || !stageForm.name.trim() || Number(stageForm.order) <= 0) {
      toast.error("Template, stage name, and order are required.");
      return;
    }

    setStageCreating(true);
    try {
      await governmentService.createApprovalStage({
        template: stageForm.template,
        order: Number(stageForm.order),
        name: stageForm.name.trim(),
        required_role: stageForm.required_role.trim(),
        is_required: stageForm.is_required,
        maps_to_status: stageForm.maps_to_status,
      });
      setStageForm((previous) => ({
        ...previous,
        order: Number(previous.order) + 1,
        name: "",
      }));
      toast.success("Approval stage created.");
      await loadAll();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to create approval stage.");
    } finally {
      setStageCreating(false);
    }
  };

  const campaignById = useMemo(() => {
    return campaigns.reduce<Record<string, VettingCampaign>>((accumulator, campaign) => {
      accumulator[campaign.id] = campaign;
      return accumulator;
    }, {});
  }, [campaigns]);

  const templateById = useMemo(() => {
    return stageTemplates.reduce<Record<string, ApprovalStageTemplate>>((accumulator, template) => {
      accumulator[template.id] = template;
      return accumulator;
    }, {});
  }, [stageTemplates]);

  const stagesByTemplate = useMemo(() => {
    return stages.reduce<Record<string, ApprovalStage[]>>((accumulator, stage) => {
      if (!accumulator[stage.template]) {
        accumulator[stage.template] = [];
      }
      accumulator[stage.template].push(stage);
      return accumulator;
    }, {});
  }, [stages]);

  const getStageChoicesForRow = useCallback(
    (row: AppointmentRecord, targetStatus: AppointmentStatus): ApprovalStage[] => {
      if (!row.appointment_exercise) {
        return [];
      }
      const campaign = campaignById[row.appointment_exercise];
      if (!campaign?.approval_template) {
        return [];
      }
      const templateStages = stagesByTemplate[campaign.approval_template] || [];
      const matching = templateStages.filter((stage) => stage.maps_to_status === targetStatus);
      return (matching.length > 0 ? matching : templateStages).sort((left, right) => left.order - right.order);
    },
    [campaignById, stagesByTemplate],
  );

  const getStatusOptionsForRow = useCallback((currentStatus: AppointmentStatus): AppointmentStatus[] => {
    const allowed = [currentStatus, ...(STATUS_TRANSITION_OPTIONS[currentStatus] || [])];
    return STATUS_OPTIONS.filter((status) => allowed.includes(status));
  }, []);

  const applyRowStatusAction = async (row: AppointmentRecord) => {
    if (!canAdvanceAppointmentStage) {
      toast.error("You are not authorized to transition appointment records.");
      return;
    }
    if (!isWithinActiveOrganization(row.organization)) {
      toast.error("Switch to the matching organization context to transition this appointment.");
      return;
    }

    const targetStatus = rowActionStatus[row.id];
    if (!targetStatus || targetStatus === row.status) {
      toast.info("Choose a different status to advance.");
      return;
    }
    if ((targetStatus === "appointed" || targetStatus === "rejected") && !canFinalizeAppointment) {
      toast.error("Only appointing authority or admins can finalize appointment decisions.");
      return;
    }
    const stageChoices = getStageChoicesForRow(row, targetStatus);
    const stageId = rowActionStageId[row.id] || stageChoices[0]?.id || undefined;
    const selectedStage = stageChoices.find((item) => item.id === stageId) || stageChoices[0];
    if (!canManageLifecycleForRow(row, targetStatus, selectedStage)) {
      toast.error("You do not have committee or organization access for this stage transition.");
      return;
    }
    const evidenceLinks = parseEvidenceLinks(rowActionEvidence[row.id] || "");
    const actionIntent = rowActionIntent[row.id] || "note";
    const trimmedReason = (rowActionReason[row.id] || "").trim();
    const reasonWithIntent =
      actionIntent === "note" ? trimmedReason : `${actionIntent.toUpperCase()}: ${trimmedReason || "No note provided."}`;

    setRowActionLoadingKey(`${row.id}:advance`);
    try {
      if (targetStatus === "appointed") {
        await governmentService.appoint(row.id, {
          stage_id: stageId,
          reason_note: reasonWithIntent,
          evidence_links: evidenceLinks,
        });
      } else if (targetStatus === "rejected") {
        await governmentService.reject(row.id, {
          stage_id: stageId,
          reason_note: reasonWithIntent,
          evidence_links: evidenceLinks,
        });
      } else {
        await governmentService.advanceAppointmentStage(row.id, {
          status: targetStatus,
          stage_id: stageId,
          reason_note: reasonWithIntent,
          evidence_links: evidenceLinks,
        });
      }
      toast.success("Appointment lifecycle updated.");
      await loadAll();
    } catch (error) {
      if (isRecentAuthRequiredError(error)) {
        toast.error(RECENT_AUTH_REQUIRED_MESSAGE);
      } else {
        toast.error(error instanceof Error ? error.message : "Failed to apply lifecycle action.");
      }
    } finally {
      setRowActionLoadingKey(null);
    }
  };

  const handleEnsureLinkage = async (row: AppointmentRecord) => {
    setRowActionLoadingKey(`${row.id}:linkage`);
    try {
      await governmentService.ensureVettingLinkage(row.id);
      toast.success("Vetting linkage ensured.");
      await loadAll();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to ensure linkage.");
    } finally {
      setRowActionLoadingKey(null);
    }
  };

  const handlePublish = async (row: AppointmentRecord) => {
    if (!canPublishAppointment) {
      toast.error("You are not authorized to publish appointment records.");
      return;
    }
    if (!canManagePublicationForRow(row)) {
      toast.error("Switch to the matching organization context to publish this appointment.");
      return;
    }
    const draft = publishDraftByAppointment[row.id] || {};
    setRowActionLoadingKey(`${row.id}:publish`);
    try {
      await governmentService.publishAppointment(row.id, {
        publication_reference: draft.publication_reference?.trim(),
        publication_document_hash: draft.publication_document_hash?.trim().toLowerCase(),
        publication_notes: draft.publication_notes?.trim(),
        gazette_number: draft.gazette_number?.trim(),
        gazette_date: draft.gazette_date?.trim() || undefined,
      });
      toast.success("Appointment publication recorded.");
      await loadAll();
    } catch (error) {
      if (isRecentAuthRequiredError(error)) {
        toast.error(RECENT_AUTH_REQUIRED_MESSAGE);
      } else {
        toast.error(error instanceof Error ? error.message : "Failed to publish appointment.");
      }
    } finally {
      setRowActionLoadingKey(null);
    }
  };

  const handleRevoke = async (row: AppointmentRecord) => {
    if (!canPublishAppointment) {
      toast.error("You are not authorized to revoke appointment publications.");
      return;
    }
    if (!canManagePublicationForRow(row)) {
      toast.error("Switch to the matching organization context to revoke this appointment publication.");
      return;
    }
    const draft = revokeDraftByAppointment[row.id] || { reason: "", make_private: true };
    if (!draft.reason.trim()) {
      toast.error("Revocation reason is required.");
      return;
    }
    setRowActionLoadingKey(`${row.id}:revoke`);
    try {
      await governmentService.revokeAppointmentPublication(row.id, {
        revocation_reason: draft.reason.trim(),
        make_private: draft.make_private,
      });
      toast.success("Appointment publication revoked.");
      await loadAll();
    } catch (error) {
      if (isRecentAuthRequiredError(error)) {
        toast.error(RECENT_AUTH_REQUIRED_MESSAGE);
      } else {
        toast.error(error instanceof Error ? error.message : "Failed to revoke publication.");
      }
    } finally {
      setRowActionLoadingKey(null);
    }
  };

  const handleToggleActions = async (row: AppointmentRecord) => {
    if (!canViewStageActionsForRow(row)) {
      toast.error("Only committee members/chairs and admins can view stage actions.");
      return;
    }

    if (openActionsFor === row.id) {
      setOpenActionsFor(null);
      return;
    }

    setOpenActionsFor(row.id);
    if (stageActions[row.id]) {
      return;
    }
    try {
      const actions = await governmentService.listStageActions(row.id);
      setStageActions((previous) => ({ ...previous, [row.id]: actions }));
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "You are not permitted to view stage actions for this record.");
    }
  };

  const setPublishDraftField = useCallback((appointmentId: string, field: string, value: string) => {
    setPublishDraftByAppointment((previous) => ({
      ...previous,
      [appointmentId]: {
        ...(previous[appointmentId] || {}),
        [field]: value,
      },
    }));
  }, []);

  const setRevokeDraft = useCallback(
    (appointmentId: string, patch: Partial<{ reason: string; make_private: boolean }>) => {
      setRevokeDraftByAppointment((previous) => ({
        ...previous,
        [appointmentId]: {
          reason: previous[appointmentId]?.reason || "",
          make_private: previous[appointmentId]?.make_private ?? true,
          ...patch,
        },
      }));
    },
    [],
  );

  const stats = useMemo(() => {
    const total = scopedRows.length;
    const active = scopedRows.filter((row) =>
      ["nominated", "under_vetting", "committee_review", "confirmation_pending"].includes(row.status),
    ).length;
    const appointed = scopedRows.filter((row) => row.status === "appointed" || row.status === "serving").length;
    const published = scopedRows.filter(
      (row) => publicationsByAppointment[row.id]?.status === "published",
    ).length;
    return { total, active, appointed, published };
  }, [publicationsByAppointment, scopedRows]);

  return (
    <main className="mx-auto max-w-7xl px-4 py-8 space-y-6">
      <header className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-3xl font-black tracking-tight text-slate-900">Appointment Registry</h1>
            <p className="mt-1 text-sm text-slate-700">
              Govern nomination, approval-chain transitions, and publication lifecycle.
            </p>
            <p className="mt-1 text-xs font-semibold uppercase tracking-wide text-slate-700">
              Active organization scope: {activeOrganization?.name || "Default"}
            </p>
          </div>
          <Button type="button" variant="outline" onClick={() => void handleRefresh()} disabled={refreshing}>
            <RefreshCw className={`mr-2 h-4 w-4 ${refreshing ? "animate-spin" : ""}`} />
            Refresh
          </Button>
        </div>
      </header>

      {!isAdmin && !activeOrganizationId ? (
        <section className="rounded-xl border border-amber-300 bg-amber-50 p-4 text-sm text-amber-900">
          Select an active organization to view and act on organization-scoped appointment records.
        </section>
      ) : null}

      <section className="grid gap-4 md:grid-cols-4">
        <article className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <p className="text-sm text-slate-700">Total Records</p>
          <p className="mt-2 text-3xl font-black text-slate-900">{stats.total}</p>
        </article>
        <article className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <p className="text-sm text-slate-700">Active Pipeline</p>
          <p className="mt-2 text-3xl font-black text-indigo-700">{stats.active}</p>
        </article>
        <article className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <p className="text-sm text-slate-700">Appointed / Serving</p>
          <p className="mt-2 text-3xl font-black text-emerald-700">{stats.appointed}</p>
        </article>
        <article className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <p className="text-sm text-slate-700">Published</p>
          <p className="mt-2 text-3xl font-black text-cyan-700">{stats.published}</p>
        </article>
      </section>

      {canInitializeApprovalChain ? (
        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="mb-3 flex items-center gap-2">
            <Workflow className="h-5 w-5 text-indigo-700" />
            <h2 className="text-lg font-bold text-slate-900">Initialize Approval Chain</h2>
          </div>
          <p className="mb-4 text-sm text-slate-700">
            Define approval-stage templates and stage roles used by campaign-linked appointment workflows.
          </p>

          <div className="grid gap-4 lg:grid-cols-2">
            <form onSubmit={handleCreateTemplate} className="rounded-lg border border-slate-200 p-4">
              <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-700">Create Stage Template</h3>
              <div className="mt-3 space-y-3">
                <div>
                  <label htmlFor="template-name" className="mb-1 block text-xs font-semibold uppercase text-slate-700">Template Name</label>
                  <Input
                    id="template-name"
                    value={templateForm.name}
                    onChange={(event) => setTemplateForm((previous) => ({ ...previous, name: event.target.value }))}
                    placeholder="Ministerial Standard Chain"
                  />
                </div>
                <div>
                  <label htmlFor="template-exercise-type" className="mb-1 block text-xs font-semibold uppercase text-slate-700">Exercise Type</label>
                  <select
                    className={SELECT_FIELD_CLASS}
                    id="template-exercise-type"
                    value={templateForm.exercise_type}
                    onChange={(event) =>
                      setTemplateForm((previous) => ({ ...previous, exercise_type: event.target.value }))
                    }
                  >
                    {EXERCISE_TYPE_OPTIONS.map((value) => (
                      <option key={value} value={value}>
                        {value}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="flex justify-end">
                  <Button type="submit" disabled={templateCreating}>
                    {templateCreating ? "Saving..." : "Create Template"}
                  </Button>
                </div>
              </div>
            </form>

            <form onSubmit={handleCreateStage} className="rounded-lg border border-slate-200 p-4">
              <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-700">Create Stage</h3>
              <div className="mt-3 grid gap-3 sm:grid-cols-2">
                <div className="sm:col-span-2">
                  <label htmlFor="stage-template" className="mb-1 block text-xs font-semibold uppercase text-slate-700">Template</label>
                  <select
                    className={SELECT_FIELD_CLASS}
                    id="stage-template"
                    value={stageForm.template}
                    onChange={(event) => setStageForm((previous) => ({ ...previous, template: event.target.value }))}
                  >
                    <option value="">Select template</option>
                    {stageTemplates.map((template) => (
                      <option key={template.id} value={template.id}>
                        {template.name}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label htmlFor="stage-order" className="mb-1 block text-xs font-semibold uppercase text-slate-700">Order</label>
                  <Input
                    type="number"
                    min={1}
                    id="stage-order"
                    value={stageForm.order}
                    onChange={(event) =>
                      setStageForm((previous) => ({ ...previous, order: Number(event.target.value) || 1 }))
                    }
                  />
                </div>
                <div>
                  <label htmlFor="stage-maps-to-status" className="mb-1 block text-xs font-semibold uppercase text-slate-700">Maps To Status</label>
                  <select
                    className={SELECT_FIELD_CLASS}
                    id="stage-maps-to-status"
                    value={stageForm.maps_to_status}
                    onChange={(event) =>
                      setStageForm((previous) => ({
                        ...previous,
                        maps_to_status: event.target.value as AppointmentStatus,
                      }))
                    }
                  >
                    {STATUS_OPTIONS.map((status) => (
                      <option key={status} value={status}>
                        {statusLabel(status)}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="sm:col-span-2">
                  <label htmlFor="stage-name" className="mb-1 block text-xs font-semibold uppercase text-slate-700">Stage Name</label>
                  <Input
                    id="stage-name"
                    value={stageForm.name}
                    onChange={(event) => setStageForm((previous) => ({ ...previous, name: event.target.value }))}
                    placeholder="Committee Review"
                  />
                </div>
                <div>
                  <label htmlFor="stage-required-role" className="mb-1 block text-xs font-semibold uppercase text-slate-700">Required Role</label>
                  <select
                    className={SELECT_FIELD_CLASS}
                    id="stage-required-role"
                    value={stageForm.required_role}
                    onChange={(event) =>
                      setStageForm((previous) => ({ ...previous, required_role: event.target.value }))
                    }
                  >
                    {REQUIRED_ROLE_OPTIONS.map((roleName) => (
                      <option key={roleName} value={roleName}>
                        {roleName}
                      </option>
                    ))}
                  </select>
                </div>
                <label className="inline-flex items-center gap-2 self-end text-sm text-slate-800">
                  <input
                    type="checkbox"
                    checked={stageForm.is_required}
                    onChange={(event) =>
                      setStageForm((previous) => ({ ...previous, is_required: event.target.checked }))
                    }
                  />
                  Required stage
                </label>
                <div className="flex justify-end sm:col-span-2">
                  <Button type="submit" disabled={stageCreating}>
                    {stageCreating ? "Saving..." : "Create Stage"}
                  </Button>
                </div>
              </div>
            </form>
          </div>
        </section>
      ) : null}

      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="text-lg font-bold text-slate-900">Create Nomination Record</h2>
        {!canCreateAppointment ? (
          <div className="mt-3 rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
            {!canManageRegistry
              ? "Only registry operators can create nomination records."
              : !activeOrganizationId && !isAdmin
              ? "Select an active organization before creating nomination records."
              : !hasPositionOptions || !hasNomineeOptions
              ? "Create at least one position and one personnel profile before starting a nomination."
              : "You do not have permission to create nomination records."}
          </div>
        ) : null}
        <form onSubmit={handleCreate} className="mt-4 grid gap-3 md:grid-cols-2">
          <div>
            <label htmlFor="position" className="mb-1 block text-xs font-semibold uppercase text-slate-700">Position</label>
            <select
              className={SELECT_FIELD_CLASS}
              id="position"
              value={form.position}
              disabled={!hasPositionOptions}
              onChange={(event) => setForm((p) => ({ ...p, position: event.target.value }))}
            >
              <option value="">{hasPositionOptions ? "Select position" : "No positions available"}</option>
              {scopedPositions.map((position) => (
                <option key={position.id} value={position.id}>
                  {position.title} - {position.institution}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="nominee" className="mb-1 block text-xs font-semibold uppercase text-slate-700">Nominee</label>
            <select
              className={SELECT_FIELD_CLASS}
              id="nominee"
              value={form.nominee}
              disabled={!hasNomineeOptions}
              onChange={(event) => setForm((p) => ({ ...p, nominee: event.target.value }))}
            >
              <option value="">{hasNomineeOptions ? "Select nominee" : "No personnel available"}</option>
              {scopedPersonnel.map((row) => (
                <option key={row.id} value={row.id}>
                  {row.full_name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="appointment-exercise" className="mb-1 block text-xs font-semibold uppercase text-slate-700">Appointment Exercise (Campaign)</label>
            <select
              className={SELECT_FIELD_CLASS}
              id="appointment-exercise"
              value={form.appointment_exercise}
              onChange={(event) => setForm((p) => ({ ...p, appointment_exercise: event.target.value }))}
            >
              <option value="">None</option>
              {scopedCampaigns.map((campaign) => (
                <option key={campaign.id} value={campaign.id}>
                  {campaign.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="nomination-date" className="mb-1 block text-xs font-semibold uppercase text-slate-700">Nomination Date</label>
            <Input
              type="date"
              id="nomination-date"
              value={form.nomination_date}
              onChange={(event) => setForm((p) => ({ ...p, nomination_date: event.target.value }))}
            />
          </div>
          <div>
            <label htmlFor="nominated-by-display" className="mb-1 block text-xs font-semibold uppercase text-slate-700">Nominated By (Display)</label>
            <Input
              id="nominated-by-display"
              value={form.nominated_by_display}
              onChange={(event) => setForm((p) => ({ ...p, nominated_by_display: event.target.value }))}
              placeholder="H.E. President"
            />
          </div>
          <div>
            <label htmlFor="nominating-organization" className="mb-1 block text-xs font-semibold uppercase text-slate-700">Nominating Organization</label>
            <Input
              id="nominating-organization"
              value={form.nominated_by_org}
              onChange={(event) => setForm((p) => ({ ...p, nominated_by_org: event.target.value }))}
              placeholder="Office of the President"
            />
          </div>
          <label className="inline-flex items-center gap-2 text-sm text-slate-800 md:col-span-2">
            <input
              type="checkbox"
              checked={form.is_public}
              onChange={(event) => setForm((p) => ({ ...p, is_public: event.target.checked }))}
            />
            Mark record public
          </label>
          <div className="md:col-span-2 flex justify-end">
            <Button type="submit" disabled={creating || !canCreateAppointment}>
              <Plus className="mr-2 h-4 w-4" />
              {creating ? "Saving..." : canCreateAppointment ? "Create Nomination" : "Add Prerequisites First"}
            </Button>
          </div>
        </form>
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-lg font-bold text-slate-900">Appointment Records</h2>
          <select
            title="Filter by status"
            className={SELECT_FIELD_COMPACT_CLASS}
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value)}
          >
            <option value="all">All statuses</option>
            {STATUS_OPTIONS.map((status) => (
              <option key={status} value={status}>
                {statusLabel(status)}
              </option>
            ))}
          </select>
        </div>

        {loading ? (
          <p className="mt-4 text-sm text-slate-700">Loading appointment records...</p>
        ) : scopedRows.length === 0 ? (
          <div className="mt-4 rounded-lg border border-dashed border-slate-300 p-6 text-center text-sm text-slate-700">
            No appointment records found in the active organization scope. Create a nomination above or run
            `python manage.py setup_demo` to preload a full demo workflow.
          </div>
        ) : (
          <div className="mt-4 space-y-4">
            {scopedRows.map((row) => {
              const requestedStatusTarget = rowActionStatus[row.id] || row.status;
              const canFinalizeForRow =
                canFinalizeAppointment && isWithinActiveOrganization(row.organization);
              const lifecycleOptions = getStatusOptionsForRow(row.status).filter((candidateStatus) => {
                if (candidateStatus === "appointed" || candidateStatus === "rejected") {
                  return canFinalizeForRow || candidateStatus === row.status;
                }
                return true;
              });
              const statusTarget = lifecycleOptions.includes(requestedStatusTarget)
                ? requestedStatusTarget
                : row.status;
              const stageChoices = getStageChoicesForRow(row, statusTarget);
              const selectedStageId = rowActionStageId[row.id] || stageChoices[0]?.id || "";
              const selectedStage = stageChoices.find((stage) => stage.id === selectedStageId) || stageChoices[0];
              const intent = rowActionIntent[row.id] || "note";
              const reason = rowActionReason[row.id] || "";
              const evidenceInput = rowActionEvidence[row.id] || "";
              const actionsOpen = openActionsFor === row.id;
              const itemActions = stageActions[row.id] || [];
              const publishDraft = publishDraftByAppointment[row.id] || {};
              const revokeDraft = revokeDraftByAppointment[row.id] || { reason: "", make_private: true };
              const publication = publicationsByAppointment[row.id];
              const publicationStatus = publication?.status || "draft";
              const campaign = row.appointment_exercise ? campaignById[row.appointment_exercise] : undefined;
              const template = campaign?.approval_template ? templateById[campaign.approval_template] : undefined;
              const templateStages = template
                ? [...(stagesByTemplate[template.id] || [])].sort((left, right) => left.order - right.order)
                : [];
              const approvalChainStatus = !campaign
                ? "No campaign linked"
                : !template
                  ? "Campaign missing approval template"
                  : templateStages.length === 0
                    ? "Template has no stages"
                    : `${templateStages.length} stage${templateStages.length > 1 ? "s" : ""} configured`;
              const isAdvanceLoading = rowActionLoadingKey === `${row.id}:advance`;
              const isLinkageLoading = rowActionLoadingKey === `${row.id}:linkage`;
              const isPublishLoading = rowActionLoadingKey === `${row.id}:publish`;
              const isRevokeLoading = rowActionLoadingKey === `${row.id}:revoke`;
              const isRowBusy = Boolean(rowActionLoadingKey && rowActionLoadingKey.startsWith(`${row.id}:`));
              const canManageLifecycle = canManageLifecycleForRow(row, statusTarget, selectedStage);
              const canManagePublication = canManagePublicationForRow(row);
              const canViewStageActions = canViewStageActionsForRow(row);
              const canEnsureLinkage = canEnsureLinkageForRow(row);
              const rowOutOfScope = !isWithinActiveOrganization(row.organization);
              return (
                <article key={row.id} className="rounded-xl border border-slate-200 p-4">
                  <div className="flex flex-wrap items-start justify-between gap-4">
                    <div>
                      <p className="text-lg font-semibold text-slate-900">{row.position_title || row.position}</p>
                      <p className="text-sm text-slate-700">
                        Nominee: {row.nominee_name || row.nominee} | Status:{" "}
                        <span className="font-semibold text-indigo-700">{statusLabel(row.status)}</span>
                      </p>
                      <p className="text-xs text-slate-700">
                        Nominated by: {row.nominated_by_display} on {new Date(row.nomination_date).toLocaleDateString()}
                      </p>
                      <div className="mt-1 flex flex-wrap items-center gap-2 text-xs">
                        {row.vetting_case ? (
                          <span className="inline-flex items-center gap-1 rounded bg-emerald-100 px-2 py-1 font-semibold text-emerald-800">
                            <CheckCircle2 className="h-3 w-3" />
                            Linked case
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 rounded bg-amber-100 px-2 py-1 font-semibold text-amber-800">
                            <ShieldAlert className="h-3 w-3" />
                            Missing case
                          </span>
                        )}
                        {row.is_public ? (
                          <span className="inline-flex rounded bg-indigo-100 px-2 py-1 font-semibold text-indigo-800">Public</span>
                        ) : null}
                        <span
                          className={`inline-flex rounded px-2 py-1 font-semibold ${
                            publicationStatus === "published"
                              ? "bg-cyan-100 text-cyan-800"
                              : publicationStatus === "revoked"
                                ? "bg-rose-100 text-rose-800"
                                : "bg-slate-100 text-slate-700"
                          }`}
                        >
                          Publication: {publicationLabel(publicationStatus)}
                        </span>
                      </div>
                      <p className="mt-2 text-xs text-slate-700">
                        Campaign: {campaign ? campaign.name : "Not linked"}{" "}
                        {campaign?.exercise_type ? `(${campaign.exercise_type})` : ""}
                      </p>
                      <p className="text-xs text-slate-700">
                        Approval template: {template ? template.name : "Not configured"}
                        {templateStages.length > 0
                          ? ` | Stages: ${templateStages.map((item) => `${item.order}. ${item.name}`).join(", ")}`
                          : ""}
                      </p>
                      <p className="text-xs text-slate-700">Approval chain status: {approvalChainStatus}</p>
                    </div>
                    {canEnsureLinkage ? (
                      <Button
                        type="button"
                        variant="outline"
                        onClick={() => void handleEnsureLinkage(row)}
                        disabled={isRowBusy}
                      >
                        <Clock3 className="mr-2 h-4 w-4" />
                        {isLinkageLoading ? "Linking..." : "Ensure Linkage"}
                      </Button>
                    ) : (
                      <span className="text-xs text-slate-700">
                        Linkage actions are restricted to authorized stage actors.
                      </span>
                    )}
                  </div>

                  <div className="mt-4 rounded-lg border border-slate-200 bg-slate-50 p-3">
                    <div className="mb-3 flex items-center gap-2">
                      <Workflow className="h-4 w-4 text-indigo-700" />
                      <p className="text-sm font-semibold text-slate-900">Lifecycle and Stage Action</p>
                    </div>

                    {canManageLifecycle ? (
                      <div className="grid gap-3 lg:grid-cols-2">
                        <div>
                          <label htmlFor={`target-status-${row.id}`} className="mb-1 block text-xs font-semibold uppercase text-slate-700">Target Status</label>
                          <select
                            id={`target-status-${row.id}`}
                            className={SELECT_FIELD_CLASS}
                            value={statusTarget}
                            onChange={(event) => {
                              const nextStatus = event.target.value as AppointmentStatus;
                              setRowActionStatus((previous) => ({ ...previous, [row.id]: nextStatus }));
                              const nextStages = getStageChoicesForRow(row, nextStatus);
                              setRowActionStageId((previous) => {
                                const current = previous[row.id];
                                if (nextStages.length === 0) {
                                  return { ...previous, [row.id]: "" };
                                }
                                if (current && nextStages.some((item) => item.id === current)) {
                                  return previous;
                                }
                                return { ...previous, [row.id]: nextStages[0].id };
                              });
                            }}
                          >
                            {lifecycleOptions.map((status) => (
                              <option key={status} value={status}>
                                {statusLabel(status)}
                              </option>
                            ))}
                          </select>
                        </div>

                        <div>
                          <label htmlFor={`stage-${row.id}`}  className="mb-1 block text-xs font-semibold uppercase text-slate-700">Approval Stage</label>
                          <select
                            id={`stage-${row.id}`}  
                            className={SELECT_FIELD_CLASS}
                            value={selectedStageId}
                            disabled={stageChoices.length === 0}
                            onChange={(event) =>
                              setRowActionStageId((previous) => ({
                                ...previous,
                                [row.id]: event.target.value,
                              }))
                            }
                          >
                            {stageChoices.length === 0 ? (
                              <option value="">No mapped stage for selected transition</option>
                            ) : (
                              stageChoices.map((stage) => (
                                <option key={stage.id} value={stage.id}>
                                  {stage.order}. {stage.name} ({stage.required_role})
                                </option>
                              ))
                            )}
                          </select>
                        </div>

                        <div>
                          <label htmlFor={`intent-${row.id}`} className="mb-1 block text-xs font-semibold uppercase text-slate-700">Action Intent</label>
                          <select
                            className={SELECT_FIELD_CLASS}
                            id={`intent-${row.id}`}
                            value={intent}
                            onChange={(event) =>
                              setRowActionIntent((previous) => ({
                                ...previous,
                                [row.id]: event.target.value as StageActionIntent,
                              }))
                            }
                          >
                            {STAGE_ACTION_INTENT_OPTIONS.map((option) => (
                              <option key={option.value} value={option.value}>
                                {option.label}
                              </option>
                            ))}
                          </select>
                        </div>

                        <div>
                          <label htmlFor={`reason-${row.id}`} className="mb-1 block text-xs font-semibold uppercase text-slate-700">Reason / Note</label>
                          <Input
                            id={`reason-${row.id}`}
                            value={reason}
                            onChange={(event) =>
                              setRowActionReason((previous) => ({
                                ...previous,
                                [row.id]: event.target.value,
                              }))
                            }
                            placeholder="Decision note or rationale"
                          />
                        </div>

                        <div className="lg:col-span-2">
                          <label htmlFor={`evidence-${row.id}`} className="mb-1 block text-xs font-semibold uppercase text-slate-700">
                            Evidence Links (comma or newline separated URLs)
                          </label>
                          <textarea
                            className="min-h-[84px] w-full rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-900"
                            id={`evidence-${row.id}`}
                            value={evidenceInput}
                            onChange={(event) =>
                              setRowActionEvidence((previous) => ({
                                ...previous,
                                [row.id]: event.target.value,
                              }))
                            }
                            placeholder="https://example.gov/document-1, https://example.gov/document-2"
                          />
                        </div>

                        <div className="lg:col-span-2 flex justify-end">
                          <Button
                            type="button"
                            onClick={() => void applyRowStatusAction(row)}
                            disabled={isRowBusy || statusTarget === row.status}
                          >
                            {isAdvanceLoading ? "Updating..." : "Apply Transition"}
                          </Button>
                        </div>
                      </div>
                    ) : (
                      <p className="text-xs text-slate-700">
                        {rowOutOfScope
                          ? "This record is outside the active organization scope."
                          : "Stage transition controls are restricted to authorized stage actors."}
                      </p>
                    )}
                  </div>

                  <div className="mt-4 rounded-lg border border-slate-200 bg-white p-3">
                    <div className="mb-3 flex items-center gap-2">
                      <Stamp className="h-4 w-4 text-cyan-700" />
                      <p className="text-sm font-semibold text-slate-900">Publication and Gazette</p>
                    </div>
                    <div className="mb-3 flex flex-wrap items-center gap-2 text-xs text-slate-700">
                      <span className="rounded bg-slate-100 px-2 py-1 font-semibold text-slate-700">
                        Status: {publicationLabel(publicationStatus)}
                      </span>
                      {publication?.published_at ? (
                        <span className="rounded bg-cyan-100 px-2 py-1 font-semibold text-cyan-800">
                          Published {new Date(publication.published_at).toLocaleString()}
                        </span>
                      ) : null}
                      {publication?.revoked_at ? (
                        <span className="rounded bg-rose-100 px-2 py-1 font-semibold text-rose-800">
                          Revoked {new Date(publication.revoked_at).toLocaleString()}
                        </span>
                      ) : null}
                    </div>

                    {canManagePublication ? (
                      <div className="grid gap-3 lg:grid-cols-2">
                        <div>
                          <label htmlFor={`publishDraft.publication_reference-${row.id}`} className="mb-1 block text-xs font-semibold uppercase text-slate-700">Publication Reference</label>
                          <Input
                            id={`publishDraft.publication_reference-${row.id}`}
                            value={publishDraft.publication_reference ?? publication?.publication_reference ?? ""}
                            onChange={(event) => setPublishDraftField(row.id, "publication_reference", event.target.value)}
                            placeholder="Gazette reference number"
                          />
                        </div>
                        <div>
                          <label htmlFor={`publishDraft.publication_document_hash-${row.id}`} className="mb-1 block text-xs font-semibold uppercase text-slate-700">Document Hash</label>
                          <Input
                            id={`publishDraft.publication_document_hash-${row.id}`}
                            value={publishDraft.publication_document_hash ?? publication?.publication_document_hash ?? ""}
                            onChange={(event) => setPublishDraftField(row.id, "publication_document_hash", event.target.value)}
                            placeholder="sha256/sha512 hash"
                          />
                        </div>
                        <div>
                          <label htmlFor={`publishDraft.gazette_number-${row.id}`} className="mb-1 block text-xs font-semibold uppercase text-slate-700">Gazette Number</label>
                          <Input
                            id={`publishDraft.gazette_number-${row.id}`}
                            value={publishDraft.gazette_number ?? row.gazette_number ?? ""}
                            onChange={(event) => setPublishDraftField(row.id, "gazette_number", event.target.value)}
                            placeholder="Official gazette number"
                          />
                        </div>
                        <div>
                          <label htmlFor={`publishDraft.gazette_date-${row.id}`} className="mb-1 block text-xs font-semibold uppercase text-slate-700">Gazette Date</label>
                          <Input
                            id={`publishDraft.gazette_date-${row.id}`}
                            type="date"
                            value={publishDraft.gazette_date ?? row.gazette_date ?? ""}
                            onChange={(event) => setPublishDraftField(row.id, "gazette_date", event.target.value)}
                          />
                        </div>
                        <div className="lg:col-span-2">
                          <label htmlFor={`publishDraft.publication_notes-${row.id}`} className="mb-1 block text-xs font-semibold uppercase text-slate-700">Publication Notes</label>
                          <Input
                            id={`publishDraft.publication_notes-${row.id}`}
                            value={publishDraft.publication_notes ?? publication?.publication_notes ?? ""}
                            onChange={(event) => setPublishDraftField(row.id, "publication_notes", event.target.value)}
                            placeholder="Reference notes (public-safe)"
                          />
                        </div>
                        <div className="lg:col-span-2 flex flex-wrap justify-end gap-2">
                          <Button
                            type="button"
                            variant="outline"
                            onClick={() => void handlePublish(row)}
                            disabled={isRowBusy}
                          >
                            {isPublishLoading
                              ? "Publishing..."
                              : publicationStatus === "published"
                                ? "Update Publication"
                                : "Publish Appointment"}
                          </Button>
                        </div>
                      </div>
                    ) : null}

                    {canManagePublication && publicationStatus === "published" ? (
                      <div className="mt-3 grid gap-2 rounded-md border border-rose-200 bg-rose-50 p-3 lg:grid-cols-2">
                        <div className="lg:col-span-2">
                          <label htmlFor={`revocation-reason-${row.id}`} className="mb-1 block text-xs font-semibold uppercase text-rose-700">Revocation Reason</label>
                          <Input
                            id={`revocation-reason-${row.id}`}
                            value={revokeDraft.reason}
                            onChange={(event) => setRevokeDraft(row.id, { reason: event.target.value })}
                            placeholder="Regulatory correction or legal reason"
                          />
                        </div>
                        <label className="inline-flex items-center gap-2 text-sm text-rose-800">
                          <input
                            type="checkbox"
                            checked={revokeDraft.make_private}
                            onChange={(event) => setRevokeDraft(row.id, { make_private: event.target.checked })}
                          />
                          Make record private after revocation
                        </label>
                        <div className="flex justify-end">
                          <Button
                            type="button"
                            variant="outline"
                            onClick={() => void handleRevoke(row)}
                            disabled={isRowBusy}
                          >
                            {isRevokeLoading ? "Revoking..." : "Revoke Publication"}
                          </Button>
                        </div>
                      </div>
                    ) : null}

                    {publicationStatus === "revoked" ? (
                      <p className="mt-3 text-xs text-rose-700">
                        Revoked by {publication?.revoked_by_email || publication?.revoked_by || "system"}.
                        {isAdmin && publication?.revocation_reason ? ` Reason: ${publication.revocation_reason}` : ""}
                      </p>
                    ) : null}
                  </div>

                  {canViewStageActions ? (
                    <div className="mt-4">
                      <button
                        type="button"
                        className="text-sm font-semibold text-indigo-700 hover:text-indigo-800"
                        onClick={() => void handleToggleActions(row)}
                      >
                        {actionsOpen ? "Hide stage actions" : "Show stage actions"}
                      </button>
                      {actionsOpen ? (
                        <div className="mt-2 rounded-lg border border-slate-200 bg-slate-50 p-3">
                          {itemActions.length === 0 ? (
                            <p className="text-xs text-slate-700">No stage actions available yet.</p>
                          ) : (
                            <ul className="space-y-2 text-xs text-slate-800">
                              {itemActions.map((item) => (
                                <li key={item.id} className="rounded border border-slate-200 bg-white p-2">
                                  <p className="font-semibold">
                                    {humanizeCode(item.previous_status)}
                                    {" -> "}
                                    {humanizeCode(item.new_status)}
                                  </p>
                                  <p>Stage: {item.stage_name || "No explicit stage"}</p>
                                  <p>Actor: {item.actor_email || item.actor}</p>
                                  <p>Role: {item.actor_role}</p>
                                  <p>At: {new Date(item.acted_at).toLocaleString()}</p>
                                  {isAdmin && item.reason_note ? <p>Internal note: {item.reason_note}</p> : null}
                                </li>
                              ))}
                            </ul>
                          )}
                        </div>
                      ) : null}
                    </div>
                  ) : null}
                </article>
              );
            })}
          </div>
        )}
      </section>
    </main>
  );
};

export default AppointmentsRegistryPage;

