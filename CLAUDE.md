# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Common Development Commands

### Backend (Django + DRF)

- **Setup virtual environment**:

  ```bash
  cd backend
  python -m venv venv
  source venv/bin/activate  # Windows: venv\Scripts\activate
  pip install -r requirements/development.txt -c requirements/constraints.lock.txt
  ```

- **Database migrations**:

  ```bash
  python manage.py migrate
  ```

- **Run development server**:

  ```bash
  python manage.py runserver
  ```

- **Run tests** (full suite):

  ```bash
  python manage.py test --keepdb
  ```

- **Run a single backend test**:

  ```bash
  python manage.py test apps.appointments.tests.AppointmentTests
  ```

- **Lint / type checks**:

  ```bash
  python -m flake8 .
  mypy .
  ```

- **Start auxiliary services**:
  - Redis: `redis-server`
  - Celery worker: `celery -A config worker -l info -E`
  - Celery beat: `celery -A config beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler`
  - Flower UI: `celery -A config flower --port=5555`

### Frontend (React + Vite + TypeScript)

- **Install dependencies**: `cd frontend && npm install`
- **Dev server**: `npm run dev`
- **Lint**: `npm run lint`
- **Type-check**: `npm run type-check`
- **Full test suite**: `npm test`
- **Single test**: `vitest src/pages/HomePage.test.tsx --run`
- **Build for CI** (type-check + lint included): `npm run build:ci`

## High-Level Architecture

### Platform Identity

This is **CAVP** (Civic Appointment & Vetting Platform), merging two systems:

- **OVS** — automated vetting (campaigns, cases, interviews, rubrics, fraud, audit)
- **GAMS** — government appointment governance (positions, personnel, appointments, approval chain, gazette)

**Core rule**: extend existing OVS modules; do not rewrite them.

### Multi-Tenancy (django-tenants)

The entire backend is multi-tenant. `apps/tenants/models.py::Organization` is the tenant model. Each `Organization` gets its own PostgreSQL schema.

- **`SHARED_APPS`** — live in the `public` schema: `tenants`, `users`, Django internals, third-party libraries.
- **`TENANT_APPS`** — live in each tenant's schema: all domain apps (`campaigns`, `applications`, `interviews`, `appointments`, etc.).
- **Tenant resolution**: `TenantMiddleware` resolves the tenant from the subdomain or the `X-Organization-Slug` request header. Falls back to the public schema when no tenant matches (e.g., during tests against `testserver`).
- **Public-schema URL config**: `config/public_urls.py` (`PUBLIC_SCHEMA_URLCONF`) — serves requests that have no tenant context: org onboarding/registration, system-admin login, billing webhooks. Everything else uses `config/urls.py`.

### API Versioning

- **Preferred**: `/api/v1/<resource>/` — use this for all new endpoints.
- **Legacy**: `/api/<resource>/` — kept for backward compatibility only; do not add new routes here.
- OpenAPI schema UI available at `/api/schema/swagger-ui/` and `/api/schema/redoc/` (requires `drf-spectacular`).

### Authorization Model (`apps/core/authz.py`)

Roles are strings stored on the user/membership record. Key roles:

| Role | Typical scope |
|---|---|
| `admin` | Full platform access |
| `registry_admin` | Manages positions/personnel registry |
| `vetting_officer` | Processes vetting cases |
| `committee_member` / `committee_chair` | Reviews and chairs appointment committees |
| `appointing_authority` | Issues final appointment decisions |
| `publication_officer` | Publishes gazette records |
| `auditor` | Read-only audit access |
| `applicant` / `nominee` | External candidate role |

Capabilities (e.g., `gams.appointment.decide`, `gams.appointment.publish`) are derived from roles via `ROLE_CAPABILITIES` in `authz.py`. Permission checks should use capabilities, not raw role strings, where possible.

`OrganizationMembership` (in `apps/governance/models.py`) links a user to their organization with a role. Org-scoped API calls from the frontend attach `X-Active-Organization-ID`.

### Appointment Lifecycle

`AppointmentRecord.status` state machine (service-enforced):

```
nominated → under_vetting → committee_review → confirmation_pending → appointed → serving → exited
                                             ↘ rejected
                        any stage → withdrawn
```

Stage transitions require:

1. A matching `ApprovalStage` (from the campaign's `ApprovalStageTemplate`) that maps to the target status.
2. The actor satisfying the stage's `required_role`.
3. All prior required stages completed.
4. Final decisions (`appointed`/`rejected`) require `appointing_authority` or `admin`.

### Rubric + AI Decision Engine (Advisory-Only)

Two separate layers in `apps/rubrics/`:

1. **`RubricEvaluationEngine`** — weighted scoring from case evidence; emits `evaluation_trace` and `decision_explanation`.
2. **`VettingDecisionEngine`** — consumes rubric outputs + AI signals; generates `VettingDecisionRecommendation` (`recommend_approve` / `recommend_reject` / `recommend_manual_review`).

**AI signals are advisory-only** (`advisory_only=True`). They never auto-finalize a human appointment decision. Human overrides are recorded in `VettingDecisionOverride` and audit-logged.

### Real-Time Interview Stack

WebSocket interviews use Django Channels routed in `apps/interviews/routing.py`. This is **opt-in**: set `ENABLE_REALTIME=True` in the environment to activate Daphne + Channels; the default ASGI app is plain Django without WebSocket support.

Interview services (`apps/interviews/services/`) integrate:

- **LiveKit** — real-time media sessions (`livekit_sdk.py`)
- **Tavus** — AI avatar layer (`avatar_service.py`)
- **Anthropic** — AI interview analysis (`enhanced_engine.py`)

### Frontend Architecture

Role-aware route layers:

- `/admin/platform/*` — platform superadmin UI
- `/admin/org/:orgId/*` — organization admin UI
- `/workspace/*` — internal staff workspace
- `/candidate/*` — candidate-facing UI
- `/government/*` — government positions, personnel, appointments

Redux slices (`frontend/src/store/`) manage client state. React Query handles server state. All API calls go through `frontend/src/services/*.service.ts`; the `api.ts` base client attaches JWT and the `X-Active-Organization-ID` header.

### UI Concept Aliases

Phase 1 keeps API contracts stable while using clearer UI labels. When reading frontend code, these map to backend models:

| UI label | Backend model/concept |
|---|---|
| Government Office | `GovernmentPosition` |
| Appointment Exercise | `VettingCampaign` |
| Appointment Route Template | `ApprovalStageTemplate` |
| Nomination / Appointment File | `AppointmentRecord` |
| Vetting Dossier | `VettingCase` |
| Gazette / Publication Record | `AppointmentPublication` |

### Billing & Quotas

`apps/billing/quotas.py` enforces per-organization limits (candidates, seats) based on subscription tier (`starter`, `growth`, `enterprise`). Billing webhooks (Stripe, Paystack) are handled in the public schema (`config/public_urls.py`) since they arrive before tenant resolution.

## Notable Configuration Files

- `backend/config/settings/*.py` — `base.py` (shared), `development.py`, `production.py`
- `backend/config/urls.py` — tenant-scoped URL conf
- `backend/config/public_urls.py` — public-schema URL conf (no tenant required)
- `frontend/vite.config.ts` — Vite config + proxy to backend
- `docker-compose.yml` / `docker-compose.prod.yml` — full service orchestration
- `.github/workflows/release-gate.yml` — CI: lint → type-check → tests → build → OpenAPI validation

## Release Gate Checklist

Before pushing: frontend lint → type-check → tests → `build:ci` → coverage → backend tests → `python manage.py check --deploy`.

When adding new API endpoints: update `backend/openapi.yaml` and verify CI validation passes.
