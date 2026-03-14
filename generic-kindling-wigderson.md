# Redesign Front‑End Role‑Based Dashboards

## Context & Why

The OVS‑Redo platform serves three distinct audiences:

1. **Platform administrators** – manage the SaaS product itself (billing, AI performance, global settings). They are the Django super‑users (`user.is_superuser` or `user_type == "admin"`).
2. **Organization administrators** – each subscribing organisation has an admin who manages that org’s users, cases, campaigns, documents, etc. Their permissions are granted via `ROLE_ADMIN` on the organization and are evaluated through `is_admin_user` in the backend.
3. **Regular users** – internal staff, candidates/nominees, and other roles that only see data they are allowed to act on.

The current front‑end mixes all of these concerns under `src/pages/admin/*`. This makes the UI confusing and risks leaking organisation‑specific data to platform admins and vice‑versa.

## Goal

Create a clear separation of UI layers that mirrors the permission model already implemented in the backend. No code changes to the backend are required because the permission helpers (`is_platform_admin_user`, `is_admin_user`, `is_internal_user`) already differentiate the three groups.

## High‑Level Plan

| Phase | Tasks | Owner | Dependencies |
|------|------|------|--------------|
| **1️⃣ Exploration** | Verify permission helpers and existing API endpoints for platform vs organisation scopes. | – | – |
| **2️⃣ Routing Refactor** | Introduce role‑based route prefixes: `/admin/platform/*`, `/admin/org/:orgId/*`, `/workspace/*`, `/candidate/*`. Update `App.tsx` (React‑Router) to mount guard components that read the logged‑in user and redirect to the correct base path. | Front‑end | Phase 1 |
| **3️⃣ Page Restructure** | Move existing files into new folders and rename where appropriate. | Front‑end | Phase 2 |
| **4️⃣ Platform Admin UI** | Keep pages that are truly platform‑wide: `AdminDashboardPage`, `AdminAnalyticsPage`, `AdminControlCenterPage` (links to Django admin), `SubscriptionPlansPage`, `BillingCheckoutResultPage`, `AiMonitorPage`. Ensure all API calls use the `platform/` namespace (e.g., `adminService.getBillingStats`). | Front‑end | Phase 3 |
| **5️⃣ Organisation Admin UI** | Create `src/pages/org-admin/` with: `OrgDashboardPage` (summary of org health), `OrgCasesPage` (formerly `AdminCasesPage` but filtered by organisation), `OrgUsersPage` (formerly `AdminUsersPage` but filtered to the org), `OrgSettingsPage`, `OrgDocumentsPage`. Re‑use existing components (`AdminCasesPage`, `AdminUsersPage`) after converting the service calls to include the org header (`X-Organization-ID`). | Front‑end | Phase 3 |
| **6️⃣ Internal User Workspace** | Add `src/pages/workspace/` containing pages like `HomePage`, `AuditLogsPage`, `NotificationsPage`, `OperationsDashboardPage`. These pages already exist; they will be moved and their routes guarded by `is_internal_user`/`is_platform_admin_user` check. | Front‑end | Phase 2 |
| **7️⃣ Candidate Workspace** | Add `src/pages/candidate/` (or `src/pages/nominee/`) with pages that already target applicants: `CandidateAccessPage`, `RegisterPage`, `ForgotPasswordPage`, `UploadDocumentPage` (currently under `ApplicationDetailPage` etc.). Ensure these pages call the applicant‑specific endpoints that check `user_type == "applicant"`. | Front‑end | Phase 2 |
| **8️⃣ Navigation Updates** | Update the top‑level navigation component to render menu groups based on `user_type` and default organisation membership. Platform admins see *Platform* menu; organisation admins see *Organisation* menu; internal users see *Workspace*; candidates see *Candidate* menu. | Front‑end | Phase 4 |
| **9️⃣ Service Layer Adjustments** | Extend `admin.service.ts` with a `platform` namespace (e.g., `getPlatformBilling()`) and an `org` namespace (`getOrgCases(orgId)`). Add a small wrapper that reads the currently selected organisation from the JWT or from `User.get_primary_organization_membership()`. | Front‑end | Phase 5 |
| **🔟 Testing & Verification** | Update unit tests (`*.test.tsx`) to import pages from the new paths. Add integration tests that simulate each user type and verify they cannot navigate to another role’s routes. Run the full front‑end test suite (`npm test`) and the backend tests (`python manage.py test`). | QA | All previous phases |

## Backend Confirmation (already satisfied)

- Permission helpers (`is_platform_admin_user`, `is_admin_user`) exist in `backend/apps/core/permissions.py` and are used by all viewsets.
- `OrganizationMembership` provides the organisation context via `active_organization_memberships()`.
- No new API endpoints are required; we only need to **ensure** that the front‑end includes the `X-Organization-ID` header (or uses the standard session header) when calling organisation‑scoped endpoints. The backend will filter based on the user’s membership automatically.

## Detailed Front‑End Tasks

1. **Create folder hierarchy**

   ```
   src/pages/platform-admin/
   src/pages/org-admin/
   src/pages/workspace/
   src/pages/candidate/
   ```

2. **Move files**
   - Platform admin:
     - `AdminDashboardPage.{tsx, test.tsx}` → `platform-admin/PlatformDashboardPage.*`
     - `AdminAnalyticsPage.tsx` → `platform-admin/AnalyticsPage.tsx`
     - `AdminControlCenterPage.tsx` → `platform-admin/ControlCenterPage.tsx`
     - `SubscriptionPlansPage.*` → `platform-admin/SubscriptionPlansPage.*`
     - `BillingCheckoutResultPage.*` → `platform-admin/BillingResultPage.*`
   - Organisation admin:
     - `AdminCasesPage.{tsx,test}` → `org-admin/OrgCasesPage.*`
     - `AdminUsersPage.{tsx,test}` → `org-admin/OrgUsersPage.*`
     - Create thin wrapper components `OrgDashboardPage.tsx` that import the existing `AdminDashboardPage` UI but pass the organisation ID via props.
   - Workspace:
     - Move generic user pages (`HomePage`, `AuditLogsPage`, `NotificationsPage`, `OperationsDashboardPage`, etc.) into `workspace/`.
   - Candidate:
     - Move applicant‑focused pages (`CandidateAccessPage`, `RegisterPage`, `ForgotPasswordPage`, `ApplicationDetailPage`, …) into `candidate/`.
3. **Update routing** (`src/App.tsx` or wherever `<Routes>` are defined):

   ```tsx
   <Route path="/admin/platform/*" element={<RequirePlatformAdmin><PlatformLayout /></RequirePlatformAdmin>} />
   <Route path="/admin/org/:orgId/*" element={<RequireOrgAdmin><OrgLayout /></RequireOrgAdmin>} />
   <Route path="/workspace/*" element={<RequireInternalUser><WorkspaceLayout /></RequireInternalUser>} />
   <Route path="/candidate/*" element={<RequireCandidate><CandidateLayout /></RequireCandidate>} />
   ```

   Guard components will read the auth context (JWT) and call the backend helper `active_organization_memberships()` to confirm the role.
4. **Navigation component** (`src/components/common/Navbar.tsx`):
   - Add conditional rendering based on `user.user_type` and whether `user.get_primary_organization_membership()` exists.
   - Highlight the active base path (`/admin/platform`, `/admin/org/:id`, `/workspace`, `/candidate`).
5. **Service layer** (`src/services/admin.service.ts`):
   - Add methods `getOrgCases(orgId, params)`, `getOrgUsers(orgId, params)`, etc., that automatically attach the org header.
   - Keep existing platform‑wide methods (`getBillingStats`, `getAiMetrics`).
6. **Update components** that fetch data:
   - In `AdminCasesPage` (now `OrgCasesPage`) replace direct calls to `adminService.getCases` with `adminService.getOrgCases(orgId, …)`.
   - In `AdminUsersPage` (now `OrgUsersPage`) do the same for user management.
7. **Tests**
   - Update import paths in all `*.test.tsx` files to reflect new locations.
   - Add role‑based test cases ensuring a platform admin cannot access `/admin/org/:orgId/*` routes and vice‑versa.
8. **Documentation**
   - Update `README.md` and any front‑end contribution docs to describe the new folder layout and routing conventions.

## Verification Checklist

- [ ] Logging in as a Django super‑user lands on `/admin/platform/dashboard`.
- [ ] Logging in as an organisation admin (user with `ROLE_ADMIN` in an org) lands on `/admin/org/<org-id>/dashboard`.
- [ ] Internal staff (non‑admin) lands on `/workspace/home`.
- [ ] Candidate logs in and lands on `/candidate/home` and cannot reach any `/admin/*` routes.
- [ ] API calls from the organisation admin UI include the correct `X-Organization-ID` header and return only the organisation’s data.
- [ ] Platform admin UI never shows organisation‑specific data (case lists, documents, etc.).
- [ ] All unit and integration tests pass (`npm test`, `python manage.py test`).

---
  **Next Steps**

1. Confirm that the permission helpers identified in `backend/apps/core/permissions.py` are indeed used by all DRF viewsets that serve the admin UI (they are). If any viewset is missing the check, note it for a later backend patch.
2. Proceed with the front‑end restructuring as outlined above.

*If any detail of the folder naming, route structure, or API wrapper approach needs adjustment, let me know so the plan can be refined.*
