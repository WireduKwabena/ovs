# 5) Internal Campaign and Rubric Workflows

## 5.1 Campaign Lifecycle Overview

Campaigns are the orchestration unit for vetting activities.

Core actions:

1. Create campaign.
2. Configure rubric version(s).
3. Import or enroll candidates.
4. Monitor dashboard progress.
5. Execute review and decisions.

## 5.2 Campaign Management Surfaces

Frontend pages:

- `/campaigns`
- `/campaigns/:campaignId`

Core APIs:

- `GET/POST /api/campaigns/`
- `GET/PATCH/DELETE /api/campaigns/{id}/`
- `POST /api/campaigns/{id}/candidates/import/`
- `GET /api/campaigns/{id}/dashboard/`
- `POST /api/campaigns/{id}/rubrics/versions/`
- `POST /api/campaigns/{id}/rubrics/versions/activate/`

## 5.3 Creating a Campaign

Recommended input data:

- Campaign name and purpose,
- Start/end windows,
- Ownership and team context,
- Operational settings for invitations and review.

Post-create checks:

- Campaign appears in list with editable state.
- Dashboard endpoint returns zeroed but valid summary.

## 5.4 Rubric Strategy

Rubrics define weighted scoring policy, while recommendation generation runs in a separate decision layer.

Pages:

- `/rubrics`
- `/rubrics/new`
- `/rubrics/:rubricId/edit`

Rubric APIs:

- `GET/POST /api/rubrics/vetting-rubrics/`
- `GET/PATCH/DELETE /api/rubrics/vetting-rubrics/{id}/`
- `POST /api/rubrics/vetting-rubrics/{id}/activate/`
- `POST /api/rubrics/vetting-rubrics/{id}/criteria/`
- `POST /api/rubrics/vetting-rubrics/{id}/duplicate/`
- `POST /api/rubrics/vetting-rubrics/create_from_template/`
- `GET /api/rubrics/vetting-rubrics/templates/`

## 5.5 Rubric Design Best Practices

1. Keep criteria explicit and measurable.
2. Use balanced weights; avoid over-concentrating one signal.
3. Define manual-review thresholds intentionally.
4. Validate rubric behavior on sample cases before activation.
5. Keep naming conventions stable for team consistency.

## 5.6 Evaluation Workflow

Implemented architecture:

1. Rubric scoring layer (`RubricEvaluationEngine`):
   - calculates weighted component scores and criterion-level outcomes,
   - stores transparent scoring internals in:
     - `evaluation_trace`
     - `decision_explanation`.
2. Vetting Decision Engine (`VettingDecisionEngine`):
   - runs after rubric evaluation,
   - generates advisory recommendation output (`decision_recommendation`) with:
     - `recommendation_status`
     - `blocking_issues`
     - `warnings`
     - `decision_basis` and explanation metadata.

AI inputs:

- Optional `ai_signals` payload is accepted only for synchronous rubric evaluation calls.
- AI signals are sanitized and persisted as advisory (`advisory_only=True`).
- Async evaluation rejects `ai_signals`.

Case evaluation APIs:

- `POST /api/rubrics/vetting-rubrics/{id}/evaluate-case/`
- `POST /api/rubrics/vetting-rubrics/{id}/evaluate_application/`

Evaluation management APIs:

- `GET /api/rubrics/evaluations/`
- `GET /api/rubrics/evaluations/{id}/`
- `POST /api/rubrics/evaluations/{id}/rerun/`
- `GET /api/rubrics/evaluations/{id}/decision-recommendation/`
- `POST /api/rubrics/evaluations/{id}/override-decision/`
- `POST /api/rubrics/evaluations/{id}/override-criterion/`

## 5.7 Recommendation Override and Audit

Use `POST /api/rubrics/evaluations/{id}/override-decision/` when a human reviewer needs to override the latest advisory recommendation.

Override behavior:

- `rationale` is required.
- override is stored as `VettingDecisionOverride`.
- recommendation status is updated with a `human_override` entry in `decision_basis`.
- API-driven recommendation/override actions emit audit events for generation and override recording.

Human authority remains final: recommendation output does not auto-approve or auto-reject an appointment.

## 5.8 Internal Daily Workflow Example

1. Open campaign workspace.
2. Confirm active rubric version.
3. Review intake totals (enrolled, in-progress, completed).
4. Run or rerun rubric evaluation as needed.
5. Inspect `decision_explanation`, `evaluation_trace`, and latest `decision_recommendation`.
6. Record decision override (with rationale) when policy or evidence requires a different recommendation path.
7. Apply final human decision with rationale.

## 5.9 Common Campaign Mistakes

- Activating campaign without active rubric.
- Importing candidates before verifying quota.
- Using ambiguous rubric criteria descriptions.
- Ignoring manual-review flags for low-confidence outputs.
- Treating advisory AI signals as final authority.
