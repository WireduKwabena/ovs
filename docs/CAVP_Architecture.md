# CAVP Architecture (OVS + GAMS)

This document summarizes the implemented architecture of CAVP (Civic Appointment and Vetting Platform), which combines:

- OVS: automated vetting workflows
- GAMS: government appointment governance workflows

## 1. Platform Topology

### 1.1 Backend

- Framework: Django + Django REST Framework
- Tenancy: django-tenants with PostgreSQL schema-per-organization
- Async: Celery + Redis
- Optional real-time: Django Channels (enabled only when `ENABLE_REALTIME=True`)

### 1.2 Frontend

- Framework: React + Vite + TypeScript
- Route layers:
  - `/admin/platform/*` (platform superadmin)
  - `/admin/org/:orgId/*` (organization admin)
  - `/workspace/*` (internal operations)
  - `/candidate/*` (candidate-facing)
  - `/government/*` (government appointments and registry views)

## 2. Multi-Tenancy Model

The tenant model is `Organization` in `apps/tenants/models.py`.

- Shared/public schema: identity, tenant registry, onboarding/public endpoints, payment webhooks, and framework internals.
- Tenant schemas: domain data for campaigns, cases, appointments, governance, publications, and related operational modules.

Tenant context is resolved by middleware from:

- subdomain, or
- `X-Organization-Slug` request header.

Org-scoped API calls also use:

- `X-Active-Organization-ID` to select active organization context for membership-validated actions.

## 3. Identity, Roles, and Capabilities

Authorization is layered:

1. Coarse user identity type (`admin`, `internal`, `applicant`)
2. Effective operational roles from:
   - Django groups
   - organization membership
   - committee membership
3. Capability resolution from effective roles
4. Scope checks (organization, committee, stage)
5. Security overlays (2FA and recent-auth for sensitive actions)

Key governance capabilities:

- `gams.registry.manage`
- `gams.appointment.stage`
- `gams.appointment.decide`
- `gams.appointment.publish`
- `gams.appointment.view_internal`
- `gams.audit.view`

## 4. Government Appointment Lifecycle

`AppointmentRecord.status` transitions are service-controlled:

`nominated -> under_vetting -> committee_review -> confirmation_pending -> appointed -> serving -> exited`

Additional outcomes:

- `rejected`
- `withdrawn`

Transition gates enforce:

- matching stage template/stage,
- required role,
- prior-stage completion,
- appoint/reject authority checks.

## 5. Core Domain Components

### 5.1 OVS (Vetting)

- `VettingCampaign`
- `VettingCase`
- `Document` + verification outputs
- `VettingRubric`, `RubricCriteria`, `RubricEvaluation`
- Fraud and consistency result entities

### 5.2 GAMS (Appointments)

- `GovernmentPosition`
- `PersonnelRecord`
- `AppointmentRecord`
- `ApprovalStageTemplate` + `ApprovalStage`
- `AppointmentPublication`
- Governance resources (org members, committees, committee memberships)

### 5.3 Billing and Onboarding

- Subscription tiers: `starter`, `growth`, `enterprise`
- Quota enforcement in `apps/billing/quotas.py`
- Organization onboarding token lifecycle endpoints under `/api/billing/onboarding-token/*`

## 6. AI and Decisioning Principle

AI-assisted outputs are advisory-only.

- Rubric engine produces weighted evidence-based scoring.
- Decision recommendation engine provides recommendation outputs.
- Human decision makers remain final authority for appointment decisions.
- Overrides and decision actions are auditable.

## 7. API Surface and Versioning

Preferred API base:

- `/api/v1/`

Legacy compatibility base:

- `/api/`

OpenAPI docs:

- `/api/schema/swagger-ui/`
- `/api/schema/redoc/`

## 8. Integrations

- Billing: Stripe, Paystack
- Real-time interviews: LiveKit
- Avatar layer: Tavus
- AI analysis: Anthropic-backed services

## 9. CI and Release Gate

Release gate sequence:

1. Frontend lint
2. Frontend type-check
3. Frontend `build:ci`
4. Backend tests
5. `python manage.py check --deploy`
6. OpenAPI validation

## 10. Key Documentation Set

- `docs/USER_MANUAL.md`
- `docs/user-manual/` modules
- `docs/USER_TYPES_AND_CAPABILITIES.md`
- `docs/A Comprehensive Blueprint for the Development of an Online Vetting System (1).docx`
- `CLAUDE.md`