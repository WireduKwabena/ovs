# 2) Roles, Permissions, and Navigation

## 2.1 Identity Types and Operational Roles

The platform uses two layers:

- Identity type (`user_type`): `admin`, `internal`, `applicant`
- Operational role(s): capability-bearing governance/vetting roles

Operational roles currently enforced include:

- `registry_admin`
- `vetting_officer`
- `committee_member`
- `committee_chair`
- `appointing_authority`
- `publication_officer`
- `auditor`
- `nominee`

Important:

- `internal` alone is not enough for sensitive governance actions.
- Capability and scope checks must pass together.

## 2.2 Route Layers (Current Frontend)

Primary application route zones:

- `/admin/platform/*`: platform superadmin dashboards and controls
- `/admin/org/:orgId/*`: organization admin operations (users, members, committees, onboarding)
- `/workspace/*`: internal vetting and operations workspace
- `/candidate/*`: candidate access and interview flow
- `/government/*`: government positions, personnel, and appointments registry

Public and auth-adjacent routes (selected):

- `/`, `/login`, `/register`, `/subscribe`
- `/forgot-password`, `/reset-password/:token`
- invitation acceptance and billing callback routes

## 2.3 Role-to-Navigation Expectations

### Platform admin (`admin`)

Typical paths:

- `/admin/platform/dashboard`
- `/admin/platform/analytics`
- `/admin/platform/ai-engine`
- `/admin/platform/registry`
- `/admin/platform/billing`
- `/admin/platform/health`
- `/admin/platform/logs`

Can operate cross-organization oversight paths as policy permits.

### Organization admin (`registry_admin`-capable)

Typical paths:

- `/admin/org/:orgId/dashboard`
- `/admin/org/:orgId/users`
- `/admin/org/:orgId/members`
- `/admin/org/:orgId/committees`
- `/admin/org/:orgId/onboarding`
- `/admin/org/:orgId/cases`

Expected responsibilities:

- org member and committee management
- onboarding token lifecycle and invitations
- organization-scoped governance oversight

### Internal operators (`vetting_officer`, committee roles, appointing/publication authority)

Typical paths:

- `/workspace`
- `/workspace/campaigns`
- `/workspace/applications`
- `/workspace/rubrics`
- `/workspace/video-calls`
- `/government/positions`
- `/government/personnel`
- `/government/appointments`

Scope-dependent actions:

- stage actions require stage role + org scope
- committee actions require active committee membership
- appoint/reject requires appointing authority capability
- publication actions require publication capability

### Candidate / nominee (`applicant` identity)

Typical paths:

- `/candidate/access`
- `/candidate/interview/:applicationId`
- invitation entry routes (`/invite/:token` and related)

Candidates do not get internal governance navigation.

## 2.4 Permission Design Notes

- Route guards improve UX but do not replace backend authorization.
- Backend capability + scope enforcement is authoritative.
- Sensitive actions may require recent-auth re-verification.
- Internal operators are subject to 2FA policy.

## 2.5 Multi-Organization Navigation Behavior

When users have multiple organization memberships:

- Active org context drives visible org-admin pages and permitted actions.
- Org context is validated server-side using membership and role mapping.
- Switching org context can change available menus and action buttons.

## 2.6 Navigation Troubleshooting

If expected menus/routes are missing:

1. Confirm authenticated profile and role/capability payload.
2. Confirm active organization selection is valid.
3. Confirm committee assignment for committee-bound actions.
4. Check for pending 2FA or recent-auth requirements.
5. Verify token freshness and retry profile fetch.

