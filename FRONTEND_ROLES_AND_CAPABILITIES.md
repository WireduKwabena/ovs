# Frontend: Roles, Capabilities & Access Control

This document describes every user type, their capabilities, the routes they can access, and the UI they see — as implemented in the frontend codebase. Refactoring issues are noted throughout.

---

## 1. The Identity Model

### 1.1 User Types (`auth.userType`)

The Redux store holds a single `userType` field (defined in `authSlice.ts:30`) that drives all layout and route decisions:

| Value | Source | Meaning |
|---|---|---|
| `"platform_admin"` | Resolved by `resolveUserType()` | Superuser or flagged `is_platform_admin` by backend |
| `"admin"` | Raw backend payload | Legacy alias for `platform_admin`; treated identically throughout the app |
| `"org_admin"` | Resolved by `resolveUserType()` | Admin-type user with an active organization context |
| `"internal"` | Raw backend payload | Workflow operator (vetting officer, committee member, etc.) |
| `"applicant"` | Raw backend payload | External candidate/applicant |
| `null` | Initial / logged-out | Unauthenticated |

#### `resolveUserType()` logic (`authSlice.ts:76-107`)

```
1. is_platform_admin flag === true  OR  user.is_superuser === true
       → "platform_admin"
2. type hint is "admin" | "platform_admin" | "org_admin"
     AND active_organization present  → "org_admin"
     AND user.is_staff === true       → "platform_admin"
     otherwise                        → "org_admin"
3. Fall through to raw type hint
```

> **Refactor note:** Step 2 has an ambiguous branch: an `org_admin`-typed user with no active organization and `is_staff=true` becomes `platform_admin`. This is a side-effect of merging staff detection into org resolution. Consider splitting these into explicit backend flags rather than inferring from `is_staff`.

### 1.2 RBAC: Roles

Roles are Django group names granted to users and exposed via the auth payload. They are stored in `auth.roles[]` and resolved in `useAuth.ts` by merging three sources:

```
resolvedRoles = union(auth.roles, user.roles, user.group_roles)
```

| Role | Functional Meaning |
|---|---|
| `registry_admin` | Manages government positions, personnel, and campaigns |
| `vetting_officer` | Runs the intake/vetting stage of an appointment |
| `committee_member` | Participates in committee review stage |
| `committee_chair` | Chairs the committee, can vote and manage the review |
| `appointing_authority` | Makes the final appointment decision |
| `publication_officer` | Publishes gazette entries |
| `auditor` | Read-only audit access |

### 1.3 RBAC: Capabilities

Capabilities are fine-grained permission strings from the backend, stored in `auth.capabilities[]`. Defined in `utils/frontendAuthz.ts`:

| Capability | Grants access to |
|---|---|
| `gams.registry.manage` | Positions, personnel, campaigns, rubrics |
| `gams.appointment.stage` | Advancing appointment stages |
| `gams.appointment.decide` | Final appointment decision |
| `gams.appointment.publish` | Publishing gazette entries |
| `gams.appointment.view_internal` | Internal appointment views |
| `gams.audit.view` | Audit log pages |

> **Refactor note:** `INTERNAL_WORKFLOW_ROUTE_CAPABILITIES` and `GOVERNMENT_WORKFLOW_CAPABILITIES` are defined as two separate named constants but are byte-for-byte identical arrays. They can be merged into one.
>
> Similarly, `CAMPAIGN_MANAGE_CAPABILITIES` and `RUBRIC_MANAGE_CAPABILITIES` are both just `["gams.registry.manage"]`. This naming adds no clarity and should be collapsed into direct usage of `REGISTRY_ROUTE_CAPABILITIES`.

---

## 2. Layouts by User Type

`AppShell` (`App.tsx:308`) selects a layout shell based on `userType` **before** rendering routes:

```
userType === "platform_admin" | "admin"  →  SystemAdminLayout  (dedicated sidebar)
userType === "org_admin"                 →  OrgAdminLayout     (org-scoped sidebar)
userType === "internal"                  →  Navbar             (top + left sidebar)
userType === "applicant"                 →  No nav             (clean fullscreen)
unauthenticated or public route          →  No nav
```

> **Refactor note:** `AppShell` calls `renderRoutes()` — which defines the full `<Routes>` tree — inside three separate layout branches. This means the entire route tree JSX is created three times in the component tree. While React deduplicates the work during reconciliation, the pattern makes the code harder to reason about. The routes should be lifted above the layout shell switch so the layout wraps the routes rather than containing them.

---

## 3. Role Breakdown

### 3.1 Platform Admin (`platform_admin` / `admin`)

**Who:** Superusers, staff flagged `is_platform_admin` by backend.

**Layout:** `SystemAdminLayout` — a fixed sidebar with:

| Sidebar Link | Route |
|---|---|
| Platform Dashboard | `/admin/platform/dashboard` |
| AI Infrastructure | `/admin/platform/ai-engine` |
| Organization Registry | `/admin/platform/registry` |
| Billing & Plans | `/admin/platform/billing` |
| System Health | `/admin/platform/health` |
| Platform Audit Logs | `/admin/platform/logs` |

**Route guard:** All platform admin routes use `<ProtectedRoute platformAdminOnly>` (`App.tsx:759-795`), which checks:
```typescript
const isPlatformAdmin = userType === "platform_admin" || userType === "admin";
if (platformAdminOnly && !isPlatformAdmin) → redirect to fallback dashboard
```

**Pages and capabilities:**

| Page | What it shows |
|---|---|
| `PlatformDashboardPage` | Platform-wide org count, growth metrics, billing posture, system alerts |
| `AiInfrastructurePage` | AI service health, model status, inference pipeline metrics |
| `OrganizationRegistryPage` | All registered organizations; activate/deactivate orgs |
| `BillingManagementPage` | Revenue metrics, subscription plan management, Stripe/Paystack gateway health |
| `SystemHealthPage` | Real-time service latency, Celery worker health, reminder runtime status |
| `PlatformAuditLogsPage` | All platform-level administrative audit events |

**What platform admins are blocked from:**

- Org-scoped routes (`/admin/org/:orgId/*`) — `OrganizationScopedRoute` explicitly redirects `platform_admin`/`admin` to the platform dashboard (`App.tsx:258`).
- Workspace workflow routes — `disallowUserTypes={["applicant", "platform_admin"]}` blocks them from `/workspace/applications`, `/workspace/campaigns`, etc.
- Legacy organization routes redirect to the platform dashboard via `LegacyOrganizationRedirect`.

**Dashboard redirect:** `getDashboardPathForUser()` in `authRouting.ts` → `/admin/platform/dashboard`.

---

### 3.2 Org Admin (`org_admin`)

**Who:** Organization-scoped admins. Resolved when a user has an `admin`/`org_admin` type hint AND an active organization is set in context.

**Layout:** `OrgAdminLayout` — a fixed sidebar scoped to the active organization:

| Sidebar Link | Route |
|---|---|
| Org Dashboard | `/admin/org/:orgId/dashboard` |
| Vetting Cases | `/admin/org/:orgId/cases` |
| Committees | `/admin/org/:orgId/committees` |
| Personnel | `/admin/org/:orgId/users` |
| Onboarding | `/admin/org/:orgId/onboarding` |
| Subscription | `/settings` |

**Route guard:** All org-admin routes use `OrganizationScopedRoute` (`App.tsx:212`), which:
1. Reads `:orgId` from the URL.
2. Dispatches `switchActiveOrganization(orgId)` if it doesn't match the current active org.
3. Wraps children in `<ProtectedRoute disallowUserTypes={["applicant", "platform_admin"]} requireOrganizationGovernance>`.
4. Shows a loader while the org switch is in progress.
5. Redirects to `/organization/setup?next=...` if the org ID cannot be resolved.

The `requireOrganizationGovernance` flag checks `canManageOrganizationGovernance()` which requires:
- `isAdmin` flag, OR
- An active `OrganizationMembership` in the matching org with a recognized governance role.

**Pages and capabilities:**

| Page | What it shows |
|---|---|
| `OrgDashboardPage` | Org-level stats: member count, active cases, pipeline summary |
| `OrgCasesPage` | Vetting cases scoped to the organization |
| `OrgUsersPage` | Users/members within the organization |
| `OrganizationMembersPage` | Detailed member management |
| `OrganizationCommitteesPage` | Committees within the org |
| `CommitteeDetailPage` | Individual committee detail and memberships |
| `OrganizationOnboardingPage` | Onboarding token / invitation management |

**Multi-org support:** If the user has memberships in multiple organizations, `OrgAdminLayout` renders an org-switcher dropdown. Switching calls `selectActiveOrganization()` which dispatches `switchActiveOrganization` to the Redux store and re-fetches the profile.

**What org admins are blocked from:**
- Platform admin routes (`platformAdminOnly` guard redirects them).
- Applicant routes.

**Dashboard redirect:** `getDashboardPathForUser()` → `/dashboard` (generic dashboard, which then further redirects based on active org state).

> **Refactor note:** The `OrgAdminLayout` sidebar hardcodes the "Subscription" link to `/settings`. This is inconsistent — `/settings` is a generic user settings page that all roles can access, not an org-admin-specific subscription page. It should link to a dedicated subscription/billing management page or be removed from the org-admin sidebar.

---

### 3.3 Internal Workflow User (`internal`)

**Who:** Government workflow operators — vetting officers, committee members, committee chairs, appointing authorities, registry admins, publication officers, auditors.

**Layout:** Standard `Navbar` component — a combination top bar and collapsible left sidebar. Navigation links rendered depend on which capabilities and roles the user holds.

**Dashboard redirect:** `getDashboardPathForUser()` → `/dashboard`.

**Route prefix:** `/workspace/*`

**Pages and their guards:**

| Page | Route | Capability / Role Required |
|---|---|---|
| `WorkspaceHomePage` | `/workspace/home` | Not applicant or platform_admin |
| `ApplicationsPage` | `/workspace/applications` | `INTERNAL_WORKFLOW_ROUTE_CAPABILITIES` |
| `ApplicationDetailPage` | `/workspace/applications/:caseId` | `INTERNAL_WORKFLOW_ROUTE_CAPABILITIES` |
| `CampaignsPage` | `/workspace/campaigns` | `CAMPAIGN_MANAGE_CAPABILITIES` (= `gams.registry.manage`) |
| `CampaignWorkspacePage` | `/workspace/campaigns/:id` | `CAMPAIGN_MANAGE_CAPABILITIES` |
| `VideoCallsPage` | `/workspace/video-calls` | `INTERNAL_WORKFLOW_ROUTE_CAPABILITIES` |
| `AuditLogsPage` | `/workspace/audit-logs` | `gams.audit.view` (admin fallback allowed) |
| `FraudInsightsPage` | `/workspace/fraud-insights` | `INTERNAL_WORKFLOW_ROUTE_CAPABILITIES` |
| `BackgroundChecksPage` | `/workspace/background-checks` | `INTERNAL_WORKFLOW_ROUTE_CAPABILITIES` |
| `RubricsPage` / `RubricBuilderPage` | `/workspace/rubrics` | `RUBRIC_MANAGE_CAPABILITIES` (= `gams.registry.manage`) |
| `GovernmentPositionsPage` | `/workspace/government/positions` | `REGISTRY_ROUTE_CAPABILITIES` (= `gams.registry.manage`) |
| `GovernmentPersonnelPage` | `/workspace/government/personnel` | `REGISTRY_ROUTE_CAPABILITIES` |
| `AppointmentsRegistryPage` | `/workspace/government/appointments` | `APPOINTMENT_ROUTE_CAPABILITIES` |
| `NotificationsPage` | `/workspace/notifications` | Not applicant |

**Derived permissions in `useAuth`:**

| Flag | How Derived | Used By |
|---|---|---|
| `canAccessAppointments` | Has any `APPOINTMENT_ROUTE_CAPABILITIES` OR any `APPOINTMENT_WORKFLOW_ROLES` | Navbar link visibility |
| `canAdvanceAppointmentStage` | Has any `STAGE_ACTOR_ROLES` OR `gams.appointment.stage` | Stage action buttons |
| `canFinalizeAppointment` | Has `appointing_authority` role OR `gams.appointment.decide` | Final decision UI |
| `canPublishAppointment` | Has `publication_officer`/`appointing_authority` role OR `gams.appointment.publish` | Publish button |
| `canViewAppointmentStageActions` | Has `committee_member`/`committee_chair` role | Stage history panel |
| `canAccessCampaigns` | Has `gams.registry.manage` | Navbar link / route guard |
| `canManageRubrics` | Has `gams.registry.manage` | Navbar link / route guard |
| `canViewAuditLogs` | `isAdmin` OR has `gams.audit.view` | Navbar link |
| `canAccessVideoCalls` | Has any `INTERNAL_WORKFLOW_ROUTE_CAPABILITIES` | Navbar link |
| `canAccessInternalWorkflow` | Has any `GOVERNMENT_WORKFLOW_CAPABILITIES` OR any `APPOINTMENT_WORKFLOW_ROLES` | General gate |
| `canManageActiveOrganizationGovernance` | Has admin access + governance role + active org | `OrganizationScopedRoute` |

**Navbar link grouping (`Navbar.tsx`):**

- **Primary links (always in sidebar):** Cases, Users (when user has org governance + active org)
- **Secondary links (behind "More" toggle):** Appointment Workflow, Offices, Nominees, Members, Committees, Onboarding, Subscription

The "More" button is always rendered in the DOM regardless of whether secondary links exist, so it's visible even to users who have no secondary links (e.g., platform admins using the workspace accidentally). The secondary links render conditionally based on `canAccessAppointments`, `canAccessRegistry`, and `canManageActiveOrganizationGovernance`.

---

### 3.4 Applicant (`applicant`)

**Who:** External candidates applying for positions.

**Layout:** No navbar. Full-screen clean layout.

**Dashboard redirect:** `getDashboardPathForUser()` → `/candidate/home`.

**Pages:**

| Page | Route | Guard |
|---|---|---|
| `CandidateHomePage` | `/candidate/home` | None (publicly accessible path, but content gated by auth state) |
| `CandidateInterrogationPage` | `/candidate/interview/:applicationId` | None explicit (applicationId required) |

**Blocked from:**
- All `/workspace/*` routes (`disallowUserTypes` includes `"applicant"`)
- All platform admin routes (`platformAdminOnly`)
- `/security` page (`disallowUserTypes={["applicant"]}`)
- Notifications (`disallowUserTypes={["applicant"]}`)

---

### 3.5 Public / Unauthenticated

**Pages accessible without authentication:**

| Page | Route |
|---|---|
| `HomePage` | `/` |
| `PublicGazettePage` | `/gazette` |
| `PublicTransparencyPage` | `/transparency` |
| `PublicAppointmentDetailPage` | `/transparency/appointments/:id` |
| `SubscriptionPlansPage` | `/subscribe` |
| `LoginPage` | `/login` (UnauthenticatedRoute) |
| `TwoFactorPage` | `/login/2fa` (UnauthenticatedRoute with 2FA flag) |
| `RegisterPage` | `/register` (UnauthenticatedRoute) |
| `ForgotPasswordPage` | `/forgot-password` (UnauthenticatedRoute) |
| `ResetPasswordPage` | `/reset-password/:token` (UnauthenticatedRoute) |
| `OrganizationAdminSignupPage` | `/organization/get-started` (UnauthenticatedRoute) |
| `InvitationAcceptPage` | `/invite/:token` |
| `BillingCheckoutResultPage` | `/billing/success`, `/billing/cancel` |

`UnauthenticatedRoute` redirects authenticated users to their dashboard via `resolveUnauthenticatedRouteRedirect()`.

---

## 4. Route Path System (`utils/appPaths.ts`)

| Constant | Base Path | Used By |
|---|---|---|
| `PLATFORM_ADMIN_BASE_PATH` | `/admin/platform` | Platform admin routes |
| `ORG_ADMIN_BASE_PATH` | `/admin/org` | Org admin routes |
| `WORKSPACE_BASE_PATH` | `/workspace` | Internal workflow routes |
| `CANDIDATE_BASE_PATH` | `/candidate` | Applicant routes |

Helper functions:
- `getPlatformAdminPath(segment)` → `/admin/platform/{segment}`
- `getOrgAdminPath(orgId, segment)` → `/admin/org/{orgId}/{segment}`
- `getWorkspacePath(segment)` → `/workspace/{segment}`
- `getCandidatePath(segment)` → `/candidate/{segment}`
- `getOrganizationSetupPath(next?)` → `/organization/setup?next={next}`

---

## 5. `ProtectedRoute` Guard Props Reference

```typescript
interface ProtectedRouteProps {
  adminOnly?                    // allows any admin (platform or org)
  platformAdminOnly?            // allows only platform_admin / admin
  orgAdminOnly?                 // allows only org_admin
  disallowUserTypes?            // blocks listed types
  requiredRoles?                // must have at least one of these roles
  requiredCapabilities?         // must have at least one of these capabilities
  legacyUserTypeFallback?       // if capabilities missing, admin fallback
  requireOrganizationGovernance? // must have active org + governance role
  requireActiveOrganization?    // must have any active org set
  activeOrganizationRedirectPath? // where to send if no active org
}
```

Guard evaluation order (first failure wins):
1. Redux rehydration check → show loader
2. Not authenticated / 2FA pending → redirect to `/login` or `/login/2fa`
3. `adminOnly` → redirect to fallback dashboard if not any admin
4. `platformAdminOnly` → redirect if not `platform_admin`/`admin`
5. `orgAdminOnly` → redirect if not `org_admin`
6. `disallowUserTypes` check (using normalized effective type) → redirect
7. `requiredRoles` check → redirect
8. `requireOrganizationGovernance` check → redirect
9. `requireActiveOrganization` check → redirect to setup page
10. `requiredCapabilities` check (with legacy fallback) → redirect or allow

---

## 6. Legacy Route Redirects

The app maintains several legacy URL paths that redirect to the current canonical paths:

| Legacy Path | Redirects To | Mechanism |
|---|---|---|
| `/admin/dashboard` | `/admin/platform/dashboard` | `LegacyPlatformRedirect` |
| `/admin/analytics` | `/admin/platform/analytics` → dashboard | `LegacyPlatformRedirect` + redirect |
| `/admin/register` | `/admin/platform/register` → dashboard | `LegacyPlatformRedirect` + redirect |
| `/admin/control-center` | `/admin/platform/control-center` → dashboard | `LegacyPlatformRedirect` + redirect |
| `/admin/users` | `/admin/org/:orgId/users` | `LegacyOrganizationRedirect` |
| `/admin/applications`, `/admin/cases` | `/admin/org/:orgId/cases` | `LegacyOrganizationRedirect` |
| `/organization/dashboard` | `/admin/org/:orgId/dashboard` | `LegacyOrganizationRedirect` |
| `/organization/members` | `/admin/org/:orgId/members` | `LegacyOrganizationRedirect` |
| `/organization/committees` | `/admin/org/:orgId/committees` | `LegacyOrganizationRedirect` |
| `/organization/committees/:id` | `/admin/org/:orgId/committees/:id` | `LegacyOrganizationCommitteeRedirect` |
| `/admin/cases/:caseId` | `/admin/org/:orgId/cases/:caseId` | `LegacyOrganizationCaseReviewRedirect` |
| `/workspace` | `/workspace/home` | `LegacyWorkspaceRedirect` |
| `/candidate/access` | `/candidate/home` | `LegacyCandidateRedirect` |
| `/ml-monitoring`, `/ai-monitor` | `/admin/platform/ml-monitoring` → dashboard | `LegacyPlatformRedirect` + redirect |

`LegacyOrganizationRedirect` and related components always check `userType` first — if `platform_admin`/`admin`, they redirect to the platform dashboard instead of attempting org resolution.

---

## 7. Two-Factor Authentication Flow

`UnauthenticatedRoute` and `ProtectedRoute` both handle 2FA state:

- If `twoFactorRequired === true` AND `twoFactorToken` is present → redirect to `/login/2fa`
- The 2FA page is mounted on `UnauthenticatedRoute allowTwoFactorChallenge` to allow access while the 2FA challenge is active but before full authentication
- After successful `verifyTwoFactor`, the store applies full session state including `userType`, `roles`, `capabilities`, and org context

---

## 8. Refactoring Issues Summary

| # | File | Issue |
|---|---|---|
| 1 | `authSlice.ts:94-103` | `resolveUserType` has an ambiguous branch: `is_staff` on an `org_admin`-typed user without active org yields `platform_admin`, which is a non-obvious side effect |
| 2 | `authSlice.ts:76-107` | `"admin"` is a legacy raw value from the backend but leaks into the normalized `userType`. It should be normalized to `"platform_admin"` at parse time so the rest of the app only ever sees the canonical 4 types |
| 3 | `frontendAuthz.ts:9,20` | `INTERNAL_WORKFLOW_ROUTE_CAPABILITIES === GOVERNMENT_WORKFLOW_CAPABILITIES` — two names for the same constant. Merge into one |
| 4 | `frontendAuthz.ts:14,16` | `CAMPAIGN_MANAGE_CAPABILITIES` and `RUBRIC_MANAGE_CAPABILITIES` are both `["gams.registry.manage"]`. Merge into `REGISTRY_ROUTE_CAPABILITIES` |
| 5 | `App.tsx` | Massive route duplication: every `/workspace/*` route is mirrored with an identical legacy `/*` sibling (e.g., `/applications` and `/workspace/applications`). These legacy paths should be collapsed into `<Navigate>` redirects rather than re-defining the same route with the same guard |
| 6 | `App.tsx:308-1066` | `renderRoutes()` is called in three separate layout branches. The Routes tree should live above the layout switch so the layout wraps routes rather than containing them |
| 7 | `ProtectedRoute.tsx:67-73` / `useAuth.ts:55-61` | Role merging logic (`union(auth.roles, user.roles, user.group_roles)`) is duplicated in both files. Extract into a shared utility |
| 8 | `ProtectedRoute.tsx:78` / `useAuth.ts:106` | `hasAdminAccess` and `isAdmin` are defined differently in the two files: `ProtectedRoute` includes `isOrgAdmin` in `hasAdminAccess`, while `useAuth` does not include it in `isAdmin`. This inconsistency could cause subtle authorization bugs |
| 9 | `OrgAdminLayout.tsx:47` | "Subscription" links to `/settings` (generic user settings) instead of a real subscription management page |
| 10 | `authSlice.ts:533-540` / `authSlice.ts:566-573` | After login and after 2FA verify, org context is reset to empty arrays. This is correct, but the identical object literal is repeated twice verbatim. Extract as a constant |
| 11 | `useAuth.ts:72` | `resolvedCommittees` conditional is re-evaluated on every render, causing ESLint `react-hooks/exhaustive-deps` warning (already flagged in lint audit). Wrap in `useMemo` |
| 12 | `App.tsx:120` | `ORG_WORKFLOW_DISALLOWED_USER_TYPES` is typed as `Array<"applicant" | "platform_admin">` but `disallowUserTypes` prop expects `Array<"applicant" | "internal" | "org_admin" | "platform_admin">`. TypeScript accepts this because it's a subset, but the type annotation could be more precise |
