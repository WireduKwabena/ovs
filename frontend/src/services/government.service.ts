import api from "./api";
import type {
  ApprovalStage,
  ApprovalStageTemplate,
  AppointmentPublication,
  AppointmentRecord,
  AppointmentStageAction,
  AppointmentStatus,
  GovernmentPosition,
  PaginatedResponse,
  PersonnelRecord,
  PublicAppointmentRecord,
  PublicTransparencyOfficeholder,
  PublicTransparencyPosition,
  PublicTransparencySummary,
  VettingCampaign,
} from "@/types";

type ResultEnvelope<T> = PaginatedResponse<T> | T[];
const RECENT_AUTH_REQUIRED_CODE = "RECENT_AUTH_REQUIRED";

export interface AppointmentAdvancePayload {
  status: AppointmentStatus;
  stage_id?: string;
  reason_note?: string;
  evidence_links?: string[];
}

export interface AppointmentPublishPayload {
  publication_reference?: string;
  publication_document_hash?: string;
  publication_notes?: string;
  gazette_number?: string;
  gazette_date?: string;
}

export interface AppointmentRevokePayload {
  revocation_reason: string;
  make_private?: boolean;
}

function extractResults<T>(payload: ResultEnvelope<T>): T[] {
  if (Array.isArray(payload)) {
    return payload;
  }
  return Array.isArray(payload.results) ? payload.results : [];
}

type ServiceErrorShape = {
  message: string;
  code: string | null;
  status: number | null;
  details: unknown;
};

export class GovernmentServiceError extends Error {
  code: string | null;
  status: number | null;
  details: unknown;

  constructor(payload: ServiceErrorShape) {
    super(payload.message);
    this.name = "GovernmentServiceError";
    this.code = payload.code;
    this.status = payload.status;
    this.details = payload.details;
  }
}

function normalizeCode(value: unknown): string | null {
  if (typeof value !== "string") {
    return null;
  }
  const normalized = value.trim().toUpperCase();
  return normalized || null;
}

function extractErrorCode(raw: unknown): string | null {
  if (!raw || typeof raw !== "object") {
    return null;
  }
  const payload = raw as Record<string, unknown>;
  const fromTopLevel = normalizeCode(payload.code);
  if (fromTopLevel) {
    return fromTopLevel;
  }

  const detail = payload.detail;
  if (detail && typeof detail === "object" && !Array.isArray(detail)) {
    const nested = normalizeCode((detail as Record<string, unknown>).code);
    if (nested) {
      return nested;
    }
  }
  return null;
}

function extractErrorMessage(raw: unknown, fallback: string): string {
  if (!raw || typeof raw !== "object") {
    return fallback;
  }
  const payload = raw as Record<string, unknown>;

  if (typeof payload.error === "string" && payload.error.trim()) {
    return payload.error.trim();
  }
  if (typeof payload.detail === "string" && payload.detail.trim()) {
    return payload.detail.trim();
  }
  if (Array.isArray(payload.detail) && typeof payload.detail[0] === "string") {
    return payload.detail[0];
  }
  if (typeof payload.message === "string" && payload.message.trim()) {
    return payload.message.trim();
  }
  if (Array.isArray(raw) && typeof raw[0] === "string") {
    return raw[0];
  }
  return fallback;
}

function toServiceError(error: unknown, fallback: string): GovernmentServiceError {
  if (error instanceof GovernmentServiceError) {
    return error;
  }

  if (typeof error !== "object" || error === null) {
    return new GovernmentServiceError({
      message: fallback,
      code: null,
      status: null,
      details: null,
    });
  }

  const maybeResponse = (error as { response?: { data?: unknown; status?: number } }).response;
  const responsePayload = maybeResponse?.data;
  const message = extractErrorMessage(responsePayload, (error as { message?: string }).message || fallback);
  const code = extractErrorCode(responsePayload);
  const status = typeof maybeResponse?.status === "number" ? maybeResponse.status : null;

  return new GovernmentServiceError({
    message,
    code,
    status,
    details: responsePayload,
  });
}

export function isRecentAuthRequiredError(error: unknown): boolean {
  if (error instanceof GovernmentServiceError && error.code === RECENT_AUTH_REQUIRED_CODE) {
    return true;
  }
  if (typeof error === "object" && error !== null) {
    const maybeCode = normalizeCode((error as { code?: unknown }).code);
    if (maybeCode === RECENT_AUTH_REQUIRED_CODE) {
      return true;
    }
    const responseCode = extractErrorCode(
      (error as { response?: { data?: unknown } }).response?.data,
    );
    if (responseCode === RECENT_AUTH_REQUIRED_CODE) {
      return true;
    }
  }
  const message = error instanceof Error ? error.message.toUpperCase() : "";
  return message.includes(RECENT_AUTH_REQUIRED_CODE);
}

export const governmentService = {
  async listPositions(params?: {
    branch?: string;
    is_vacant?: boolean;
    is_public?: boolean;
    search?: string;
  }): Promise<GovernmentPosition[]> {
    try {
      const response = await api.get<ResultEnvelope<GovernmentPosition>>("/positions/", { params });
      return extractResults(response.data);
    } catch (error) {
      throw toServiceError(error, "Failed to fetch government positions.");
    }
  },

  async createPosition(payload: Partial<GovernmentPosition>): Promise<GovernmentPosition> {
    try {
      const response = await api.post<GovernmentPosition>("/positions/", payload);
      return response.data;
    } catch (error) {
      throw toServiceError(error, "Failed to create government position.");
    }
  },

  async listPersonnel(params?: {
    is_active_officeholder?: boolean;
    is_public?: boolean;
    search?: string;
  }): Promise<PersonnelRecord[]> {
    try {
      const response = await api.get<ResultEnvelope<PersonnelRecord>>("/personnel/", { params });
      return extractResults(response.data);
    } catch (error) {
      throw toServiceError(error, "Failed to fetch personnel records.");
    }
  },

  async createPersonnel(payload: Partial<PersonnelRecord>): Promise<PersonnelRecord> {
    try {
      const response = await api.post<PersonnelRecord>("/personnel/", payload);
      return response.data;
    } catch (error) {
      throw toServiceError(error, "Failed to create personnel record.");
    }
  },

  async listAppointments(params?: {
    status?: string;
    is_public?: boolean;
    position?: string;
    nominee?: string;
    search?: string;
  }): Promise<AppointmentRecord[]> {
    try {
      const response = await api.get<ResultEnvelope<AppointmentRecord>>("/appointments/records/", { params });
      return extractResults(response.data);
    } catch (error) {
      throw toServiceError(error, "Failed to fetch appointment records.");
    }
  },

  async createAppointment(payload: {
    position: string;
    nominee: string;
    appointment_exercise?: string | null;
    nominated_by_display: string;
    nominated_by_org?: string;
    nomination_date: string;
    is_public?: boolean;
  }): Promise<AppointmentRecord> {
    try {
      const response = await api.post<AppointmentRecord>("/appointments/records/", payload);
      return response.data;
    } catch (error) {
      throw toServiceError(error, "Failed to create appointment record.");
    }
  },

  async listApprovalStageTemplates(params?: {
    exercise_type?: string;
    search?: string;
  }): Promise<ApprovalStageTemplate[]> {
    try {
      const response = await api.get<ResultEnvelope<ApprovalStageTemplate>>("/appointments/stage-templates/", { params });
      return extractResults(response.data);
    } catch (error) {
      throw toServiceError(error, "Failed to fetch approval stage templates.");
    }
  },

  async createApprovalStageTemplate(payload: {
    name: string;
    exercise_type: string;
  }): Promise<ApprovalStageTemplate> {
    try {
      const response = await api.post<ApprovalStageTemplate>("/appointments/stage-templates/", payload);
      return response.data;
    } catch (error) {
      throw toServiceError(error, "Failed to create approval stage template.");
    }
  },

  async listApprovalStages(params?: {
    template?: string;
    maps_to_status?: AppointmentStatus;
    required_role?: string;
    is_required?: boolean;
    search?: string;
  }): Promise<ApprovalStage[]> {
    try {
      const response = await api.get<ResultEnvelope<ApprovalStage>>("/appointments/stages/", { params });
      return extractResults(response.data);
    } catch (error) {
      throw toServiceError(error, "Failed to fetch approval stages.");
    }
  },

  async createApprovalStage(payload: {
    template: string;
    order: number;
    name: string;
    required_role: string;
    is_required?: boolean;
    maps_to_status: AppointmentStatus;
  }): Promise<ApprovalStage> {
    try {
      const response = await api.post<ApprovalStage>("/appointments/stages/", payload);
      return response.data;
    } catch (error) {
      throw toServiceError(error, "Failed to create approval stage.");
    }
  },

  async advanceAppointmentStage(appointmentId: string, payload: AppointmentAdvancePayload): Promise<AppointmentRecord> {
    try {
      const response = await api.post<AppointmentRecord>(
        `/appointments/records/${appointmentId}/advance-stage/`,
        payload,
      );
      return response.data;
    } catch (error) {
      throw toServiceError(error, "Failed to advance appointment stage.");
    }
  },

  async appoint(
    appointmentId: string,
    payload?: {
      stage_id?: string;
      reason_note?: string;
      evidence_links?: string[];
    },
  ): Promise<AppointmentRecord> {
    try {
      const response = await api.post<AppointmentRecord>(
        `/appointments/records/${appointmentId}/appoint/`,
        {
          stage_id: payload?.stage_id,
          reason_note: payload?.reason_note || "",
          evidence_links: payload?.evidence_links || [],
        },
      );
      return response.data;
    } catch (error) {
      throw toServiceError(error, "Failed to finalize appointment.");
    }
  },

  async reject(
    appointmentId: string,
    payload?: {
      stage_id?: string;
      reason_note?: string;
      evidence_links?: string[];
    },
  ): Promise<AppointmentRecord> {
    try {
      const response = await api.post<AppointmentRecord>(
        `/appointments/records/${appointmentId}/reject/`,
        {
          stage_id: payload?.stage_id,
          reason_note: payload?.reason_note || "",
          evidence_links: payload?.evidence_links || [],
        },
      );
      return response.data;
    } catch (error) {
      throw toServiceError(error, "Failed to reject appointment.");
    }
  },

  async listStageActions(appointmentId: string): Promise<AppointmentStageAction[]> {
    try {
      const response = await api.get<AppointmentStageAction[]>(`/appointments/records/${appointmentId}/stage-actions/`);
      return Array.isArray(response.data) ? response.data : [];
    } catch (error) {
      throw toServiceError(error, "Failed to fetch stage actions.");
    }
  },

  async getAppointmentPublication(appointmentId: string): Promise<AppointmentPublication> {
    try {
      const response = await api.get<AppointmentPublication>(`/appointments/records/${appointmentId}/publication/`);
      return response.data;
    } catch (error) {
      throw toServiceError(error, "Failed to fetch appointment publication state.");
    }
  },

  async publishAppointment(
    appointmentId: string,
    payload: AppointmentPublishPayload = {},
  ): Promise<AppointmentPublication> {
    try {
      const response = await api.post<AppointmentPublication>(`/appointments/records/${appointmentId}/publish/`, payload);
      return response.data;
    } catch (error) {
      throw toServiceError(error, "Failed to publish appointment.");
    }
  },

  async revokeAppointmentPublication(
    appointmentId: string,
    payload: AppointmentRevokePayload,
  ): Promise<AppointmentPublication> {
    try {
      const response = await api.post<AppointmentPublication>(
        `/appointments/records/${appointmentId}/revoke-publication/`,
        payload,
      );
      return response.data;
    } catch (error) {
      throw toServiceError(error, "Failed to revoke appointment publication.");
    }
  },

  async listPublicGazetteFeed(): Promise<PublicAppointmentRecord[]> {
    try {
      const response = await api.get<PublicAppointmentRecord[]>("/appointments/records/gazette-feed/");
      return Array.isArray(response.data) ? response.data : [];
    } catch (error) {
      throw toServiceError(error, "Failed to fetch gazette feed.");
    }
  },

  async listPublicOpenAppointments(): Promise<PublicAppointmentRecord[]> {
    try {
      const response = await api.get<PublicAppointmentRecord[]>("/appointments/records/open/");
      return Array.isArray(response.data) ? response.data : [];
    } catch (error) {
      throw toServiceError(error, "Failed to fetch open appointments feed.");
    }
  },

  async getPublicTransparencySummary(): Promise<PublicTransparencySummary> {
    try {
      const response = await api.get<PublicTransparencySummary>("/public/transparency/summary/");
      return response.data;
    } catch (error) {
      throw toServiceError(error, "Failed to fetch transparency summary.");
    }
  },

  async listPublicTransparencyAppointments(params?: {
    search?: string;
    status?: string;
    ordering?: string;
  }): Promise<PublicAppointmentRecord[]> {
    try {
      const response = await api.get<PublicAppointmentRecord[]>("/public/transparency/appointments/", { params });
      return Array.isArray(response.data) ? response.data : [];
    } catch (error) {
      throw toServiceError(error, "Failed to fetch published appointments.");
    }
  },

  async listPublicTransparencyGazetteFeed(params?: {
    search?: string;
    status?: string;
    ordering?: string;
  }): Promise<PublicAppointmentRecord[]> {
    try {
      const response = await api.get<PublicAppointmentRecord[]>("/public/transparency/appointments/gazette-feed/", {
        params,
      });
      return Array.isArray(response.data) ? response.data : [];
    } catch (error) {
      throw toServiceError(error, "Failed to fetch public gazette feed.");
    }
  },

  async getPublicTransparencyAppointmentDetail(appointmentId: string): Promise<PublicAppointmentRecord> {
    try {
      const response = await api.get<PublicAppointmentRecord>(`/public/transparency/appointments/${appointmentId}/`);
      return response.data;
    } catch (error) {
      throw toServiceError(error, "Failed to fetch published appointment detail.");
    }
  },

  async listPublicTransparencyOpenAppointments(params?: {
    search?: string;
    status?: string;
    ordering?: string;
  }): Promise<PublicAppointmentRecord[]> {
    try {
      const response = await api.get<PublicAppointmentRecord[]>("/public/transparency/appointments/open/", { params });
      return Array.isArray(response.data) ? response.data : [];
    } catch (error) {
      throw toServiceError(error, "Failed to fetch open transparency appointments.");
    }
  },

  async listPublicTransparencyPositions(): Promise<PublicTransparencyPosition[]> {
    try {
      const response = await api.get<PublicTransparencyPosition[]>("/public/transparency/positions/");
      return Array.isArray(response.data) ? response.data : [];
    } catch (error) {
      throw toServiceError(error, "Failed to fetch public positions.");
    }
  },

  async listPublicTransparencyVacantPositions(): Promise<PublicTransparencyPosition[]> {
    try {
      const response = await api.get<PublicTransparencyPosition[]>("/public/transparency/positions/vacant/");
      return Array.isArray(response.data) ? response.data : [];
    } catch (error) {
      throw toServiceError(error, "Failed to fetch vacant public positions.");
    }
  },

  async listPublicTransparencyOfficeholders(): Promise<PublicTransparencyOfficeholder[]> {
    try {
      const response = await api.get<PublicTransparencyOfficeholder[]>("/public/transparency/officeholders/");
      return Array.isArray(response.data) ? response.data : [];
    } catch (error) {
      throw toServiceError(error, "Failed to fetch public officeholders.");
    }
  },

  async ensureVettingLinkage(appointmentId: string): Promise<AppointmentRecord> {
    try {
      const response = await api.post<AppointmentRecord>(`/appointments/records/${appointmentId}/ensure-vetting-linkage/`);
      return response.data;
    } catch (error) {
      throw toServiceError(error, "Failed to ensure vetting linkage.");
    }
  },

  async listCampaignsForAppointments(): Promise<VettingCampaign[]> {
    try {
      const response = await api.get<ResultEnvelope<VettingCampaign>>("/campaigns/");
      return extractResults(response.data);
    } catch (error) {
      throw toServiceError(error, "Failed to fetch campaign options.");
    }
  },
};
