import api from "./api";
import type {
  AppointmentRecord,
  AppointmentStageAction,
  GovernmentPosition,
  PaginatedResponse,
  PersonnelRecord,
  VettingCampaign,
} from "@/types";

type ResultEnvelope<T> = PaginatedResponse<T> | T[];

interface AppointmentAdvancePayload {
  status: string;
  stage_id?: string;
  reason_note?: string;
  evidence_links?: string[];
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

  async appoint(appointmentId: string, reason_note?: string): Promise<AppointmentRecord> {
    try {
      const response = await api.post<AppointmentRecord>(
        `/appointments/records/${appointmentId}/appoint/`,
        { reason_note: reason_note || "" },
      );
      return response.data;
    } catch (error) {
      throw new Error(toErrorMessage(error, "Failed to finalize appointment."));
    }
  },

  async reject(appointmentId: string, reason_note?: string): Promise<AppointmentRecord> {
    try {
      const response = await api.post<AppointmentRecord>(
        `/appointments/records/${appointmentId}/reject/`,
        { reason_note: reason_note || "" },
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
