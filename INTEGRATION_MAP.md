# OVS Integration Map

## Goal

Keep `campaigns` as orchestration and preserve domain ownership in:

- `applications` (document vetting lifecycle)
- `rubrics` (evaluation/scoring policy)
- `interviews` (AI/live interview lifecycle)

## Current Runtime Status

### Active in runtime

- `apps.authentication`
- `apps.campaigns`
- `apps.candidates`
- `apps.invitations`

Defined in `backend/config/settings/base.py`.

### Not active in runtime

- `apps.applications`
- `apps.rubrics`
- `apps.interviews`
- `apps.notifications`
- `apps.fraud`

Not present in `INSTALLED_APPS`, and not routed in `backend/config/urls.py`.

## Relevance Decision

These apps are still product-relevant and should remain:

- `campaigns`: process setup, rubric version selection, progress overview
- `applications`: document uploads, OCR/authenticity/fraud evidence, case-level vetting facts
- `interviews`: interview session/questions/responses/video-derived evidence
- `rubrics`: policy engine that turns evidence into weighted recommendations

`campaigns` should coordinate them, not replace them.

## Target Ownership Boundaries

### campaigns

- Owns campaign lifecycle (`draft -> active -> closed -> archived`)
- Owns rubric *version selection* for a campaign
- Owns aggregate dashboard counters only

### candidates

- Owns candidate identity and enrollment state transitions
- Owns invite/registration boundary

### applications

- Owns document vetting records and AI document evidence
- Owns case-level status for document track

### interviews

- Owns AI/live interview sessions and response analytics
- Owns interview completion status and interview evidence

### rubrics

- Owns scoring/evaluation policy and override flow
- Produces recommendation, never final HR decision

## Integration Backbone (recommended)

Use `CandidateEnrollment` as the orchestration anchor.

1. `applications.VettingCase` links to `candidates.CandidateEnrollment` (1:1 recommended).
2. `interviews.InterviewSession` links to `CandidateEnrollment` (or `VettingCase` if case remains canonical).
3. `rubrics.RubricEvaluation` links to enrollment/case and campaign rubric version.
4. `campaigns` reads status projections from those apps and updates only enrollment summary state.

## Event Flow

1. Campaign created and rubric version activated.
2. Candidate imported/enrolled and invitation accepted.
3. Enrollment registration triggers creation of document case (`applications`).
4. Document processing completes and emits evaluation-ready event.
5. Interview completes and emits evaluation-ready event.
6. Rubric engine computes recommendation from document + interview evidence.
7. Score/report compiled and shown to HR.
8. HR final decision updates enrollment (`approved/rejected/escalated`) and notifications are sent.

## API Shape (module ownership)

### campaigns API

- Campaign CRUD
- Campaign rubric version CRUD/activate
- Campaign dashboard aggregation

### applications API

- Create/retrieve case by enrollment
- Upload/list documents
- Document processing status

### interviews API

- Create/start/complete interview session
- List interview outputs and analytics

### rubrics API

- Evaluate enrollment/case against selected rubric version
- Retrieve score breakdown and overrides

## Blockers Before Re-enabling Legacy Apps

1. Import/path inconsistencies:
   - package-level imports like `from apps.applications import VettingCase`
2. Model/serializer drift:
   - serializers referencing fields/related names not on current models
3. Missing dependencies:
   - references to modules not present (for example `audit`, `ai_verification`)
4. No migrations for several legacy apps:
   - `applications`, `interviews`, and `rubrics` currently have no concrete migration files in this repo state

## Practical Migration Sequence

1. Repair legacy imports and serializer/model mismatches.
2. Add/align migrations for `applications`, `interviews`, `rubrics`.
3. Introduce enrollment link fields (case/session/evaluation to enrollment).
4. Re-add apps to `INSTALLED_APPS` and wire URLs under `/api/applications`, `/api/interviews`, `/api/rubrics`.
5. Implement orchestration services in `campaigns` using domain events/tasks (not cross-app business logic duplication).
6. Add integration tests for full flow: invite -> docs -> interview -> scoring -> decision.

## Non-Goals

- Do not move rubric scoring logic into `campaigns`.
- Do not duplicate document or interview models in `campaigns`.
- Do not couple final HR decision directly to AI recommendation.

## Acceptance Criteria

1. Campaign can orchestrate end-to-end vetting without owning document/interview internals.
2. Rubric evaluation consumes evidence from both document and interview tracks.
3. Enrollment status reflects true cross-app progression.
4. Full flow works with tests and without manual DB patching.
