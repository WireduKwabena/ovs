// ============================================================================
// Interview Service
// Location: frontend/src/services/interviewService.ts
// ============================================================================

import api from './api';

export const interviewService = {
  async startInterview(applicationId: string) {
    const response = await api.post('/api/interviews/interrogation/start/', {
      application_id: applicationId,
    });
    return response.data;
  },

  async uploadResponse(sessionId: string, videoBlob: Blob) {
    const formData = new FormData();
    formData.append('video', videoBlob, 'response.webm');
    formData.append('session_id', sessionId);

    const response = await api.post(
      '/api/interviews/upload-response/',
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      }
    );
    return response.data;
  },

  async getInterviewSession(sessionId: string) {
    const response = await api.get(`/api/interviews/${sessionId}/`);
    return response.data;
  },
};
//3. Connect to FastAPI WebSocket
export const connectInterviewWebSocket = (sessionId: string) => {
  const wsUrl = `${import.meta.env.VITE_FASTAPI_WS}/ws/interview/${sessionId}`;
  return new WebSocket(wsUrl);
};