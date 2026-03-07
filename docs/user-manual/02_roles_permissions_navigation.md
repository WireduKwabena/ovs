# 2) Roles, Permissions, and Navigation

## 2.1 Supported Account Types

OVS user types:

- `admin` (system administrator),
- `hr_manager` (firm-side vetting operator),
- `applicant` (candidate participant).

## 2.2 Route Access Logic (Frontend)

The frontend enforces role-aware route guards:

- Admin-only routes: e.g. `/admin/*`, `/audit-logs`, `/ml-monitoring`, `/ai-monitor`.
- HR/Staff routes: campaigns, rubrics, applications, video calls, background checks.
- Applicant-restricted routes:
  - cannot access admin dashboards,
  - cannot access staff-only security pages.

## 2.3 Major Navigation Areas

Public pages:

- `/` landing page,
- `/subscribe`,
- `/login`,
- `/register`,
- `/forgot-password`,
- `/reset-password/:token`,
- billing callback routes.

Authenticated pages:

- `/dashboard`,
- `/settings`,
- `/security`,
- `/campaigns`,
- `/rubrics`,
- `/applications`,
- `/video-calls`,
- `/notifications`,
- monitoring and admin pages based on role.

## 2.4 Admin Responsibilities

Admins can:

- Access platform-wide dashboards and analytics.
- Manage users and high-level case oversight.
- View operational audit and monitoring surfaces.
- Control governance-sensitive areas.

Typical admin routes:

- `/admin/dashboard`
- `/admin/analytics`
- `/admin/users`
- `/admin/control-center`
- `/admin/cases`
- `/audit-logs`
- `/ml-monitoring`
- `/ai-monitor`

## 2.5 Operations User Responsibilities

Operations users can:

- Build and run vetting campaigns.
- Create and apply rubrics.
- Import and manage candidate lists.
- Monitor candidate progress and case outcomes.
- Schedule and manage video meeting workflows.

Typical operations routes:

- `/dashboard`
- `/campaigns`
- `/rubrics`
- `/applications`
- `/video-calls`
- `/background-checks`
- `/fraud-insights`
- `/notifications`

## 2.6 Candidate Responsibilities

Candidates typically interact through:

- invitation acceptance links,
- candidate access routes,
- application/document submission pages,
- interview session routes,
- result visibility routes.

Typical candidate entry points:

- `/invite/:token`
- `/candidate/access`
- limited application-interaction paths

## 2.7 Permission Design Notes

- Role checks run both in frontend route guards and backend permissions.
- UI visibility is not treated as sufficient security.
- API permissions remain authoritative for data access control.

## 2.8 Navigation Troubleshooting

If a user cannot see expected menu items:

1. Confirm account role in profile.
2. Confirm successful authentication and profile fetch.
3. Confirm no pending 2FA challenge state.
4. Check backend permissions or token freshness.
