import React, { Suspense, useEffect, useRef, useState } from "react";
import {
  BrowserRouter as Router,
  Navigate,
  Route,
  Routes,
  useLocation,
  useParams,
} from "react-router-dom";
import { Loader } from "lucide-react";
import { useDispatch, useSelector } from "react-redux";

import { ProtectedRoute } from "./components/auth/ProtectedRoute";
import { UnauthenticatedRoute } from "./components/auth/UnauthenticatedRoute";
import { ErrorBoundary } from "./components/common/ErrorBoundary";
import {
  fetchProfile,
  silentRefresh,
  REFRESH_TOKEN_SESSION_KEY,
  switchActiveOrganization,
} from "./store/authSlice";
import { type AppDispatch, type RootState } from "./app/store";
import {
  APPOINTMENT_ROUTE_CAPABILITIES,
  CAMPAIGN_MANAGE_CAPABILITIES,
  INTERNAL_WORKFLOW_ROUTE_CAPABILITIES,
  REGISTRY_ROUTE_CAPABILITIES,
  RUBRIC_MANAGE_CAPABILITIES,
} from "./utils/frontendAuthz";
import {
  getCandidatePath,
  getOrgAdminPath,
  getOrganizationSetupPath,
  getPlatformAdminPath,
  getWorkspacePath,
} from "./utils/appPaths";
import { SystemAdminLayout } from "./components/layouts/SystemAdminLayout";
import { OrgAdminLayout } from "./components/layouts/OrgAdminLayout";
import { AuditorLayout } from "./components/layouts/AuditorLayout";

const Navbar = React.lazy(() =>
  import("./components/common/Navbar").then((module) => ({
    default: module.Navbar,
  })),
);
const HomePage = React.lazy(() => import("./pages/HomePage"));
const PublicGazettePage = React.lazy(() => import("./pages/PublicGazettePage"));
const PublicTransparencyPage = React.lazy(
  () => import("./pages/PublicTransparencyPage"),
);
const PublicAppointmentDetailPage = React.lazy(
  () => import("./pages/PublicAppointmentDetailPage"),
);
const SubscriptionPlansPage = React.lazy(
  () => import("./pages/SubscriptionPlansPage"),
);
const OrganizationAdminSignupPage = React.lazy(
  () => import("./pages/OrganizationAdminSignupPage"),
);
const OrganizationSetupPage = React.lazy(
  () => import("./pages/OrganizationSetupPage"),
);
const OrgDashboardPage = React.lazy(
  () => import("./pages/org-admin/OrgDashboardPage"),
);
const OrgUsersPage = React.lazy(() => import("./pages/org-admin/OrgUsersPage"));
const WorkspaceHomePage = React.lazy(
  () => import("./pages/workspace/WorkspaceHomePage"),
);
const CandidateHomePage = React.lazy(
  () => import("./pages/candidate/CandidateHomePage"),
);
const PlatformDashboardPage = React.lazy(
  () => import("./pages/platform-admin/PlatformDashboardPage"),
);
const OrganizationRegistryPage = React.lazy(
  () => import("./pages/platform-admin/OrganizationRegistryPage"),
);
const SystemHealthPage = React.lazy(
  () => import("./pages/platform-admin/SystemHealthPage"),
);
const BillingManagementPage = React.lazy(
  () => import("./pages/platform-admin/BillingManagementPage"),
);
const PlatformAuditLogsPage = React.lazy(
  () => import("./pages/platform-admin/PlatformAuditLogsPage"),
);
const AiInfrastructurePage = React.lazy(
  () => import("./pages/platform-admin/AiInfrastructurePage"),
);
const OrganizationMembersPage = React.lazy(
  () => import("./pages/OrganizationMembersPage"),
);
const OrganizationCommitteesPage = React.lazy(
  () => import("./pages/OrganizationCommitteesPage"),
);
const CommitteeDetailPage = React.lazy(
  () => import("./pages/CommitteeDetailPage"),
);
const OrganizationOnboardingPage = React.lazy(
  () => import("./pages/OrganizationOnboardingPage"),
);
const LoginPage = React.lazy(() => import("./pages/LoginPage"));
const TwoFactorPage = React.lazy(() => import("./pages/TwoFactorPage"));
const RegisterPage = React.lazy(() => import("./pages/RegisterPage"));
const ForgotPasswordPage = React.lazy(
  () => import("./pages/ForgotPasswordPage"),
);
const EmailSentPage = React.lazy(() => import("./pages/EmailSentPage"));
const ResetPasswordPage = React.lazy(() => import("./pages/ResetPasswordPage"));
const BillingCheckoutResultPage = React.lazy(
  () => import("./pages/BillingCheckoutResultPage"),
);
const InvitationAcceptPage = React.lazy(
  () => import("./pages/InvitationAcceptPage"),
);
const DashboardPage = React.lazy(() => import("./pages/DashboardPage"));
const ChangePasswordPage = React.lazy(
  () => import("./pages/ChangePasswordPage"),
);
const UserSettingsPage = React.lazy(() => import("./pages/UserSettingsPage"));
const SecurityPage = React.lazy(() => import("./pages/SecurityPage"));
const FraudInsightsPage = React.lazy(() => import("./pages/FraudInsightsPage"));
const BackgroundChecksPage = React.lazy(
  () => import("./pages/BackgroundChecksPage"),
);
const AuditLogsPage = React.lazy(() => import("./pages/AuditLogsPage"));
const CampaignsPage = React.lazy(() => import("./pages/CampaignsPage"));
const CampaignWorkspacePage = React.lazy(
  () => import("./pages/CampaignWorkspacePage"),
);
const VideoCallsPage = React.lazy(() => import("./pages/VideoCallsPage"));
const RubricBuilderPage = React.lazy(() => import("./pages/RubricBuilderPage"));
const GovernmentPositionsPage = React.lazy(
  () => import("./pages/GovernmentPositionsPage"),
);
const GovernmentPersonnelPage = React.lazy(
  () => import("./pages/GovernmentPersonnelPage"),
);
const AppointmentsRegistryPage = React.lazy(
  () => import("./pages/AppointmentsRegistryPage"),
);
const ErrorPage = React.lazy(() => import("./pages/ErrorPage"));
const NotFoundPage = React.lazy(() => import("./pages/NotFoundPage"));
const ApplicationsPage = React.lazy(() =>
  import("./pages/ApplicationsPage").then((module) => ({
    default: module.ApplicationsPage,
  })),
);
const RubricsPage = React.lazy(() =>
  import("./pages/RubricsPage").then((module) => ({
    default: module.RubricsPage,
  })),
);
const ApplicationDetailPage = React.lazy(() =>
  import("./pages/ApplicationDetailPage").then((module) => ({
    default: module.ApplicationDetailPage,
  })),
);
const NotificationsPage = React.lazy(() =>
  import("./pages/NotificationsPage").then((module) => ({
    default: module.NotificationsPage,
  })),
);
const NotificationDetailPage = React.lazy(() =>
  import("./pages/NotificationDetailPage").then((module) => ({
    default: module.NotificationDetailPage,
  })),
);
const InterviewSession = React.lazy(() =>
  import("./components/interview/InterviewSession").then((module) => ({
    default: module.InterviewSession,
  })),
);

const HIDE_NAVBAR_PREFIXES = [
  "/",
  "/gazette",
  "/transparency",
  "/subscribe",
  "/organization/get-started",
  "/login",
  "/register",
  "/candidate",
  "/invite",
  "/forgot-password",
  "/reset-password",
  "/billing",
  "/audit",
];

const ORG_WORKFLOW_DISALLOWED_USER_TYPES: Array<
  "applicant" | "internal" | "org_admin" | "platform_admin"
> = ["applicant", "platform_admin"];

const shouldHideNavbar = (pathname: string): boolean => {
  if (pathname === "/") return true;
  return HIDE_NAVBAR_PREFIXES.some(
    (prefix) => prefix !== "/" && pathname.startsWith(prefix),
  );
};

const RouteLoader: React.FC = () => (
  <div className="relative flex min-h-[40vh] items-center justify-center">
    <Loader className="h-8 w-8 animate-spin" />
  </div>
);

const LegacyPlatformRedirect: React.FC<{ segment: string }> = ({ segment }) => {
  const location = useLocation();
  return (
    <Navigate
      to={`${getPlatformAdminPath(segment)}${location.search || ""}`}
      replace
    />
  );
};

const LegacyWorkspaceRedirect: React.FC<{ segment?: string }> = ({
  segment = "home",
}) => {
  const location = useLocation();
  return (
    <Navigate
      to={`${getWorkspacePath(segment)}${location.search || ""}`}
      replace
    />
  );
};

const LegacyCandidateRedirect: React.FC<{ segment?: string }> = ({
  segment = "home",
}) => {
  const location = useLocation();
  return (
    <Navigate
      to={`${getCandidatePath(segment)}${location.search || ""}`}
      replace
    />
  );
};

// Redirects pure auditor users away from the general workspace to the dedicated audit portal.
const AuditorWorkspaceRedirect: React.FC<{ fallback: React.ReactNode }> = ({
  fallback,
}) => {
  const capabilities = useSelector(
    (state: RootState) => state.auth.capabilities,
  );
  if (isPureAuditorUser(capabilities as string[] | null | undefined)) {
    return <Navigate to="/audit/logs" replace />;
  }
  return <>{fallback}</>;
};

// Redirect a legacy flat path (e.g. /applications/:caseId) to the canonical
// /workspace/* equivalent while preserving the param and search string.
const LegacySegmentParamRedirect: React.FC<{
  segment: string;
  paramKey: string;
  suffix?: string;
}> = ({ segment, paramKey, suffix = "" }) => {
  const params = useParams<Record<string, string>>();
  const location = useLocation();
  const paramValue = encodeURIComponent(String(params[paramKey] || "").trim());
  return (
    <Navigate
      to={`${getWorkspacePath(segment)}/${paramValue}${suffix}${location.search || ""}`}
      replace
    />
  );
};

const LegacyOrganizationRedirect: React.FC<{ segment: string }> = ({
  segment,
}) => {
  const location = useLocation();
  const userType = useSelector((state: RootState) => state.auth.userType);
  const activeOrganizationId = useSelector((state: RootState) =>
    String(state.auth.activeOrganization?.id || "").trim(),
  );

  if (userType === "platform_admin" || userType === "admin") {
    return <Navigate to={getPlatformAdminPath("dashboard")} replace />;
  }

  if (!activeOrganizationId) {
    return <Navigate to={getOrganizationSetupPath("/dashboard")} replace />;
  }

  return (
    <Navigate
      to={`${getOrgAdminPath(activeOrganizationId, segment)}${location.search || ""}`}
      replace
    />
  );
};

const LegacyOrgCaseDetailRedirect: React.FC = () => {
  const { caseId } = useParams<{ caseId: string }>();
  return (
    <Navigate
      to={`${getWorkspacePath("applications")}/${encodeURIComponent(String(caseId || "").trim())}`}
      replace
    />
  );
};

const LegacyOrganizationCommitteeRedirect: React.FC = () => {
  const { committeeId } = useParams<{ committeeId: string }>();
  const userType = useSelector((state: RootState) => state.auth.userType);
  const activeOrganizationId = useSelector((state: RootState) =>
    String(state.auth.activeOrganization?.id || "").trim(),
  );

  if (userType === "platform_admin" || userType === "admin") {
    return <Navigate to={getPlatformAdminPath("dashboard")} replace />;
  }

  if (!activeOrganizationId) {
    return <Navigate to={getOrganizationSetupPath("/dashboard")} replace />;
  }

  return (
    <Navigate
      to={`${getOrgAdminPath(activeOrganizationId, "committees")}/${encodeURIComponent(String(committeeId || "").trim())}`}
      replace
    />
  );
};

const LegacyOrganizationCaseReviewRedirect: React.FC = () => {
  const { caseId } = useParams<{ caseId: string }>();
  const userType = useSelector((state: RootState) => state.auth.userType);

  if (userType === "platform_admin" || userType === "admin") {
    return <Navigate to={getPlatformAdminPath("dashboard")} replace />;
  }

  return (
    <Navigate
      to={`${getWorkspacePath("applications")}/${encodeURIComponent(String(caseId || "").trim())}`}
      replace
    />
  );
};

const OrganizationScopedRoute: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  const dispatch = useDispatch<AppDispatch>();
  const location = useLocation();
  const { orgId } = useParams<{ orgId: string }>();
  const userType = useSelector((state: RootState) => state.auth.userType);
  const isAuthenticated = useSelector(
    (state: RootState) => state.auth.isAuthenticated,
  );
  const silentRefreshPending = useSelector(
    (state: RootState) => state.auth.silentRefreshPending,
  );
  const hasAccessToken = useSelector((state: RootState) =>
    Boolean(state.auth.tokens?.access),
  );
  const activeOrganizationId = useSelector((state: RootState) =>
    String(state.auth.activeOrganization?.id || "").trim(),
  );
  const switchingActiveOrganization = useSelector(
    (state: RootState) => state.auth.switchingActiveOrganization,
  );
  const loading = useSelector((state: RootState) => state.auth.loading);
  const attemptedOrganizationIdRef = useRef<string | null>(null);
  const [attemptedOrganizationId, setAttemptedOrganizationId] = useState<
    string | null
  >(null);
  const normalizedOrganizationId = String(orgId || "").trim();

  useEffect(() => {
    if (
      !normalizedOrganizationId ||
      normalizedOrganizationId === activeOrganizationId ||
      switchingActiveOrganization ||
      attemptedOrganizationIdRef.current === normalizedOrganizationId ||
      !isAuthenticated ||
      silentRefreshPending ||
      !hasAccessToken
    ) {
      return;
    }

    attemptedOrganizationIdRef.current = normalizedOrganizationId;
    queueMicrotask(() => {
      setAttemptedOrganizationId(normalizedOrganizationId);
    });
    void dispatch(switchActiveOrganization(normalizedOrganizationId));
  }, [
    activeOrganizationId,
    dispatch,
    hasAccessToken,
    isAuthenticated,
    normalizedOrganizationId,
    silentRefreshPending,
    switchingActiveOrganization,
  ]);

  const routePath = `${location.pathname}${location.search || ""}`;
  const setupRedirectPath = getOrganizationSetupPath(routePath);
  const syncAttempted = attemptedOrganizationId === normalizedOrganizationId;
  const isOrganizationSynced =
    normalizedOrganizationId.length > 0 &&
    activeOrganizationId === normalizedOrganizationId;

  if (userType === "platform_admin" || userType === "admin") {
    return <Navigate to={getPlatformAdminPath("dashboard")} replace />;
  }

  return (
    <ProtectedRoute
      disallowUserTypes={["applicant", "platform_admin"]}
      requireOrganizationGovernance
      activeOrganizationRedirectPath={setupRedirectPath}
    >
      {!normalizedOrganizationId ? (
        <Navigate to="/dashboard" replace />
      ) : loading || switchingActiveOrganization ? (
        <RouteLoader />
      ) : isOrganizationSynced ? (
        <>{children}</>
      ) : syncAttempted ? (
        <Navigate to={setupRedirectPath} replace />
      ) : (
        <RouteLoader />
      )}
    </ProtectedRoute>
  );
};

const InterviewSessionPage: React.FC = () => {
  const { applicationId } = useParams<{ applicationId: string }>();

  if (!applicationId) {
    return <Navigate to={getWorkspacePath("home")} />;
  }

  return <InterviewSession applicationId={applicationId} />;
};

const CandidateInterrogationPage: React.FC = () => {
  const { applicationId } = useParams<{ applicationId: string }>();

  if (!applicationId) {
    return <Navigate to={getCandidatePath("home")} />;
  }

  return (
    <InterviewSession
      applicationId={applicationId}
      completionRedirectPath={getCandidatePath("home")}
    />
  );
};

const AppRoutes: React.FC = () => (
  <Routes>
    <Route path="/" element={<HomePage />} />
    <Route path="/gazette" element={<PublicGazettePage />} />
    <Route path="/transparency" element={<PublicTransparencyPage />} />
    <Route
      path="/transparency/appointments/:appointmentId"
      element={<PublicAppointmentDetailPage />}
    />
    <Route path="/subscribe" element={<SubscriptionPlansPage />} />
    <Route
      path="/organization/get-started"
      element={
        <UnauthenticatedRoute>
          <OrganizationAdminSignupPage />
        </UnauthenticatedRoute>
      }
    />
    <Route
      path="/admin/org/:orgId/dashboard"
      element={
        <OrganizationScopedRoute>
          <OrgDashboardPage />
        </OrganizationScopedRoute>
      }
    />
    <Route
      path="/admin/org/:orgId/users"
      element={
        <ProtectedRoute platformAdminOnly>
          <OrgUsersPage />
        </ProtectedRoute>
      }
    />
    <Route
      path="/admin/org/:orgId/cases"
      element={<LegacyWorkspaceRedirect segment="applications" />}
    />
    <Route
      path="/admin/org/:orgId/members"
      element={
        <OrganizationScopedRoute>
          <OrganizationMembersPage />
        </OrganizationScopedRoute>
      }
    />
    <Route
      path="/admin/org/:orgId/committees"
      element={
        <OrganizationScopedRoute>
          <OrganizationCommitteesPage />
        </OrganizationScopedRoute>
      }
    />
    <Route
      path="/admin/org/:orgId/committees/:committeeId"
      element={
        <OrganizationScopedRoute>
          <CommitteeDetailPage />
        </OrganizationScopedRoute>
      }
    />
    <Route
      path="/admin/org/:orgId/onboarding"
      element={
        <OrganizationScopedRoute>
          <OrganizationOnboardingPage />
        </OrganizationScopedRoute>
      }
    />
    <Route
      path="/organization/dashboard"
      element={<LegacyOrganizationRedirect segment="dashboard" />}
    />
    <Route
      path="/organization/committee-dashboard"
      element={
        <ProtectedRoute
          disallowUserTypes={ORG_WORKFLOW_DISALLOWED_USER_TYPES}
          requiredRoles={["committee_member", "committee_chair"]}
          requireActiveOrganization
        >
          <Navigate to={`${getWorkspacePath("home")}?view=committee`} replace />
        </ProtectedRoute>
      }
    />
    <Route
      path="/organization/members"
      element={<LegacyOrganizationRedirect segment="members" />}
    />
    <Route
      path="/organization/committees"
      element={<LegacyOrganizationRedirect segment="committees" />}
    />
    <Route
      path="/organization/committees/:committeeId"
      element={<LegacyOrganizationCommitteeRedirect />}
    />
    <Route
      path="/organization/setup"
      element={
        <ProtectedRoute disallowUserTypes={ORG_WORKFLOW_DISALLOWED_USER_TYPES}>
          <OrganizationSetupPage />
        </ProtectedRoute>
      }
    />
    <Route
      path="/organization/onboarding"
      element={<LegacyOrganizationRedirect segment="onboarding" />}
    />
    <Route
      path="/login"
      element={
        <UnauthenticatedRoute>
          <LoginPage />
        </UnauthenticatedRoute>
      }
    />
    <Route
      path="/login/2fa"
      element={
        <UnauthenticatedRoute allowTwoFactorChallenge>
          <TwoFactorPage />
        </UnauthenticatedRoute>
      }
    />
    <Route
      path="/register"
      element={
        <UnauthenticatedRoute>
          <RegisterPage />
        </UnauthenticatedRoute>
      }
    />

    <Route
      path="/forgot-password"
      element={
        <UnauthenticatedRoute>
          <ForgotPasswordPage />
        </UnauthenticatedRoute>
      }
    />
    <Route
      path="/forgot-password/email-sent"
      element={
        <UnauthenticatedRoute>
          <EmailSentPage />
        </UnauthenticatedRoute>
      }
    />
    <Route
      path="/reset-password/:token"
      element={
        <UnauthenticatedRoute>
          <ResetPasswordPage />
        </UnauthenticatedRoute>
      }
    />

    <Route path="/billing/success" element={<BillingCheckoutResultPage />} />
    <Route path="/billing/cancel" element={<BillingCheckoutResultPage />} />

    <Route path={getCandidatePath("home")} element={<CandidateHomePage />} />
    <Route
      path="/candidate/access"
      element={<LegacyCandidateRedirect segment="home" />}
    />
    <Route
      path="/candidate/interview/:applicationId"
      element={<CandidateInterrogationPage />}
    />
    <Route path="/invite/:token" element={<InvitationAcceptPage />} />

    <Route
      path="/interview/interrogation/:applicationId"
      element={
        <ProtectedRoute disallowUserTypes={ORG_WORKFLOW_DISALLOWED_USER_TYPES}>
          <InterviewSessionPage />
        </ProtectedRoute>
      }
    />
    <Route
      path={getWorkspacePath("home")}
      element={
        <ProtectedRoute disallowUserTypes={ORG_WORKFLOW_DISALLOWED_USER_TYPES}>
          <AuditorWorkspaceRedirect fallback={<WorkspaceHomePage />} />
        </ProtectedRoute>
      }
    />
    <Route
      path="/workspace"
      element={<LegacyWorkspaceRedirect segment="home" />}
    />
    <Route
      path={getWorkspacePath("applications")}
      element={
        <ProtectedRoute
          disallowUserTypes={ORG_WORKFLOW_DISALLOWED_USER_TYPES}
          requiredCapabilities={[...INTERNAL_WORKFLOW_ROUTE_CAPABILITIES]}
          legacyUserTypeFallback={["org_admin"]}
        >
          <ApplicationsPage />
        </ProtectedRoute>
      }
    />
    <Route
      path={`${getWorkspacePath("applications")}/:caseId`}
      element={
        <ProtectedRoute
          disallowUserTypes={ORG_WORKFLOW_DISALLOWED_USER_TYPES}
          requiredCapabilities={[...INTERNAL_WORKFLOW_ROUTE_CAPABILITIES]}
          legacyUserTypeFallback={["org_admin"]}
        >
          <ApplicationDetailPage />
        </ProtectedRoute>
      }
    />
    <Route
      path={getWorkspacePath("notifications")}
      element={
        <ProtectedRoute
          disallowUserTypes={["applicant", "platform_admin"]}
          requiredCapabilities={[...INTERNAL_WORKFLOW_ROUTE_CAPABILITIES]}
        >
          <NotificationsPage />
        </ProtectedRoute>
      }
    />
    <Route
      path={`${getWorkspacePath("notifications")}/:notificationId`}
      element={
        <ProtectedRoute
          disallowUserTypes={["applicant", "platform_admin"]}
          requiredCapabilities={[...INTERNAL_WORKFLOW_ROUTE_CAPABILITIES]}
        >
          <NotificationDetailPage />
        </ProtectedRoute>
      }
    />
    <Route
      path={getWorkspacePath("campaigns")}
      element={
        <ProtectedRoute
          disallowUserTypes={ORG_WORKFLOW_DISALLOWED_USER_TYPES}
          requiredCapabilities={[...CAMPAIGN_MANAGE_CAPABILITIES]}
        >
          <CampaignsPage />
        </ProtectedRoute>
      }
    />
    <Route
      path={`${getWorkspacePath("campaigns")}/:campaignId`}
      element={
        <ProtectedRoute
          disallowUserTypes={ORG_WORKFLOW_DISALLOWED_USER_TYPES}
          requiredCapabilities={[...CAMPAIGN_MANAGE_CAPABILITIES]}
        >
          <CampaignWorkspacePage />
        </ProtectedRoute>
      }
    />
    <Route
      path={getWorkspacePath("video-calls")}
      element={
        <ProtectedRoute
          disallowUserTypes={ORG_WORKFLOW_DISALLOWED_USER_TYPES}
          requiredCapabilities={[...INTERNAL_WORKFLOW_ROUTE_CAPABILITIES]}
        >
          <VideoCallsPage />
        </ProtectedRoute>
      }
    />
    <Route
      path={getWorkspacePath("audit-logs")}
      element={
        <ProtectedRoute
          requiredCapabilities={["gams.audit.view"]}
          legacyUserTypeFallback={["org_admin", "platform_admin"]}
        >
          <AuditorWorkspaceRedirect fallback={<AuditLogsPage />} />
        </ProtectedRoute>
      }
    />
    <Route
      path={getWorkspacePath("fraud-insights")}
      element={
        <ProtectedRoute
          disallowUserTypes={ORG_WORKFLOW_DISALLOWED_USER_TYPES}
          requiredCapabilities={[...INTERNAL_WORKFLOW_ROUTE_CAPABILITIES]}
        >
          <FraudInsightsPage />
        </ProtectedRoute>
      }
    />
    <Route
      path={getWorkspacePath("background-checks")}
      element={
        <ProtectedRoute
          disallowUserTypes={ORG_WORKFLOW_DISALLOWED_USER_TYPES}
          requiredCapabilities={[...INTERNAL_WORKFLOW_ROUTE_CAPABILITIES]}
        >
          <BackgroundChecksPage />
        </ProtectedRoute>
      }
    />
    <Route
      path={getWorkspacePath("rubrics")}
      element={
        <ProtectedRoute
          disallowUserTypes={ORG_WORKFLOW_DISALLOWED_USER_TYPES}
          requiredCapabilities={[...RUBRIC_MANAGE_CAPABILITIES]}
        >
          <RubricsPage />
        </ProtectedRoute>
      }
    />
    <Route
      path={getWorkspacePath("rubrics/new")}
      element={
        <ProtectedRoute
          disallowUserTypes={ORG_WORKFLOW_DISALLOWED_USER_TYPES}
          requiredCapabilities={[...RUBRIC_MANAGE_CAPABILITIES]}
        >
          <RubricBuilderPage />
        </ProtectedRoute>
      }
    />
    <Route
      path={`${getWorkspacePath("rubrics")}/:rubricId/edit`}
      element={
        <ProtectedRoute
          disallowUserTypes={ORG_WORKFLOW_DISALLOWED_USER_TYPES}
          requiredCapabilities={[...RUBRIC_MANAGE_CAPABILITIES]}
        >
          <RubricBuilderPage />
        </ProtectedRoute>
      }
    />
    <Route
      path={getWorkspacePath("government/positions")}
      element={
        <ProtectedRoute
          disallowUserTypes={ORG_WORKFLOW_DISALLOWED_USER_TYPES}
          requiredCapabilities={[...REGISTRY_ROUTE_CAPABILITIES]}
        >
          <GovernmentPositionsPage />
        </ProtectedRoute>
      }
    />
    <Route
      path={getWorkspacePath("government/personnel")}
      element={
        <ProtectedRoute
          disallowUserTypes={ORG_WORKFLOW_DISALLOWED_USER_TYPES}
          requiredCapabilities={[...REGISTRY_ROUTE_CAPABILITIES]}
        >
          <GovernmentPersonnelPage />
        </ProtectedRoute>
      }
    />
    <Route
      path={getWorkspacePath("government/appointments")}
      element={
        <ProtectedRoute
          disallowUserTypes={ORG_WORKFLOW_DISALLOWED_USER_TYPES}
          requiredCapabilities={[...APPOINTMENT_ROUTE_CAPABILITIES]}
        >
          <AppointmentsRegistryPage />
        </ProtectedRoute>
      }
    />
    <Route
      path="/dashboard"
      element={
        <ProtectedRoute>
          <DashboardPage />
        </ProtectedRoute>
      }
    />
    <Route
      path="/change-password"
      element={
        <ProtectedRoute>
          <ChangePasswordPage />
        </ProtectedRoute>
      }
    />
    <Route
      path="/settings"
      element={
        <ProtectedRoute>
          <UserSettingsPage />
        </ProtectedRoute>
      }
    />
    <Route
      path="/security"
      element={
        <ProtectedRoute disallowUserTypes={["applicant"]}>
          <SecurityPage />
        </ProtectedRoute>
      }
    />
    {/* Platform-admin routes */}
    <Route
      path={getPlatformAdminPath("ml-monitoring")}
      element={<Navigate to={getPlatformAdminPath("dashboard")} replace />}
    />
    <Route
      path={getPlatformAdminPath("ai-monitor")}
      element={<Navigate to={getPlatformAdminPath("dashboard")} replace />}
    />
    <Route
      path={getPlatformAdminPath("analytics")}
      element={<Navigate to={getPlatformAdminPath("dashboard")} replace />}
    />
    <Route
      path={getPlatformAdminPath("register")}
      element={<Navigate to={getPlatformAdminPath("dashboard")} replace />}
    />
    <Route
      path={getPlatformAdminPath("control-center")}
      element={<Navigate to={getPlatformAdminPath("dashboard")} replace />}
    />
    <Route
      path="/admin/platform/ai-engine"
      element={
        <ProtectedRoute platformAdminOnly>
          <AiInfrastructurePage />
        </ProtectedRoute>
      }
    />
    <Route
      path="/admin/platform/logs"
      element={
        <ProtectedRoute platformAdminOnly>
          <PlatformAuditLogsPage />
        </ProtectedRoute>
      }
    />
    <Route
      path="/admin/platform/registry"
      element={
        <ProtectedRoute platformAdminOnly>
          <OrganizationRegistryPage />
        </ProtectedRoute>
      }
    />
    <Route
      path="/admin/platform/billing"
      element={
        <ProtectedRoute platformAdminOnly>
          <BillingManagementPage />
        </ProtectedRoute>
      }
    />
    <Route
      path="/admin/platform/health"
      element={
        <ProtectedRoute platformAdminOnly>
          <SystemHealthPage />
        </ProtectedRoute>
      }
    />
    <Route
      path={getPlatformAdminPath("dashboard")}
      element={
        <ProtectedRoute platformAdminOnly>
          <PlatformDashboardPage />
        </ProtectedRoute>
      }
    />

    {/* Auditor portal routes */}
    <Route
      path="/audit/logs"
      element={
        <ProtectedRoute requiredCapabilities={["gams.audit.view"]}>
          <AuditLogsPage />
        </ProtectedRoute>
      }
    />
    <Route path="/audit" element={<Navigate to="/audit/logs" replace />} />

    {/* Legacy flat-path redirects — forward to canonical /workspace/* paths */}
    <Route
      path="/fraud-insights"
      element={<Navigate to={getWorkspacePath("fraud-insights")} replace />}
    />
    <Route
      path="/background-checks"
      element={<Navigate to={getWorkspacePath("background-checks")} replace />}
    />
    <Route
      path="/audit-logs"
      element={
        <AuditorWorkspaceRedirect
          fallback={<Navigate to={getWorkspacePath("audit-logs")} replace />}
        />
      }
    />
    <Route
      path="/applications"
      element={<Navigate to={getWorkspacePath("applications")} replace />}
    />
    <Route
      path="/applications/:caseId"
      element={
        <LegacySegmentParamRedirect segment="applications" paramKey="caseId" />
      }
    />
    <Route
      path="/notifications"
      element={<Navigate to={getWorkspacePath("notifications")} replace />}
    />
    <Route
      path="/notifications/:notificationId"
      element={
        <LegacySegmentParamRedirect
          segment="notifications"
          paramKey="notificationId"
        />
      }
    />
    <Route
      path="/campaigns"
      element={<Navigate to={getWorkspacePath("campaigns")} replace />}
    />
    <Route
      path="/campaigns/:campaignId"
      element={
        <LegacySegmentParamRedirect segment="campaigns" paramKey="campaignId" />
      }
    />
    <Route
      path="/video-calls"
      element={<Navigate to={getWorkspacePath("video-calls")} replace />}
    />
    <Route
      path="/government/positions"
      element={
        <Navigate to={getWorkspacePath("government/positions")} replace />
      }
    />
    <Route
      path="/government/personnel"
      element={
        <Navigate to={getWorkspacePath("government/personnel")} replace />
      }
    />
    <Route
      path="/government/appointments"
      element={
        <Navigate to={getWorkspacePath("government/appointments")} replace />
      }
    />
    <Route
      path="/rubrics"
      element={<Navigate to={getWorkspacePath("rubrics")} replace />}
    />
    <Route
      path="/rubrics/new"
      element={<Navigate to={getWorkspacePath("rubrics/new")} replace />}
    />
    <Route
      path="/rubrics/:rubricId/edit"
      element={
        <LegacySegmentParamRedirect
          segment="rubrics"
          paramKey="rubricId"
          suffix="/edit"
        />
      }
    />

    {/* Legacy /ml-monitoring and /ai-monitor flat paths */}
    <Route
      path="/ml-monitoring"
      element={<LegacyPlatformRedirect segment="ml-monitoring" />}
    />
    <Route
      path="/ai-monitor"
      element={<LegacyPlatformRedirect segment="ai-monitor" />}
    />

    {/* Legacy /admin/* paths */}
    <Route
      path="/admin/dashboard"
      element={<LegacyPlatformRedirect segment="dashboard" />}
    />
    <Route
      path="/admin/analytics"
      element={<LegacyPlatformRedirect segment="analytics" />}
    />
    <Route
      path="/admin/register"
      element={<LegacyPlatformRedirect segment="register" />}
    />
    <Route
      path="/admin/control-center"
      element={<LegacyPlatformRedirect segment="control-center" />}
    />
    <Route
      path="/admin/users"
      element={<LegacyOrganizationRedirect segment="users" />}
    />
    <Route
      path="/admin/rubrics"
      element={<Navigate to={getWorkspacePath("rubrics")} replace />}
    />
    <Route
      path="/admin/applications"
      element={<LegacyOrganizationRedirect segment="cases" />}
    />
    <Route
      path="/admin/cases"
      element={<LegacyOrganizationRedirect segment="cases" />}
    />
    <Route
      path="/admin/org/:orgId/cases/:caseId"
      element={<LegacyOrgCaseDetailRedirect />}
    />
    <Route
      path="/admin/org/:orgId/cases"
      element={<LegacyWorkspaceRedirect segment="applications" />}
    />
    <Route
      path="/admin/cases/:caseId"
      element={<LegacyOrganizationCaseReviewRedirect />}
    />

    <Route path="/error" element={<ErrorPage />} />
    <Route path="*" element={<NotFoundPage />} />
  </Routes>
);

const GOVERNANCE_CAPABILITIES = new Set([
  "gams.registry.manage",
  "gams.appointment.stage",
  "gams.appointment.decide",
  "gams.appointment.publish",
  "gams.appointment.view_internal",
]);

const isPureAuditorUser = (
  capabilities: readonly string[] | null | undefined,
): boolean => {
  if (!Array.isArray(capabilities) || capabilities.length === 0) return false;
  const hasAuditView = capabilities.includes("gams.audit.view");
  const hasAnyGovernanceCap = capabilities.some((c) =>
    GOVERNANCE_CAPABILITIES.has(c),
  );
  return hasAuditView && !hasAnyGovernanceCap;
};

const AppShell: React.FC = () => {
  const isAuthenticated = useSelector(
    (state: RootState) => state.auth.isAuthenticated,
  );
  const userType = useSelector((state: RootState) => state.auth.userType);
  const capabilities = useSelector(
    (state: RootState) => state.auth.capabilities,
  );
  const location = useLocation();
  const hideNavbar = shouldHideNavbar(location.pathname);

  const showTopNavbar =
    isAuthenticated &&
    (userType === "applicant" || userType === "internal") &&
    !hideNavbar;
  const isPlatformAdmin =
    isAuthenticated && (userType === "platform_admin" || userType === "admin");
  const isOrgAdmin = isAuthenticated && userType === "org_admin";
  // Pure auditors: internal members whose only capability is gams.audit.view —
  // they get a dedicated read-only portal instead of the full workspace navbar.
  const isAuditor =
    isAuthenticated &&
    userType === "internal" &&
    isPureAuditorUser(capabilities as string[] | null | undefined);

  if (isPlatformAdmin) {
    return (
      <SystemAdminLayout>
        <Suspense fallback={<RouteLoader />}>
          <AppRoutes />
        </Suspense>
      </SystemAdminLayout>
    );
  }

  if (isOrgAdmin) {
    return (
      <OrgAdminLayout>
        <Suspense fallback={<RouteLoader />}>
          <AppRoutes />
        </Suspense>
      </OrgAdminLayout>
    );
  }

  if (isAuditor) {
    return (
      <AuditorLayout>
        <Suspense fallback={<RouteLoader />}>
          <AppRoutes />
        </Suspense>
      </AuditorLayout>
    );
  }

  return (
    <div className="min-h-screen bg-background text-foreground">
      {showTopNavbar ? (
        <Suspense
          fallback={
            <div className="h-16 border-b border-slate-200 bg-slate-50" />
          }
        >
          <Navbar />
        </Suspense>
      ) : null}

      <main className={showTopNavbar ? "relative lg:pl-64 xl:pl-72" : ""}>
        <Suspense fallback={<RouteLoader />}>
          <AppRoutes />
        </Suspense>
      </main>
    </div>
  );
};

const App: React.FC = () => {
  const dispatch = useDispatch<AppDispatch>();
  const isRehydrated = useSelector((state: RootState) =>
    state._persist ? state._persist.rehydrated : true,
  );
  const isAuthenticated = useSelector(
    (state: RootState) => state.auth.isAuthenticated,
  );
  const accessToken = useSelector(
    (state: RootState) => state.auth.tokens?.access,
  );

  // After redux-persist rehydrates, tokens are always cleared (by design, to
  // avoid storing JWTs in localStorage). If a refresh token was saved to
  // sessionStorage at login time, use it to silently restore the session so a
  // page refresh doesn't log the user out.
  useEffect(() => {
    if (!isRehydrated || isAuthenticated) return;
    const storedRefresh = sessionStorage.getItem(REFRESH_TOKEN_SESSION_KEY);
    if (storedRefresh) {
      void dispatch(silentRefresh());
    }
  }, [dispatch, isRehydrated, isAuthenticated]);

  useEffect(() => {
    if (!isRehydrated || !isAuthenticated || !accessToken) {
      return;
    }

    void dispatch(fetchProfile());
  }, [dispatch, isRehydrated, isAuthenticated, accessToken]);

  if (!isRehydrated) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Loader className="h-8 w-8 animate-spin" />
      </div>
    );
  }

  return (
    <ErrorBoundary>
      <Router>
        <AppShell />
      </Router>
    </ErrorBoundary>
  );
};

export default App;
