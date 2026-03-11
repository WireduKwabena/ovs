# 9) Admin Operations and Control Center

## 9.1 Admin UI Areas

Admin-exclusive routes:

- `/admin/dashboard`
- `/admin/analytics`
- `/admin/register`
- `/admin/control-center`
- `/admin/users`
- `/admin/cases`
- `/admin/cases/:caseId`
- `/admin/rubrics`

## 9.2 Admin APIs

Admin dashboard endpoints:

- `GET /api/admin/dashboard/`
- `GET /api/admin/analytics/`
- `GET /api/admin/cases/`
- `GET /api/admin/users/`
- `PATCH /api/admin/users/{user_id}/`

## 9.3 Key Admin Responsibilities

1. Platform-level user management.
2. Global case oversight and intervention.
3. Policy and quality governance.
4. Operational visibility and escalation.
5. Access and permission lifecycle control.

## 9.4 User Management Procedures

For each user update:

1. Validate reason for change.
2. Confirm role impact (admin/internal/applicant).
3. Apply change and verify route/access behavior.
4. Log and communicate action where required.

## 9.5 Case Oversight Procedures

Admin case review focuses on:

- unresolved flagged cases,
- edge-case decisions requiring override,
- cross-workspace anomalies or abuse patterns,
- incident-triggered investigations.

## 9.6 Governance Recommendations

- Keep admin account count minimal.
- Enforce 2FA across all non-candidate accounts.
- Review audit logs routinely.
- Require rationale for sensitive state changes.

## 9.7 Delegation Model

Admins should avoid day-to-day vetting execution when possible.

- Internal reviewers run campaign execution.
- Admins focus on:
  - policy enforcement,
  - platform stability,
  - compliance and forensic readiness.
