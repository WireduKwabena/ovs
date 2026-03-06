import axios from 'axios';
import api from './api';
import type { InterrogationFlag } from '@/types/interview.types';

interface StartInterviewResponse {
  session_id: string;
  interrogation_flags: InterrogationFlag[];
  websocket_url: string;
}

interface InterviewSessionRecord {
  id: string;
  session_id: string;
  status: string;
  case: string;
  interrogation_flags?: Array<{
    id?: string | number;
    type?: string;
    severity?: string;
    status?: string;
    context?: string;
    description?: string;
  }>;
}

interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

interface UploadResponsePayload {
  video_path?: string;
}

interface AvatarSessionResponse {
  enabled: boolean;
  token?: string;
  avatar_name?: string;
  voice_id?: string;
  quality?: 'low' | 'medium' | 'high';
  language?: string;
  activity_idle_timeout?: number;
}

interface InterviewQuestionRecord {
  id: string;
  question_text: string;
  question_type: string;
  difficulty: string;
  is_active: boolean;
}

interface InterviewResponseRecord {
  id: string;
  session: string;
  sequence_number: number;
  transcript: string;
  sentiment: string;
}

interface InterviewFeedbackRecord {
  id: string;
  session: string;
  reviewer: string;
  overall_rating: number;
  recommendation: string;
  notes: string;
}

const candidateSessionConfig = { withCredentials: true };

interface InterviewPlaybackPayload {
  [key: string]: unknown;
}

export interface HeyGenAvatarSdkConfig {
  token: string;
  avatarName: string;
  voiceId?: string;
  quality?: 'low' | 'medium' | 'high';
  language?: string;
  activityIdleTimeout?: number;
}

const buildWsBaseUrl = (): string => {
  const explicitBase =
    (import.meta as { env?: Record<string, string> }).env?.VITE_INTERVIEW_WS_URL ||
    (import.meta as { env?: Record<string, string> }).env?.VITE_FASTAPI_WS;

  if (explicitBase) {
    return explicitBase.replace(/\/$/, '');
  }

  const apiUrl =
    (import.meta as { env?: Record<string, string> }).env?.VITE_API_URL || '/api';

  let apiOrigin = 'http://localhost:8000';
  if (/^https?:\/\//i.test(apiUrl)) {
    apiOrigin = new URL(apiUrl).origin;
  } else if (typeof window !== 'undefined' && window.location?.origin) {
    apiOrigin = window.location.origin;
  }

  const wsProtocol = apiOrigin.startsWith('https') ? 'wss' : 'ws';
  return apiOrigin.replace(/^https?/, wsProtocol);
};

const buildSessionWebsocketUrl = (sessionId: string): string =>
  `${buildWsBaseUrl()}/ws/interview/${sessionId}/`;

const normalizeSeverity = (severity?: string): InterrogationFlag['severity'] => {
  if (severity === 'critical' || severity === 'high' || severity === 'medium') {
    return severity;
  }
  return 'low';
};

const normalizeStatus = (status?: string): InterrogationFlag['status'] => {
  if (status === 'pending' || status === 'addressed' || status === 'resolved') {
    return status;
  }
  return 'unresolved';
};

const normalizeFlags = (flags?: InterviewSessionRecord['interrogation_flags']): InterrogationFlag[] => {
  if (!Array.isArray(flags)) {
    return [];
  }

  return flags.map((flag, index) => ({
    id: String(flag.id ?? `flag-${index + 1}`),
    type: flag.type || 'consistency',
    severity: normalizeSeverity(flag.severity),
    context: flag.context || flag.description || 'Potential inconsistency detected.',
    status: normalizeStatus(flag.status),
  }));
};

const toStartResponse = (session: InterviewSessionRecord): StartInterviewResponse => ({
  session_id: session.session_id,
  interrogation_flags: normalizeFlags(session.interrogation_flags),
  websocket_url: buildSessionWebsocketUrl(session.session_id),
});

const getLatestSessionForCase = async (caseIdentifier: string): Promise<InterviewSessionRecord | null> => {
  const response = await api.get<PaginatedResponse<InterviewSessionRecord> | InterviewSessionRecord[]>(
    '/interviews/sessions/',
    { params: { case: caseIdentifier }, ...candidateSessionConfig }
  );
  const sessions = Array.isArray(response.data) ? response.data : response.data.results || [];
  return sessions.length > 0 ? sessions[0] : null;
};

const resolveCasePrimaryKey = async (caseIdentifier: string): Promise<string> => {
  const response = await api.get<{ id: string }>(`/applications/cases/${caseIdentifier}/`, candidateSessionConfig);
  return response.data.id;
};

const ensureInterviewSession = async (applicationId: string): Promise<InterviewSessionRecord> => {
  try {
    const directSessionResponse = await api.get<InterviewSessionRecord>(
      `/interviews/sessions/${applicationId}/`,
      candidateSessionConfig,
    );
    return directSessionResponse.data;
  } catch {
    // Not a direct session lookup; continue with case-based flow.
  }

  let session = await getLatestSessionForCase(applicationId);
  if (session) {
    return session;
  }

  const casePrimaryKey = await resolveCasePrimaryKey(applicationId);
  session = await getLatestSessionForCase(casePrimaryKey);
  if (session) {
    return session;
  }

  const createdSessionResponse = await api.post<InterviewSessionRecord>('/interviews/sessions/', {
    case: casePrimaryKey,
    use_dynamic_questions: true,
  }, candidateSessionConfig);
  return createdSessionResponse.data;
};

export const interviewService = {
  async startInterview(applicationId: string): Promise<StartInterviewResponse> {
    try {
      const legacyResponse = await api.post<StartInterviewResponse>('/interviews/interrogation/start/', {
        application_id: applicationId,
      }, candidateSessionConfig);
      return {
        ...legacyResponse.data,
        websocket_url:
          legacyResponse.data.websocket_url || buildSessionWebsocketUrl(legacyResponse.data.session_id),
      };
    } catch (legacyError) {
      if (axios.isAxiosError(legacyError) && legacyError.response?.status && legacyError.response.status >= 500) {
        throw legacyError;
      }
    }

    const session = await ensureInterviewSession(applicationId);
    let activeSession = session;

    if (session.status === 'created') {
      const startResponse = await api.post<InterviewSessionRecord>(
        `/interviews/sessions/${session.session_id}/start/`,
        {},
        candidateSessionConfig,
      );
      activeSession = startResponse.data;
    }

    return toStartResponse(activeSession);
  },

  async uploadResponse(sessionId: string, videoBlob: Blob): Promise<UploadResponsePayload> {
    const formData = new FormData();
    formData.append('video', videoBlob, 'response.webm');
    formData.append('session_id', sessionId);

    const response = await api.post<UploadResponsePayload>('/interviews/upload-response/', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      ...candidateSessionConfig,
    });
    return response.data;
  },

  async getInterviewSession(sessionId: string) {
    const response = await api.get(`/interviews/sessions/${sessionId}/`, candidateSessionConfig);
    return response.data;
  },

  async getAvatarSessionConfig(sessionId: string): Promise<HeyGenAvatarSdkConfig | null> {
    try {
      const response = await api.post<AvatarSessionResponse>(
        `/interviews/sessions/${sessionId}/avatar-session/`,
        {},
        candidateSessionConfig,
      );
      const payload = response.data;
      if (!payload.enabled || !payload.token || !payload.avatar_name) {
        return null;
      }
      return {
        token: payload.token,
        avatarName: payload.avatar_name,
        voiceId: payload.voice_id,
        quality: payload.quality,
        language: payload.language,
        activityIdleTimeout: payload.activity_idle_timeout,
      };
    } catch (error) {
      console.warn('Unable to initialize HeyGen SDK session. Falling back to binary transport.', error);
      return null;
    }
  },

  async completeSession(sessionId: string): Promise<Record<string, unknown>> {
    const response = await api.post<Record<string, unknown>>(
      `/interviews/sessions/${sessionId}/complete/`,
      {},
      candidateSessionConfig,
    );
    return response.data;
  },

  async saveExchange(
    sessionId: string,
    payload: {
      question_text: string;
      sequence_number?: number;
      question_intent?: string;
      target_flag_id?: string | number;
    },
  ): Promise<Record<string, unknown>> {
    const response = await api.post<Record<string, unknown>>(
      `/interviews/sessions/${sessionId}/save-exchange/`,
      payload,
      candidateSessionConfig,
    );
    return response.data;
  },

  async updateExchange(
    sessionId: string,
    payload: {
      sequence_number?: number;
      transcript?: string;
      video_url?: string;
      sentiment?: string;
      nonverbal_data?: Record<string, unknown>;
    },
  ): Promise<Record<string, unknown>> {
    const response = await api.post<Record<string, unknown>>(
      `/interviews/sessions/${sessionId}/update-exchange/`,
      payload,
      candidateSessionConfig,
    );
    return response.data;
  },

  async getPlayback(sessionId: string): Promise<InterviewPlaybackPayload> {
    const response = await api.get<InterviewPlaybackPayload>(
      `/interviews/sessions/${sessionId}/playback/`,
      candidateSessionConfig,
    );
    return response.data;
  },

  async compareSessions(sessionIds: string[]): Promise<Record<string, unknown>> {
    const response = await api.post<Record<string, unknown>>("/interviews/sessions/compare/", {
      session_ids: sessionIds,
    }, candidateSessionConfig);
    return response.data;
  },

  async generateFlags(caseId: string, persist = true, replacePending = false): Promise<Record<string, unknown>> {
    const response = await api.post<Record<string, unknown>>("/interviews/sessions/generate-flags/", {
      case: caseId,
      persist,
      replace_pending: replacePending,
    }, candidateSessionConfig);
    return response.data;
  },

  async listQuestions(params?: {
    question_type?: string;
    difficulty?: string;
    active?: boolean;
  }): Promise<InterviewQuestionRecord[]> {
    const response = await api.get<PaginatedResponse<InterviewQuestionRecord> | InterviewQuestionRecord[]>(
      "/interviews/questions/",
      { params, ...candidateSessionConfig },
    );
    return Array.isArray(response.data) ? response.data : response.data.results || [];
  },

  async getQuestionById(questionId: string): Promise<InterviewQuestionRecord> {
    const response = await api.get<InterviewQuestionRecord>(
      `/interviews/questions/${questionId}/`,
      candidateSessionConfig,
    );
    return response.data;
  },

  async listResponses(params?: { session?: string }): Promise<InterviewResponseRecord[]> {
    const response = await api.get<PaginatedResponse<InterviewResponseRecord> | InterviewResponseRecord[]>(
      "/interviews/responses/",
      { params, ...candidateSessionConfig },
    );
    return Array.isArray(response.data) ? response.data : response.data.results || [];
  },

  async getResponseById(responseId: string): Promise<InterviewResponseRecord> {
    const response = await api.get<InterviewResponseRecord>(
      `/interviews/responses/${responseId}/`,
      candidateSessionConfig,
    );
    return response.data;
  },

  async analyzeResponse(responseId: string): Promise<{ message: string }> {
    const response = await api.post<{ message: string }>(
      `/interviews/responses/${responseId}/analyze/`,
      {},
      candidateSessionConfig,
    );
    return response.data;
  },

  async listFeedback(params?: { session?: string }): Promise<InterviewFeedbackRecord[]> {
    const response = await api.get<PaginatedResponse<InterviewFeedbackRecord> | InterviewFeedbackRecord[]>(
      "/interviews/feedback/",
      { params, ...candidateSessionConfig },
    );
    return Array.isArray(response.data) ? response.data : response.data.results || [];
  },

  async getFeedbackById(feedbackId: string): Promise<InterviewFeedbackRecord> {
    const response = await api.get<InterviewFeedbackRecord>(
      `/interviews/feedback/${feedbackId}/`,
      candidateSessionConfig,
    );
    return response.data;
  },
};

export const connectInterviewWebSocket = (sessionId: string) => {
  const wsUrl = buildSessionWebsocketUrl(sessionId);
  return new WebSocket(wsUrl);
};
