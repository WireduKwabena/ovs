# 12) Notifications and Decision Lifecycle

## 12.1 Notification Surfaces

Frontend route:

- `/notifications`

Notification APIs:

- `GET /api/notifications/`
- `GET /api/notifications/{id}/`
- `POST /api/notifications/{id}/mark_read/`
- `DELETE /api/notifications/{id}/archive/`
- `POST /api/notifications/mark-as-read/`
- `POST /api/notifications/mark-all-as-read/`
- `GET /api/notifications/unread-count/`

## 12.2 Notification Use Cases

- Invitation delivery and reminders,
- Case progress updates,
- Interview scheduling/reminders,
- Billing/subscription state changes,
- Decision publication to candidates.

## 12.3 Decision Lifecycle Model

Typical status progression:

1. Candidate invited/enrolled.
2. Evidence collection.
3. AI analysis and score aggregation.
4. HR/Admin review.
5. Final decision:
   - approve,
   - reject,
   - escalate/manual review.
6. Candidate and stakeholders notified.

## 12.4 Decision Quality Controls

Before finalizing:

- Confirm rubric context and active version.
- Check for unresolved high-risk flags.
- Ensure all required evidence has completed processing.
- Add reviewer notes where required by policy.

## 12.5 Notification Hygiene

Recommended team process:

1. Keep unread count near zero for operational roles.
2. Archive obsolete notifications to reduce noise.
3. Use filters and case links for triage.
4. Correlate decision notifications with audit entries.

