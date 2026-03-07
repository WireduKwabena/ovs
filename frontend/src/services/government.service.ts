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
  VettingCampaign,
} from "@/types";

type ResultEnvelope<T> = PaginatedResponse<T> | T[];

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

function toErrorMessage(error: unknown, fallback: string): string {
  if (typeof error !== "object" || error === null) {
    return fallback;
  }
  const maybeResponse = (error as any).response?.data;
  if (!maybeResponse) {
    return (error as any).message || fallback;
  }
  if (typeof maybeResponse.error === "string") {
    return maybeResponse.error;
  }
  if (typeof maybeResponse.detail === "string") {
    return maybeResponse.detail;
  }
  if (Array.isArray(maybeResponse) && typeof maybeResponse[0] === "string") {
    return maybeResponse[0];
  }
  if (typeof maybeResponse.message === "string") {
    return maybeResponse.message;
  }
  if (typeof maybeResponse.code === "string") {
    return maybeResponse.code;
  }
  return (error as any).message || fallback;
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
      throw new Error(toErrorMessage(error, "Failed to fetch government positions."));
    }
  },

  async createPosition(payload: Partial<GovernmentPosition>): Promise<GovernmentPosition> {
    try {
      const response = await api.post<GovernmentPosition>("/positions/", payload);
      return response.data;
    } catch (error) {
      throw new Error(toErrorMessage(error, "Failed to create government position."));
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
      throw new Error(toErrorMessage(error, "Failed to fetch personnel records."));
    }
  },

  async createPersonnel(payload: Partial<PersonnelRecord>): Promise<PersonnelRecord> {
    try {
      const response = await api.post<PersonnelRecord>("/personnel/", payload);
      return response.data;
    } catch (error) {
      throw new Error(toErrorMessage(error, "Failed to create personnel record."));
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
      throw new Error(toErrorMessage(error, "Failed to fetch appointment records."));
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
      throw new Error(toErrorMessage(error, "Failed to create appointment record."));
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
      throw new Error(toErrorMessage(error, "Failed to fetch approval stage templates."));
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
      throw new Error(toErrorMessage(error, "Failed to create approval stage template."));
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
      throw new Error(toErrorMessage(error, "Failed to fetch approval stages."));
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
      throw new Error(toErrorMessage(error, "Failed to create approval stage."));
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
      throw new Error(toErrorMessage(error, "Failed to advance appointment stage."));
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
      throw new Error(toErrorMessage(error, "Failed to finalize appointment."));
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
      throw new Error(toErrorMessage(error, "Failed to reject appointment."));
    }
  },

  async listStageActions(appointmentId: string): Promise<AppointmentStageAction[]> {
    try {
      const response = await api.get<AppointmentStageAction[]>(`/appointments/records/${appointmentId}/stage-actions/`);
      return Array.isArray(response.data) ? response.data : [];
    } catch (error) {
      throw new Error(toErrorMessage(error, "Failed to fetch stage actions."));
    }
  },

  async getAppointmentPublication(appointmentId: string): Promise<AppointmentPublication> {
    try {
      const response = await api.get<AppointmentPublication>(`/appointments/records/${appointmentId}/publication/`);
      return response.data;
    } catch (error) {
      throw new Error(toErrorMessage(error, "Failed to fetch appointment publication state."));
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
      throw new Error(toErrorMessage(error, "Failed to publish appointment."));
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
      throw new Error(toErrorMessage(error, "Failed to revoke appointment publication."));
    }
  },

  async listPublicGazetteFeed(): Promise<PublicAppointmentRecord[]> {
    try {
      const response = await api.get<PublicAppointmentRecord[]>("/appointments/records/gazette-feed/");
      return Array.isArray(response.data) ? response.data : [];
    } catch (error) {
      throw new Error(toErrorMessage(error, "Failed to fetch gazette feed."));
    }
  },

  async listPublicOpenAppointments(): Promise<PublicAppointmentRecord[]> {
    try {
      const response = await api.get<PublicAppointmentRecord[]>("/appointments/records/open/");
      return Array.isArray(response.data) ? response.data : [];
    } catch (error) {
      throw new Error(toErrorMessage(error, "Failed to fetch open appointments feed."));
    }
  },

  async ensureVettingLinkage(appointmentId: string): Promise<AppointmentRecord> {
    try {
      const response = await api.post<AppointmentRecord>(`/appointments/records/${appointmentId}/ensure-vetting-linkage/`);
      return response.data;
    } catch (error) {
      throw new Error(toErrorMessage(error, "Failed to ensure vetting linkage."));
    }
  },

  async listCampaignsForAppointments(): Promise<VettingCampaign[]> {
    try {
      const response = await api.get<ResultEnvelope<VettingCampaign>>("/campaigns/");
      return extractResults(response.data);
    } catch (error) {
      throw new Error(toErrorMessage(error, "Failed to fetch campaign options."));
    }
  },
};
