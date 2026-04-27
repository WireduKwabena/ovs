# CAVP User Manual

Version: 2.1  
Last Updated: March 12, 2026

## Start Here

If you want a practical, click-by-click guide, use:

- [End-User Task Manual](USER_MANUAL_PRINT.md)
- [Supervisor Demo Quick Script](USER_MANUAL_PRINT.md#0-supervisor-demo-quick-script)

This manual is organized for day-to-day work by role:

- Applicant tasks (invitation, document upload, interview, results)
- Operations tasks (appointment exercises, rubrics, vetting dossier review, checks, calls)
- Government appointment tasks (offices, nominee records, nomination files, approval route stages, publication)
- Admin oversight tasks (users, audit, monitoring)

Core lifecycle framing used across the UI:

- `Office -> Appointment Exercise -> Nominee / Nomination File -> Vetting Dossier -> Review -> Approval -> Appointment -> Publication`

## CAVP in One View

CAVP merges two operating layers:

- OVS: vetting, dossier evidence, rubric scoring, interview intelligence, and background checks.
- GAMS: government office registry, personnel records, approval chains, appointment decisions, and publication.

Core operating rule:

- AI assists and recommends.
- Human authorities decide and sign off.

## Access and Navigation Model

The product is route-layered by account and authority scope:

- Platform admin: `/admin/platform/*`
- Organization admin: `/admin/org/:orgId/*`
- Internal operations workspace: `/workspace/*`
- Candidate flows: `/candidate/*`
- Government registry and appointments: `/government/*`

For complete role/capability policy, see:

- `docs/USER_TYPES_AND_CAPABILITIES.md`
- `docs/user-manual/02_roles_permissions_navigation.md`

## Multi-Organization Context

For users who belong to more than one organization:

- Tenant context is resolved by organization slug (`X-Organization-Slug`) and request routing.
- Active working organization is selected with `X-Active-Organization-ID` for scoped operations.
- Committee and appointment actions are validated against both role capability and active organization scope.

## Appointment Flow (Operational)

Main appointment lifecycle:

- `nominated -> under_vetting -> committee_review -> confirmation_pending -> appointed -> serving -> exited`

Alternative exits:

- `rejected`
- `withdrawn`

Final decision gates are restricted to appointing authority or platform admin according to policy.

## Organization Onboarding and Subscription

Subscription controls and onboarding are integrated into billing workflows:

- Tiers: `starter`, `growth`, `enterprise`
- Providers: Stripe and Paystack
- Onboarding token lifecycle endpoints:
	- `/api/billing/onboarding-token/`
	- `/api/billing/onboarding-token/generate/`
	- `/api/billing/onboarding-token/revoke/`
	- `/api/billing/onboarding-token/send-invite/`
	- `/api/billing/onboarding-token/validate/`

Quotas are enforced by tier and organization limits.

## What This Guide Emphasizes

- Navigation paths you can open in the UI
- Step-by-step task execution
- Expected outcomes after each action
- Common blockers and how to resolve them safely

## Core Principles

- AI is decision-support only.
- Human decision-makers remain final authority.
- Public endpoints and views must not expose internal vetting details.
- Role and permission controls are enforced by the backend.

## Documentation Map

Primary documents:

- `docs/USER_MANUAL_PRINT.md` (task-first guide)
- `docs/user-manual/` (modular reference set)
- `docs/USER_TYPES_AND_CAPABILITIES.md` (authorization source)
- `docs/CAVP_Architecture.md` (architecture overview)

Recommended reading order for new internal operators:

1. This file (`USER_MANUAL.md`)
2. `docs/user-manual/01_platform_overview.md`
3. `docs/user-manual/02_roles_permissions_navigation.md`
4. `docs/user-manual/03_admin_dashboard_and_system_monitoring.md`
5. `docs/user-manual/15_api_endpoint_quick_map.md`

## Technical Reference (Optional)

For deeper operational or API-level details, keep using files in `docs/user-manual/`.
These are support references, not primary end-user onboarding content.
