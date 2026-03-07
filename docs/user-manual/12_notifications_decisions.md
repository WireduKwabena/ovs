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
4. HR/Admin review.
5. Final decision:
   - approve,
   - reject,
   - escalate/manual review.
6. Candidate and stakeholders notified.

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

## 12.4 Decision Quality Controls

Before finalizing:

- Confirm rubric context and active version.
- Check for unresolved high-risk flags.
- Ensure all required evidence has completed processing.
- Add reviewer notes where required by policy.
- For appointments, ensure required approval stage context is attached when template policy requires it.

## 12.5 Notification Hygiene

Recommended team process:

1. Keep unread count near zero for operational roles.
2. Archive obsolete notifications to reduce noise.
3. Use filters and case links for triage.
4. Correlate decision notifications with audit entries.
5. For GAMS, track appointment event types in notification metadata (for example `appointment_published`, `appointment_revoked`).
