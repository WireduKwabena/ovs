# Frontend Overview (CAVP)

This frontend is a React + TypeScript app for both:

- Vetting workflows (campaigns, applications, interviews, rubrics, monitoring).
- Government workflows (positions, personnel, appointments, approval chain, publication lifecycle).

## Core Government Pages

- `src/pages/GovernmentPositionsPage.tsx`
  - Register and browse `GovernmentPosition` records.
  - Public/vacancy flags shown in registry table.
- `src/pages/GovernmentPersonnelPage.tsx`
  - Register and browse `PersonnelRecord` records.
  - Officeholder/public flags and candidate linkage visibility.
- `src/pages/AppointmentsRegistryPage.tsx`
  - Create nominations (`AppointmentRecord`).
  - Manage approval-stage templates and stages.
  - Execute lifecycle transitions, stage actions, publish/revoke actions.
  - View publication status and stage-action history.

## Government API Service Layer

- `src/services/government.service.ts`
  - Positions: list/create
  - Personnel: list/create
  - Appointments: list/create, stage transitions, appoint/reject, vetting linkage
  - Approval chain: stage templates + stages
  - Publication lifecycle: publication detail, publish, revoke
  - Public feeds: gazette feed + open appointments

## Route Integration

Protected routes in `src/App.tsx`:

- `/government/positions`
- `/government/personnel`
- `/government/appointments`

These routes are behind authentication and excluded for applicant-only users.

## Data Exposure Rules in UI

- Internal appointment registry views are for authenticated HR/admin government actors.
- Public feeds use separate backend serializers and should not include vetting-case internals.
- UI labels and state controls are lifecycle-aware, but backend remains source of truth for transition policy.

## Dev Commands

```bash
npm install
npm run dev
npm run type-check
npm test
```
