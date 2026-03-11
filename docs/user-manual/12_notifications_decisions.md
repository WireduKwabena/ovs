# 12) Notifications and Decision Lifecycle

## 12.1 Notification Surfaces

Frontend route:

- `/notifications`

Notification APIs:

- `GET /api/notifications/`
- `GET /api/notifications/{id}/`
- `POST /api/notifications/{id}/mark_read/`
- `DELETE /api/notifications/{id}/archive/`
- `POST /api/notifications/{id}/restore/`
- `POST /api/notifications/mark-as-read/`
- `POST /api/notifications/mark-all-as-read/`
- `GET /api/notifications/unread-count/`

## 12.2 Notification Use Cases

- Invitation delivery and reminders,
- Case progress updates,
- Interview scheduling/reminders,
- Billing/subscription state changes,
- Candidate decision publication,
- Government appointment lifecycle events (nomination, stage moves, decision, publication, revocation).

## 12.3 Decision Lifecycle Model

OVS case progression (typical):

1. Candidate invited/enrolled.
2. Evidence collection.
3. AI analysis and score aggregation.
4. Internal reviewer/admin review.
5. Final decision:
   - approve,
   - reject,
   - escalate/manual review.
6. Candidate and stakeholders notified.

Rubric and recommendation architecture:

1. Rubric scoring layer computes weighted scoring + criterion outcomes.
2. Decision recommendation layer consumes rubric outputs, policy/evidence checks, and advisory AI signals.
3. Human reviewers retain final authority and can record recommendation overrides with rationale.

GAMS appointment progression (service-enforced transitions):

1. `nominated`
2. `under_vetting`
3. `committee_review`
4. `confirmation_pending`
5. `appointed`
6. `serving`
7. `exited`

Alternative terminal outcomes:

- `rejected`
- `withdrawn`

## 12.4 Appointment Stage Gating With Recommendation Context

For appointments linked to vetting cases, transitions into governance decision stages require recommendation context:

- gated statuses: `committee_review`, `confirmation_pending`, `appointed`
- required baseline:
  - linked rubric evaluation exists
  - latest vetting decision recommendation exists

Additional enforcement:

- For `confirmation_pending` and `appointed`:
  - if blocking issues exist, provide `reason_note` or record recommendation override first.
- For `appointed`:
  - `recommend_reject` requires recommendation override.
  - `recommend_manual_review` requires `reason_note` or recommendation override.

This gate is advisory-aware, not autonomous: human actors still execute final stage transitions.

## 12.5 Decision Quality Controls

Before finalizing:

- Confirm rubric context and active version.
- Review `decision_explanation`, `evaluation_trace`, and latest recommendation status.
- Check for unresolved high-risk flags.
- Ensure all required evidence has completed processing.
- Add reviewer notes where required by policy (`reason_note` where needed).
- For appointments, ensure required approval-stage context is attached when template policy requires it.

## 12.6 Notification Hygiene

Recommended team process:

1. Keep unread count near zero for operational roles.
2. Archive obsolete notifications to reduce noise.
3. Use filters and case links for triage.
4. Correlate decision notifications with audit entries.
5. For GAMS, track appointment lifecycle event types in metadata (for example `appointment_moved_to_approval_chain`, `appointment_published`, `appointment_revoked`).
