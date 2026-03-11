# 8) AI Interviews and Live Video Calls

## 8.1 Interview Surfaces

Frontend routes:

- `/interview/interrogation/:applicationId`
- `/video-calls`

Interview APIs:

- `GET/POST /api/interviews/sessions/`
- `GET/PATCH/DELETE /api/interviews/sessions/{id}/`
- `POST /api/interviews/sessions/{id}/start/`
- `POST /api/interviews/sessions/{id}/complete/`
- `POST /api/interviews/sessions/{id}/avatar-session/`
- `GET /api/interviews/sessions/{id}/playback/`
- `POST /api/interviews/sessions/{id}/save-exchange/`
- `POST /api/interviews/sessions/{id}/update-exchange/`
- analytics utility endpoints under `/api/interviews/sessions/*`

Interview content APIs:

- `GET/POST /api/interviews/questions/`
- `GET/POST /api/interviews/responses/`
- `POST /api/interviews/responses/{id}/analyze/`
- `GET/POST /api/interviews/feedback/`

## 8.2 Interview Flow

1. Session is scheduled or started.
2. Questions are asked/generated.
3. Responses are recorded/uploaded.
4. Response analysis is performed.
5. Session is completed and feedback is attached.

## 8.3 Video Meeting APIs (LiveKit-Oriented)

- `GET/POST /api/video-calls/meetings/`
- `GET/PATCH/DELETE /api/video-calls/meetings/{id}/`
- `POST /api/video-calls/meetings/{id}/start/`
- `POST /api/video-calls/meetings/{id}/complete/`
- `POST /api/video-calls/meetings/{id}/cancel/`
- `POST /api/video-calls/meetings/{id}/reschedule/`
- `POST /api/video-calls/meetings/{id}/extend/`
- `POST /api/video-calls/meetings/{id}/join-token/`
- `GET /api/video-calls/meetings/{id}/events/`
- `GET /api/video-calls/meetings/reminder-health/`
- recurring series endpoints:
  - `POST /api/video-calls/meetings/schedule-series/`
  - `POST /api/video-calls/meetings/{id}/reschedule-series/`
  - `POST /api/video-calls/meetings/{id}/cancel-series/`

## 8.4 Scheduling Best Practices

1. Choose clear timezone and meeting title conventions.
2. Confirm candidates receive invite notifications early.
3. Use extension/reschedule actions instead of deleting records.
4. Track reminder runtime health if reminder delivery appears delayed.

## 8.5 1v1 and 1vMany Notes

The meeting model supports structured scheduling and participant states.

- 1v1: Internal reviewer and a single candidate.
- 1vMany: Internal reviewer with multiple candidate participants.

Always confirm participant list and role metadata before start.

## 8.6 Troubleshooting Interview/Meeting Issues

If join fails:

1. Confirm join-token endpoint returns valid token.
2. Check LiveKit env configuration (`LIVEKIT_URL`, API key/secret).
3. Verify meeting state is startable (not canceled/completed).
4. Check reminder-health endpoint for runtime degradation.
