# 1) Getting Started

## 1.1 What the Platform Is

CAVP is a web-based platform combining:

- OVS vetting orchestration (campaigns, rubrics, case tracking),
- AI-assisted evidence analysis (documents and interviews),
- Two-layer decision support:
  - rubric scoring + trace/explanation output,
  - advisory decision recommendation with audited human override support,
- GAMS appointment governance (positions, personnel, approval chain, publication),
- Human final authority and operational monitoring.

## 1.2 Deployment Modes

The platform can run in:

- Local development mode (Docker Compose, localhost),
- Production mode (dedicated production compose stack and hosted services).

## 1.3 Access URLs (Typical Local Setup)

- Frontend: `http://localhost:3000`
- Backend API root: `http://localhost:8000/api/`
- Django admin: `http://localhost:8000/admin/`
- OpenAPI schema:
  - `http://localhost:8000/api/schema/`
  - `http://localhost:8000/api/schema/swagger-ui/`
  - `http://localhost:8000/api/schema/redoc/`
- Flower (Celery monitoring): `http://localhost:5555`

## 1.4 Environment Requirements

Minimum runtime dependencies:

- Python 3.11+
- Node.js 18+
- PostgreSQL
- Redis
- Docker + Docker Compose (recommended for full stack startup)

## 1.5 First Login and Initial State

After environment setup:

1. Open the frontend landing page.
2. Select subscription flow if onboarding a new organization.
3. Complete registration (when access is granted via subscription confirmation).
4. Log in and complete 2FA for non-candidate account types.

## 1.6 High-Level Workflow Map

1. Admin/internal reviewer creates campaign.
2. Internal reviewer defines or attaches rubric.
3. Internal reviewer adds/imports candidates.
4. Candidate receives invitation link or access route.
5. Candidate submits required evidence and interview responses.
6. AI analyses are processed asynchronously.
7. Internal reviewer/admin reviews rubric trace + recommendation context and makes a final human decision.
8. Notifications and status updates are distributed.

## 1.7 Data Handling Model

The platform stores and displays:

- Identity and profile information (role-scoped),
- Campaign metadata and rubric versions,
- Case/evidence analysis outputs,
- Decision recommendation and override audit artifacts,
- Billing and subscription records,
- Audit and operational metrics.

All major actions are designed to be traceable through logs and model outputs.

## 1.8 Recommended Reading Next

- Continue to [Roles, Permissions, and Navigation](02_roles_permissions_navigation.md).
- Then read either:
  - [Internal Campaign and Rubric Workflows](05_hr_campaigns_rubrics.md), or
  - [Admin Operations and Control Center](09_admin_operations_control_center.md).
