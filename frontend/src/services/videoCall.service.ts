import api from "./api";
import type {
  ApiError,
  PaginatedResponse,
  VideoMeeting,
  VideoMeetingCreatePayload,
  VideoMeetingEvent,
  VideoMeetingJoinToken,
  VideoMeetingSeriesCancelPayload,
  VideoMeetingSeriesPayload,
  VideoMeetingSeriesReschedulePayload,
  VideoMeetingSeriesResponse,
  VideoMeetingReschedulePayload,
  VideoMeetingReminderHealth,
} from "@/types";

const extractResults = <T>(payload: PaginatedResponse<T> | T[]): T[] => {
  if (Array.isArray(payload)) {
    return payload;
  }
  return Array.isArray(payload.results) ? payload.results : [];
};

const toMessage = (error: unknown, fallback: string): string => {
  const response = (error as { response?: { status?: number; data?: ApiError & { detail?: string; non_field_errors?: string[] } } })?.response;
  const responseData = response?.data;
  if (!responseData) {
    const genericMessage = (error as { message?: string })?.message;
    return typeof genericMessage === "string" && genericMessage.trim() ? genericMessage : fallback;
  }
  if (typeof responseData.detail === "string" && responseData.detail.trim()) {
    return responseData.detail;
  }
  if (Array.isArray(responseData.non_field_errors) && responseData.non_field_errors.length > 0) {
    return responseData.non_field_errors.join(" ");
  }
  if (response?.status === 401) {
    return "Session expired or unauthorized. Please sign in again.";
  }
  if (response?.status === 403 && fallback.toLowerCase().includes("reminder health")) {
    return "Reminder runtime is available to admin accounts only.";
  }
  if (response?.status === 403) {
    return "You do not have permission to view this resource.";
  }
  if (response?.status === 404 && fallback.toLowerCase().includes("reminder health")) {
    return "Reminder health endpoint unavailable. Restart backend services to load latest routes.";
  }
  return (
    responseData.message ||
    (responseData as { error?: string }).error ||
    fallback
  );
};

export const videoCallService = {
  async list(params?: {
    status?: string;
  }): Promise<VideoMeeting[]> {
    try {
      const response = await api.get<PaginatedResponse<VideoMeeting> | VideoMeeting[]>(
        "/video-calls/meetings/",
        { params },
      );
      return extractResults(response.data);
    } catch (error) {
      throw new Error(toMessage(error, "Failed to fetch meetings."));
    }
  },

  async listUpcoming(): Promise<VideoMeeting[]> {
    try {
      const response = await api.get<VideoMeeting[]>("/video-calls/meetings/upcoming/");
      return response.data;
    } catch (error) {
      throw new Error(toMessage(error, "Failed to fetch upcoming meetings."));
    }
  },

  async getById(meetingId: string): Promise<VideoMeeting> {
    try {
      const response = await api.get<VideoMeeting>(`/video-calls/meetings/${meetingId}/`);
      return response.data;
    } catch (error) {
      throw new Error(toMessage(error, "Failed to fetch meeting details."));
    }
  },

  async create(payload: VideoMeetingCreatePayload): Promise<VideoMeeting> {
    try {
      const response = await api.post<VideoMeeting>("/video-calls/meetings/", payload);
      return response.data;
    } catch (error) {
      throw new Error(toMessage(error, "Failed to schedule video meeting."));
    }
  },

  async scheduleSeries(payload: VideoMeetingSeriesPayload): Promise<VideoMeetingSeriesResponse> {
    try {
      const response = await api.post<VideoMeetingSeriesResponse>("/video-calls/meetings/schedule-series/", payload);
      return response.data;
    } catch (error) {
      throw new Error(toMessage(error, "Failed to schedule recurring meetings."));
    }
  },

  async update(meetingId: string, payload: Partial<VideoMeetingCreatePayload>): Promise<VideoMeeting> {
    try {
      const response = await api.patch<VideoMeeting>(`/video-calls/meetings/${meetingId}/`, payload);
      return response.data;
    } catch (error) {
      throw new Error(toMessage(error, "Failed to update meeting."));
    }
  },

  async reschedule(meetingId: string, payload: VideoMeetingReschedulePayload): Promise<VideoMeeting> {
    try {
      const response = await api.post<VideoMeeting>(`/video-calls/meetings/${meetingId}/reschedule/`, payload);
      return response.data;
    } catch (error) {
      throw new Error(toMessage(error, "Failed to reschedule meeting."));
    }
  },

  async rescheduleSeries(
    meetingId: string,
    payload: VideoMeetingSeriesReschedulePayload,
  ): Promise<VideoMeetingSeriesResponse> {
    try {
      const response = await api.post<VideoMeetingSeriesResponse>(
        `/video-calls/meetings/${meetingId}/reschedule-series/`,
        payload,
      );
      return response.data;
    } catch (error) {
      throw new Error(toMessage(error, "Failed to reschedule meeting series."));
    }
  },

  async extend(meetingId: string, minutes: number): Promise<VideoMeeting> {
    try {
      const response = await api.post<VideoMeeting>(`/video-calls/meetings/${meetingId}/extend/`, { minutes });
      return response.data;
    } catch (error) {
      throw new Error(toMessage(error, "Failed to extend meeting."));
    }
  },

  async cancel(meetingId: string, reason?: string): Promise<VideoMeeting> {
    try {
      const response = await api.post<VideoMeeting>(`/video-calls/meetings/${meetingId}/cancel/`, { reason });
      return response.data;
    } catch (error) {
      throw new Error(toMessage(error, "Failed to cancel meeting."));
    }
  },

  async cancelSeries(
    meetingId: string,
    payload: VideoMeetingSeriesCancelPayload,
  ): Promise<VideoMeetingSeriesResponse> {
    try {
      const response = await api.post<VideoMeetingSeriesResponse>(
        `/video-calls/meetings/${meetingId}/cancel-series/`,
        payload,
      );
      return response.data;
    } catch (error) {
      throw new Error(toMessage(error, "Failed to cancel meeting series."));
    }
  },

  async start(meetingId: string): Promise<VideoMeeting> {
    try {
      const response = await api.post<VideoMeeting>(`/video-calls/meetings/${meetingId}/start/`, {});
      return response.data;
    } catch (error) {
      throw new Error(toMessage(error, "Failed to start meeting."));
    }
  },

  async complete(meetingId: string): Promise<VideoMeeting> {
    try {
      const response = await api.post<VideoMeeting>(`/video-calls/meetings/${meetingId}/complete/`, {});
      return response.data;
    } catch (error) {
      throw new Error(toMessage(error, "Failed to complete meeting."));
    }
  },

  async getJoinToken(meetingId: string): Promise<VideoMeetingJoinToken> {
    try {
      const response = await api.get<VideoMeetingJoinToken>(`/video-calls/meetings/${meetingId}/join-token/`);
      return response.data;
    } catch (error) {
      throw new Error(toMessage(error, "Failed to generate join token."));
    }
  },

  async downloadCalendarIcs(meetingId: string): Promise<Blob> {
    try {
      const response = await api.get<Blob>(`/video-calls/meetings/${meetingId}/calendar-ics/`, {
        responseType: "blob",
      });
      return response.data;
    } catch (error) {
      throw new Error(toMessage(error, "Failed to download calendar file."));
    }
  },

  async listEvents(meetingId: string, options?: { includeSeries?: boolean; limit?: number }): Promise<VideoMeetingEvent[]> {
    try {
      const params = {
        series: options?.includeSeries ?? true ? "1" : "0",
        limit: options?.limit ?? 50,
      };
      const response = await api.get<VideoMeetingEvent[]>(`/video-calls/meetings/${meetingId}/events/`, { params });
      return response.data;
    } catch (error) {
      throw new Error(toMessage(error, "Failed to fetch meeting history."));
    }
  },

  async leave(meetingId: string): Promise<void> {
    try {
      await api.post(`/video-calls/meetings/${meetingId}/leave/`, {});
    } catch (error) {
      throw new Error(toMessage(error, "Failed to leave meeting."));
    }
  },

  async getReminderHealth(): Promise<VideoMeetingReminderHealth> {
    try {
      const response = await api.get<VideoMeetingReminderHealth>("/video-calls/meetings/reminder-health/");
      return response.data;
    } catch (error) {
      throw new Error(toMessage(error, "Failed to fetch reminder health."));
    }
  },
};
