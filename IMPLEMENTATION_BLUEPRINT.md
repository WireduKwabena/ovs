# AI Vetting Platform - Implementation Blueprint (Django + React)

## 1) Product Scope

Build a campaign-driven vetting platform where HR can:

1. Create a vetting campaign/process.
2. Configure rubric(s) and thresholds.
3. Register candidates and send invite links/credentials (email/SMS).
4. Run two vetting tracks:
   - Document verification
   - AI-assisted video interview
5. Review compiled AI + evidence report.
6. Approve/reject/escalate to human 1v1 interview.
7. Notify candidate of outcome.

## 2) Recommended Architecture

### Core Services (single backend first)

- Django API (DRF): business logic + RBAC + orchestration.
- PostgreSQL: relational source of truth.
- Redis + Celery: async AI workloads and notifications.
- Object storage (S3/MinIO): documents, video/audio artifacts.
- React frontend: HR portal + candidate portal.

### AI Interview Stack (open source first)

- Realtime media/session layer: LiveKit (preferred).
- STT: faster-whisper.
- VAD: silero-vad.
- Optional diarization: pyannote.audio.
- CV features: OpenCV + MediaPipe.
- LLM scoring/reasoning: model abstraction layer (OpenAI/local vLLM).

## 3) Domain Model (Django Apps)

### `campaigns`

- `VettingCampaign`: name, owner, status, start/end, settings.
- `CampaignRubricVersion`: immutable rubric JSON + weights + thresholds.

### `candidates`

- `Candidate`: identity, contact, consent flags.
- `CandidateEnrollment`: candidate + campaign + enrollment status.
- `Invitation`: token, expiry, channel, send status, attempts.

### `documents`

- `CandidateDocument`: type, file, status, metadata.
- `DocumentAnalysisResult`: OCR, authenticity, fraud, evidence JSON, model versions.

### `interviews`

- `InterviewSession`: scheduled/started/completed, mode (AI/live 1v1), artifacts.
- `InterviewTurn`: question, transcript, timing, quality metrics.
- `InterviewAnalysisResult`: deception/behavioral signals + confidence + evidence.

### `scoring`

- `CandidateScorecard`: weighted component scores, final recommendation, rationale.
- `ScoreDecision`: hr_decision, reviewer, notes, timestamp.

### `notifications`

- `NotificationTemplate`, `Notification`, `DeliveryAttempt`.

### `reports`

- `CandidateReport`: rendered summary snapshot (JSON/PDF), signed URL, sent status.

## 4) Workflow State Machine

### Campaign

`draft -> active -> closed -> archived`

### Candidate Enrollment

`invited -> registered -> in_progress -> completed -> reviewed -> approved/rejected/escalated`

### Document Track

`uploaded -> queued -> processing -> completed/failed -> reviewed`

### Interview Track

`scheduled -> started -> processing -> completed/failed -> reviewed`

## 5) API Contract (MVP)

### HR APIs

- `POST /api/campaigns/`
- `POST /api/campaigns/{id}/rubrics/versions/`
- `POST /api/campaigns/{id}/candidates/import`
- `POST /api/campaigns/{id}/invitations/send`
- `GET /api/campaigns/{id}/dashboard`
- `GET /api/candidates/{id}/report`
- `POST /api/candidates/{id}/decision` (`approve|reject|escalate`)
- `POST /api/candidates/{id}/schedule-live-interview`

### Candidate APIs

- `POST /api/invitations/accept`
- `POST /api/candidate/documents/upload`
- `POST /api/candidate/interview/session/start`
- `POST /api/candidate/interview/session/{id}/complete`
- `GET /api/candidate/status`

## 6) Async Jobs (Celery)

- `send_invitation(candidate_enrollment_id, channel)`
- `process_document(document_id)`
- `run_document_fraud_checks(document_id)`
- `process_interview_media(interview_session_id)`
- `generate_candidate_scorecard(enrollment_id, rubric_version_id)`
- `compile_candidate_report(enrollment_id)`
- `notify_hr_report_ready(enrollment_id)`
- `notify_candidate_decision(enrollment_id)`

## 7) Scoring and Explainability Rules

1. Keep rubric versions immutable after activation.
2. Store component-level evidence:
   - source artifact
   - feature values
   - model id/version
   - confidence
3. Recommendation is AI-generated, final decision remains human-owned.
4. Require manual review when:
   - low confidence
   - conflicting signals
   - critical flags

## 8) Security, Compliance, and Trust

1. Explicit consent for recording + AI processing.
2. PII encryption at rest and signed URLs for artifacts.
3. Audit trail for every decision and override.
4. Retention policies:
   - raw media shortest window
   - derived scores longer
5. Bias monitoring dashboard by campaign/rubric version.

## 9) Delivery Plan

### Phase 1 (MVP foundation, 2-3 weeks)

1. Campaign + candidate enrollment + invitation flow.
2. Document upload + async processing skeleton.
3. Basic scorecard and HR dashboard.

### Phase 2 (AI interview, 2-3 weeks)

1. AI interview session flow (recorded first).
2. STT + transcript scoring + interview report section.
3. Unified candidate report with recommendation.

### Phase 3 (Ops and quality, 2 weeks)

1. Notification hardening (email/SMS retries, templates).
2. Observability (task metrics, failure queues, tracing).
3. Security/compliance controls + audit exports.

### Phase 4 (Realtime + advanced, optional)

1. Realtime AI interview with LiveKit.
2. Optional 1v1 live interviewer handoff.
3. Model monitoring and retraining loops.

## 10) Immediate Next Build Tasks (Practical)

1. Stabilize current backend imports/model drift before new feature work.
2. Implement `campaigns`, `candidates`, and `invitations` apps first.
3. Introduce immutable rubric version table and bind scorecards to it.
4. Implement document pipeline end-to-end with a single OCR + authenticity baseline.
5. Add report compilation and HR decision endpoint before adding advanced interview AI.

