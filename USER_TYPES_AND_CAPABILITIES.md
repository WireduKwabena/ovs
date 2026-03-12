# User Types and Capabilities (Current OVS + GAMS)

This document describes the **actual authorization model currently implemented** in this repository.

Source of truth:

- `backend/apps/authentication/models.py`
- `backend/apps/core/authz.py`
- `backend/apps/core/permissions.py`
- `backend/apps/core/policies/registry_policy.py`
- `backend/apps/core/policies/appointment_policy.py`
- `backend/apps/core/policies/committee_policy.py`
- `backend/apps/appointments/permissions.py`
- `backend/apps/governance/views.py`
- `backend/apps/billing/views.py`
- `backend/apps/rubrics/permissions.py`

## 1) Authorization model in one view

The system is hybrid and layered:

1. `user_type` (coarse identity): `admin`, `internal`, `applicant`
2. Operational roles (fine-grained): from Django groups + org membership + committee membership
3. Capabilities: resolved from roles
4. Scope constraints: active organization + committee membership checks
5. Extra security: 2FA for internal operators; recent-auth step-up for sensitive actions

Important: `user_type="internal"` **does not** grant governance power by itself.

## 2) Coarse user types (`user.user_type`)

| user_type | Meaning | Baseline role mapping | Baseline capabilities |
| --- | --- | --- | --- |
| `admin` | Platform-level administrator identity | `admin` | All capabilities |
| `internal` | Internal staff identity marker | `internal` | None by default |
| `applicant` | External candidate/nominee identity | `nominee` | None |

Notes:

- `admin` has platform recovery override paths in scoped policies.
- `internal` must also have explicit governance role(s) to perform sensitive GAMS actions.
- `applicant`/`nominee` is non-internal and does not get governance capabilities.

## 3) Operational role sources

A user's effective roles are merged from:

1. Django groups (government role groups)
2. Organization membership role mapping
3. Committee membership role mapping
4. `user_type` fallback role (`admin` / `internal` / `nominee`)

### 3.1 Group-based roles

Recognized group roles:

- `registry_admin`
- `vetting_officer`
- `committee_member`
- `committee_chair`
- `appointing_authority`
- `publication_officer`
- `auditor`

### 3.2 Organization membership role mapping

Organization `membership_role` values mapped to authz roles:

- `registry_admin` -> `registry_admin`
- `org_admin` -> `registry_admin`
- `organization_admin` -> `registry_admin`
- `system_admin` -> `registry_admin`
- `vetting_officer` -> `vetting_officer`
- `appointing_authority` -> `appointing_authority`
- `publication_officer` -> `publication_officer`
- `auditor` -> `auditor`
- `nominee` -> `nominee`

### 3.3 Committee membership role mapping

Committee membership (`committee_role`) to authz role:

- `member` -> `committee_member`
- `secretary` -> `committee_member`
- `chair` -> `committee_member` + `committee_chair`
- `observer` -> no committee actor role

`observer` must be non-voting (`can_vote=false`) by constraint.

## 4) Capability catalog

Capabilities are currently:

- `gams.registry.manage`
- `gams.appointment.stage`
- `gams.appointment.decide`
- `gams.appointment.publish`
- `gams.appointment.view_internal`
- `gams.audit.view`

### 4.1 Role -> capability mapping

| Role | Capabilities |
| --- | --- |
| `admin` | all capabilities |
| `internal` | none |
| `registry_admin` | `gams.registry.manage`, `gams.appointment.stage`, `gams.appointment.view_internal` |
| `vetting_officer` | `gams.appointment.stage`, `gams.appointment.view_internal` |
| `committee_member` | `gams.appointment.stage`, `gams.appointment.view_internal` |
| `committee_chair` | `gams.appointment.stage`, `gams.appointment.view_internal` |
| `appointing_authority` | `gams.appointment.stage`, `gams.appointment.decide`, `gams.appointment.publish`, `gams.appointment.view_internal` |
| `publication_officer` | `gams.appointment.publish`, `gams.appointment.view_internal` |
| `auditor` | `gams.audit.view`, `gams.appointment.view_internal` |
| `nominee` | none |

## 5) Practical actor profiles (what each can do)

These are the effective actors used in OVS + GAMS operations.

### Platform Admin (`admin`)

Can:

- Access platform-wide internal operations
- Override org scoping for recovery/oversight paths
- Manage governance resources and billing onboarding paths
- View audit logs globally

### Registry Admin / Org Admin (`registry_admin`)

Can:

- Manage organization governance APIs (members, committees, committee memberships, chair reassignment)
- Manage organization onboarding token lifecycle
- Initiate org-scoped billing checkout and subscription management
- Manage registry/internal workflow operations within organization scope

Cannot:

- Operate outside org scope unless platform admin

### Vetting Officer (`vetting_officer`)

Can:

- Perform stage/vetting workflow actions that require stage authority
- Access internal appointment/vetting data in org scope

Cannot:

- Perform org-admin governance management
- Final appointment decision unless also appointing authority
- Publication unless also publication officer/appointing authority

### Committee Member (`committee_member`)

Can:

- Take committee-stage actions when actively assigned to the bound committee
- View internal data in allowed scope

Cannot:

- Perform org-admin governance controls
- Final appointment decision unless also appointing authority
- Chair-only committee actions without chair membership

### Committee Chair (`committee_chair`)

Can:

- All committee member functions
- Chair-restricted committee stage actions

Cannot:

- Bypass org scope or committee assignment checks

### Appointing Authority (`appointing_authority`)

Can:

- Final appointment decisions (appoint/reject)
- Publish/revoke authority path (policy allows)
- Stage transitions and internal views in org scope

Cannot:

- Skip recent-auth requirement on sensitive endpoints

### Publication Officer (`publication_officer`)

Can:

- Publish/revoke publication lifecycle actions
- View internal appointment data in scope

Cannot:

- Final appointment decision unless also appointing authority

### Auditor (`auditor`)

Can:

- Read audit logs (`gams.audit.view`)
- View internal appointment data where scoped

Cannot:

- Mutate governance workflow entities by auditor role alone

### Nominee / Applicant (`nominee` + `user_type=applicant`)

Can:

- Use applicant/candidate-facing flows only
- No governance capabilities by default

Cannot:

- Access internal governance actions/routes

### Public user (unauthenticated)

Can:

- Access public transparency/publication endpoints designed as `AllowAny`

Cannot:

- Access internal governance, vetting, or audit APIs

## 6) High-value policy gates (actual enforcement)

| Action family | Main gate |
| --- | --- |
| Org governance management | `can_manage_registry_governance(...)` + active org scope |
| Org onboarding token management | `_resolve_onboarding_management_organization(...)` -> governance admin check |
| Billing checkout for org | `_resolve_checkout_organization_id(...)` -> governance admin check |
| Internal appointment visibility | `can_view_internal_record(...)` |
| Stage transitions | `can_advance_stage(...)` + stage role + org scope |
| Committee actions | `can_take_committee_action(...)` + active committee membership (non-observer) |
| Final appoint/reject | `can_appoint(...)` |
| Publish/revoke | `can_publish(...)` |
| Audit access | `can_view_audit(...)` |

## 7) Security overlays

### 2FA policy

- 2FA is required for `is_internal_operator(user)`.
- Current rule: any resolved role other than `nominee` is treated as internal operator.

### Recent-auth step-up policy

Sensitive actions require recent verification (`RequiresRecentAuth`), including:

- Appoint action
- Publish action
- Revoke publication action
- Decision override endpoints (rubric/decision layer)

## 8) Scope and tenancy behavior

For non-platform users:

- Access is scoped by active organization and memberships.
- Cross-organization operations are denied (commonly 403 or 404 depending on endpoint pattern).
- Committee-stage actions require membership in the specific committee bound to stage/appointment.

For platform admins:

- Recovery/override paths remain intentionally available.

## 9) Legacy and compatibility notes

- `user_type` is intentionally kept for compatibility (`admin`, `internal`, `applicant`).
- Governance authority now comes from explicit roles/capabilities/memberships.
- Legacy broad fallback from old `hr_manager` patterns is not part of the current authz model.
- Free-form organization `membership_role` values are allowed, but only mapped values grant authz roles.

## 10) Recommended interpretation for operations

When deciding if a user can perform an action, evaluate in this order:

1. Is the user authenticated?
2. Does the user have required role/capability?
3. Is active organization context valid for the action?
4. If committee-bound, does active committee membership allow this action?
5. If sensitive, has recent-auth been satisfied?

If any step fails, treat access as denied.
