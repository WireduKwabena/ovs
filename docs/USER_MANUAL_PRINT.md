# CAVP End-User Manual (Task Guide)

Version: 2.0  
Audience: Applicants, Operations Users, Government Appointment Actors, and Admins  
Last Updated: March 7, 2026

---

## 0) Supervisor Demo Quick Script

Audience: Supervisor / evaluators  
Duration: 12-18 minutes

### 0.1 Pre-demo reset

Run once before presentation:

Local:

```bash
cd backend
python manage.py migrate
python manage.py setup_demo
```

Docker:

```bash
docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py setup_demo
```

### 0.2 Demo accounts

- Admin: `gams.admin@demo.local` / `DemoAdmin123!`
- Vetting: `gams.vetting@demo.local` / `DemoVetting123!`
- Committee: `gams.committee@demo.local` / `DemoCommittee123!`
- Authority: `gams.authority@demo.local` / `DemoAuthority123!`
- Registry: `gams.registry@demo.local` / `DemoRegistry123!`

### 0.3 Walkthrough order

1. Admin login
2. Vetting login
3. Committee login
4. Authority login
5. Registry/Admin close

### 0.4 Script steps

1. Admin: open `/government/positions`, `/government/personnel`, `/government/appointments`.
2. Show seeded records:
   - nomination record (draft publication),
   - serving record (published publication).
3. Vetting user: move nominated record to `under_vetting` with mapped stage.
4. Committee user: move same record to `committee_review`; show stage actions.
5. Authority user: move to `confirmation_pending`, then `appointed`.
6. Registry or authority: publish appointment with publication reference.
7. Admin: open `/notifications` and `/audit-logs` to show traceability.

### 0.5 Key talking points (say these explicitly)

1. CAVP preserves vetting modules and governance controls.
2. Government appointment lifecycle is governed and traceable.
3. AI is advisory only; humans remain final authority.
4. Critical actions are visible in notifications and audit logs.

### 0.6 Fast fallback if blocked

1. Re-run `python manage.py setup_demo`.
2. Refresh `/government/appointments`.
3. Resume from seeded nominated record.

---

---

## 1) What This Manual Is

This manual is for day-to-day users of the platform.

It focuses on:

- where to go in the app,
- what to click,
- what each step should produce,
- what to do when a workflow is blocked.

This is not an API or developer manual.

---

## 2) Quick Start

### 2.1 First Login

1. Open the app landing page.
2. Use your assigned route:
   - New organization signup: `/subscribe`
   - Standard sign-in: `/login`
   - Invitation onboarding: `/invite/:token`
3. Complete 2FA if prompted.
4. After login, use the top navigation bar.

### 2.2 If You Do Not See a Page

Access is role-based.

- Applicants cannot access admin, campaign management, or government registry pages.
- Operations users and admins can access vetting + government workflow pages.
- Some actions (for example final appointment decision and publication) require appointing-authority/admin rights.

---

## 3) Navigation Map By Role

### 3.1 Applicant

Primary pages:

- `/dashboard`
- `/applications` (My Cases)
- `/video-calls`
- `/candidate/access` (invitation portal)
- `/notifications`

### 3.2 Operations User

Primary pages:

- `/dashboard`
- `/campaigns`
- `/applications` (Cases)
- `/rubrics`
- `/video-calls`
- `/government/appointments`
- `/government/positions`
- `/government/personnel`
- `/fraud-insights`
- `/background-checks`
- `/notifications`

### 3.3 Admin

Primary pages:

- `/admin/dashboard`
- `/admin/cases`
- `/admin/users`
- `/admin/control-center`
- `/admin/analytics`
- `/government/appointments`
- `/government/positions`
- `/government/personnel`
- `/rubrics`
- `/audit-logs`
- `/ml-monitoring`
- `/ai-monitor`
- `/notifications`

---

## 4) Common Tasks For All Users

### 4.1 Update Profile and Security

1. Open profile menu (top-right avatar).
2. Click `Profile & Settings` (`/settings`) to update profile details.
3. Click `Security` (`/security`) to manage 2FA/security settings (non-applicant roles).
4. Click `Change Password` (`/change-password`) when needed.

### 4.2 Manage Notifications

1. Open `/notifications`.
2. Filter by `All`, `Unread`, `Read`, or `Archived`.
3. Use `Mark All as Read` to clear unread operational noise.
4. Archive old notifications to keep your list actionable.

Expected result:

- unread count in navbar decreases,
- archived items are removed from active list.

---

## 5) Applicant Task Guide

### 5.1 Accept Invitation and Start Candidate Session

Route options:

- Direct invite link: `/invite/:token`
- Candidate portal with token: `/candidate/access?token=...`

Steps:

1. Open the invite link.
2. Confirm your access token/session.
3. Review campaign requirements shown in candidate access.

Expected result:

- session is active,
- your case context is visible.

### 5.2 Upload Required Documents

1. In candidate access, pick your case.
2. Select document type.
3. Upload file.
4. Wait for verification state updates.

Expected result:

- file appears in document list,
- status progresses from queued/processing to verified/flagged/failed.

### 5.3 Complete Interview (When Assigned)

1. Open interview link from candidate access or notifications.
2. Complete interview responses.
3. Return to candidate access to monitor progress.

### 5.4 Check Status and Results

1. Open `/candidate/access`.
2. Use refresh in the results section.
3. Track progress timeline and final outcome state.

Typical timeline states you will see:

- invited
- registered
- in_progress
- completed
- reviewed
- approved / rejected / escalated

---

## 6) Operations Task Guide (Vetting Operations)

### 6.1 Create and Run a Campaign

1. Open `/campaigns`.
2. Create campaign.
3. Open the campaign workspace (`/campaigns/:campaignId`).
4. Confirm dashboard metrics load correctly.

### 6.2 Import Candidates and Send Invitations

1. In campaign workspace, use candidate import.
2. Submit candidate JSON rows.
3. Enable invitation sending if required.
4. Review import summary for successful vs failed rows.

Expected result:

- candidate enrollments are created,
- invitations are visible and can be resent.

### 6.3 Configure Rubrics

1. Open `/rubrics`.
2. Create or duplicate rubric.
3. Add/edit criteria and weights.
4. Activate rubric.
5. In campaign workspace, apply rubric version to campaign.

Important:

- rubric scoring is decision support,
- human reviewers still make final decisions.

### 6.4 Review Cases

1. Open `/applications`.
2. Filter by status/scope.
3. Open a case and inspect evidence.
4. Review document verification, interview context, and flags.
5. Record decision rationale in your workflow actions.

### 6.5 Run Background Checks

1. Open `/background-checks`.
2. Select case and check type.
3. Submit check (consent evidence required).
4. Refresh check status/events as needed.

### 6.6 Manage Interview Meetings

1. Open `/video-calls`.
2. Schedule or reschedule meeting.
3. Share participant details/invites.
4. Start/complete meeting and monitor timeline events.

---

## 7) Government Appointment Task Guide (GAMS)

### 7.1 Register Positions

1. Open `/government/positions`.
2. Fill required fields:
   - title
   - institution
   - appointment authority
3. Save.

Optional flags:

- public visibility,
- vacant status,
- confirmation required.

### 7.2 Register Personnel

1. Open `/government/personnel`.
2. Create personnel record.
3. Include contact and profile details.
4. Save.

Optional flags:

- active officeholder,
- public profile.

### 7.3 Create a Nomination (Appointment Record)

1. Open `/government/appointments`.
2. In `Create Appointment`, select:
   - position
   - nominee
   - optional campaign (appointment exercise)
3. Enter nomination details.
4. Save.

Expected result:

- appointment record exists in registry,
- nomination lifecycle starts in `nominated`.

### 7.4 Configure Approval Chain

1. In `/government/appointments`, create `Approval Stage Template` if not already present.
2. Add stages with:
   - order
   - required role
   - mapped status
3. Use required stages for governance-critical transitions.

### 7.5 Advance Stages Safely

1. On an appointment row, choose target status.
2. Provide stage context when required.
3. Add reason note/evidence links when needed.
4. Submit stage action.

Service-enforced status path:

- nominated -> under_vetting -> committee_review -> confirmation_pending -> appointed -> serving -> exited

Alternative terminal states:

- rejected
- withdrawn

### 7.6 Finalize Appointment or Rejection

- `appoint` and `reject` actions require appropriate authority.
- Final decision actions are audit tracked.

### 7.7 Publish to Gazette/Public Feed

1. Open appointment publication action.
2. Publish with reference/hash/notes when available.
3. If needed, revoke publication with mandatory revocation reason.

Expected result:

- only published + public records appear on public feeds.

---

## 8) Recommendation and Stage-Gating Rules (What Users Need To Know)

The platform uses two decision-support layers:

1. Rubric scoring layer (case scoring, trace, explanation).
2. Vetting Decision Recommendation layer (advisory recommendation + blocking/warning context).

For linked appointment cases, governance stages use recommendation context:

- entering `committee_review`, `confirmation_pending`, or `appointed` requires valid recommendation context,
- if blocking issues exist, users must provide rationale (`reason_note`) or process an authorized override before advancing,
- if recommendation is reject, appointing requires authorized override first.

Human authority is final.

- AI and recommendation outputs do not replace human decision-makers.

---

## 9) Public vs Internal Data (User Expectations)

Public feeds only show public-safe appointment records.

Public views are limited to published/public records such as:

- public positions,
- officeholder listings,
- gazette/open appointment feeds.

Internal vetting details are not meant for public exposure.

---

## 10) Troubleshooting (User-Facing)

### 10.1 "I Cannot Access This Page"

Likely cause: role/permission restriction.

Actions:

1. Confirm your logged-in account role.
2. Re-login if session is stale.
3. Ask admin if role/group assignment is missing.

### 10.2 "Stage Context Is Required"

Likely cause: appointment transition needs mapped approval stage.

Actions:

1. Select the correct stage for the target status.
2. Ensure prior required stages are complete.

### 10.3 "Blocking Issues Exist"

Likely cause: recommendation context contains unresolved blockers.

Actions:

1. Add `reason_note` when policy allows.
2. Complete required review/override governance action.

### 10.4 "Only Appointing Authority/Admin Can Finalize"

Likely cause: your role cannot perform final appointment decision actions.

Action:

- hand off to appointing-authority/admin account.

### 10.5 Notifications Are Empty or Stale

1. Refresh `/notifications`.
2. Check archived filter.
3. Confirm the triggering workflow action completed successfully.

---

## 11) Best Practices For Smooth Daily Use

1. Keep campaign and appointment records complete before advancing stages.
2. Use clear reason notes for any non-routine stage action.
3. Review warnings and blocking issues before final decisions.
4. Keep notifications triaged daily.
5. Use publication actions only after final governance decision is complete.
6. Never treat AI output as final authority.

---

## 12) Quick Page Index

### Public/Onboarding

- `/`
- `/subscribe`
- `/login`
- `/register`
- `/forgot-password`
- `/invite/:token`
- `/candidate/access`

### Core Authenticated

- `/dashboard`
- `/settings`
- `/security`
- `/change-password`
- `/notifications`

### Vetting Operations

- `/campaigns`
- `/applications`
- `/rubrics`
- `/video-calls`
- `/fraud-insights`
- `/background-checks`

### Government Operations (GAMS)

- `/government/positions`
- `/government/personnel`
- `/government/appointments`

### Admin Surfaces

- `/admin/dashboard`
- `/admin/cases`
- `/admin/users`
- `/admin/control-center`
- `/admin/analytics`
- `/audit-logs`
- `/ml-monitoring`
- `/ai-monitor`

---

End of manual.
