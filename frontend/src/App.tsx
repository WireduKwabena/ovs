import React, { Suspense, useEffect } from "react";
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
import { fetchProfile } from "./store/authSlice";
import { type AppDispatch, type RootState } from "./app/store";
import {
  APPOINTMENT_ROUTE_CAPABILITIES,
  INTERNAL_WORKFLOW_ROUTE_CAPABILITIES,
  LEGACY_CAPABILITY_STALE_FALLBACK_USER_TYPES,
  REGISTRY_ROUTE_CAPABILITIES,
  RUBRIC_MANAGE_CAPABILITIES,
} from "./utils/frontendAuthz";

const Navbar = React.lazy(() =>
  import("./components/common/Navbar").then((module) => ({ default: module.Navbar })),
);
const HomePage = React.lazy(() => import("./pages/HomePage"));
const PublicGazettePage = React.lazy(() => import("./pages/PublicGazettePage"));
const SubscriptionPlansPage = React.lazy(() => import("./pages/SubscriptionPlansPage"));
const OrganizationSetupPage = React.lazy(() => import("./pages/OrganizationSetupPage"));
const OrganizationDashboardPage = React.lazy(() => import("./pages/OrganizationDashboardPage"));
const OrganizationMembersPage = React.lazy(() => import("./pages/OrganizationMembersPage"));
const OrganizationCommitteesPage = React.lazy(() => import("./pages/OrganizationCommitteesPage"));
const CommitteeDetailPage = React.lazy(() => import("./pages/CommitteeDetailPage"));
const OrganizationOnboardingPage = React.lazy(() => import("./pages/OrganizationOnboardingPage"));
const LoginPage = React.lazy(() => import("./pages/LoginPage"));
const TwoFactorPage = React.lazy(() => import("./pages/TwoFactorPage"));
const RegisterPage = React.lazy(() => import("./pages/RegisterPage"));
const ForgotPasswordPage = React.lazy(() => import("./pages/ForgotPasswordPage"));
const EmailSentPage = React.lazy(() => import("./pages/EmailSentPage"));
const ResetPasswordPage = React.lazy(() => import("./pages/ResetPasswordPage"));
const BillingCheckoutResultPage = React.lazy(() => import("./pages/BillingCheckoutResultPage"));
const CandidateAccessPage = React.lazy(() => import("./pages/CandidateAccessPage"));
const InvitationAcceptPage = React.lazy(() => import("./pages/InvitationAcceptPage"));
const DashboardPage = React.lazy(() => import("./pages/DashboardPage"));
const ChangePasswordPage = React.lazy(() => import("./pages/ChangePasswordPage"));
const UserSettingsPage = React.lazy(() => import("./pages/UserSettingsPage"));
const SecurityPage = React.lazy(() => import("./pages/SecurityPage"));
const FraudInsightsPage = React.lazy(() => import("./pages/FraudInsightsPage"));
const BackgroundChecksPage = React.lazy(() => import("./pages/BackgroundChecksPage"));
const AuditLogsPage = React.lazy(() => import("./pages/AuditLogsPage"));
const MlMonitoringPage = React.lazy(() => import("./pages/MlMonitoringPage"));
const AiMonitorPage = React.lazy(() => import("./pages/AiMonitorPage"));
const CampaignsPage = React.lazy(() => import("./pages/CampaignsPage"));
const CampaignWorkspacePage = React.lazy(() => import("./pages/CampaignWorkspacePage"));
const VideoCallsPage = React.lazy(() => import("./pages/VideoCallsPage"));
const RubricBuilderPage = React.lazy(() => import("./pages/RubricBuilderPage"));
const GovernmentPositionsPage = React.lazy(() => import("./pages/GovernmentPositionsPage"));
const GovernmentPersonnelPage = React.lazy(() => import("./pages/GovernmentPersonnelPage"));
const AppointmentsRegistryPage = React.lazy(() => import("./pages/AppointmentsRegistryPage"));
const ErrorPage = React.lazy(() => import("./pages/ErrorPage"));
const NotFoundPage = React.lazy(() => import("./pages/NotFoundPage"));
const AdminDashboardPage = React.lazy(() => import("./pages/admin/AdminDashboardPage"));
const AdminAnalyticsPage = React.lazy(() => import("./pages/admin/AdminAnalyticsPage"));
const AdminRegisterPage = React.lazy(() => import("./pages/admin/AdminRegisterPage"));
const AdminCasesPage = React.lazy(() => import("./pages/admin/AdminCasesPage"));
const AdminControlCenterPage = React.lazy(() => import("./pages/admin/AdminControlCenterPage"));
const AdminUsersPage = React.lazy(() => import("./pages/admin/AdminUsersPage"));
const AdminCaseReview = React.lazy(() =>
  import("./components/admin/CaseReview").then((module) => ({ default: module.CaseReview })),
);
const ApplicationsPage = React.lazy(() =>
  import("./pages/ApplicationsPage").then((module) => ({ default: module.ApplicationsPage })),
);
const RubricsPage = React.lazy(() =>
  import("./pages/RubricsPage").then((module) => ({ default: module.RubricsPage })),
);
const ApplicationDetailPage = React.lazy(() =>
  import("./pages/ApplicationDetailPage").then((module) => ({ default: module.ApplicationDetailPage })),
);
const NotificationsPage = React.lazy(() =>
  import("./pages/NotificationsPage").then((module) => ({ default: module.NotificationsPage })),
);
const NotificationDetailPage = React.lazy(() =>
  import("./pages/NotificationDetailPage").then((module) => ({
    default: module.NotificationDetailPage,
  })),
);
const HeyGenInterrogation = React.lazy(() =>
  import("./components/interview/HeyGenInterrogation").then((module) => ({
    default: module.HeyGenInterrogation,
  })),
);

const HIDE_NAVBAR_PREFIXES = [
  "/",
  "/gazette",
  "/subscribe",
  "/login",
  "/register",
  "/candidate",
  "/invite",
  "/forgot-password",
  "/reset-password",
  "/billing",
];

const LEGACY_INTERNAL_FALLBACK: Array<"hr_manager" | "admin"> = [...LEGACY_CAPABILITY_STALE_FALLBACK_USER_TYPES];

const shouldHideNavbar = (pathname: string): boolean => {
  if (pathname === "/") return true;
  return HIDE_NAVBAR_PREFIXES.some((prefix) => prefix !== "/" && pathname.startsWith(prefix));
};

const HeyGenInterrogationPage: React.FC = () => {
  const { applicationId } = useParams<{ applicationId: string }>();

  if (!applicationId) {
    return <Navigate to="/dashboard" />;
  }

  return <HeyGenInterrogation applicationId={applicationId} />;
};

const CandidateInterrogationPage: React.FC = () => {
  const { applicationId } = useParams<{ applicationId: string }>();

  if (!applicationId) {
    return <Navigate to="/candidate/access" />;
  }

  return <HeyGenInterrogation applicationId={applicationId} completionRedirectPath="/candidate/access" />;
};

const AppShell: React.FC = () => {
  const isAuthenticated = useSelector((state: RootState) => state.auth.isAuthenticated);
  const userType = useSelector((state: RootState) => state.auth.userType);
  const location = useLocation();
  const hideNavbar = shouldHideNavbar(location.pathname);

  return (
    <div className="min-h-screen bg-background text-foreground">
      {isAuthenticated && userType !== "applicant" && !hideNavbar ? (
        <Suspense fallback={<div className="h-16 border-b border-slate-200 bg-slate-50" />}>
          <Navbar />
        </Suspense>
      ) : null}

      <Suspense
        fallback={
          <div className="flex min-h-[40vh] items-center justify-center">
            <Loader size="lg" className="animate-spin" />
          </div>
        }
      >
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/gazette" element={<PublicGazettePage />} />
          <Route path="/subscribe" element={<SubscriptionPlansPage />} />
          <Route
            path="/organization/dashboard"
            element={
              <ProtectedRoute
                disallowUserTypes={["applicant"]}
                requireOrganizationGovernance
                requireActiveOrganization
              >
                <OrganizationDashboardPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/organization/members"
            element={
              <ProtectedRoute
                disallowUserTypes={["applicant"]}
                requireOrganizationGovernance
                requireActiveOrganization
              >
                <OrganizationMembersPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/organization/committees"
            element={
              <ProtectedRoute
                disallowUserTypes={["applicant"]}
                requireOrganizationGovernance
                requireActiveOrganization
              >
                <OrganizationCommitteesPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/organization/committees/:committeeId"
            element={
              <ProtectedRoute
                disallowUserTypes={["applicant"]}
                requireOrganizationGovernance
                requireActiveOrganization
              >
                <CommitteeDetailPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/organization/setup"
            element={
              <ProtectedRoute disallowUserTypes={["applicant"]}>
                <OrganizationSetupPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/organization/onboarding"
            element={
              <ProtectedRoute
                disallowUserTypes={["applicant"]}
                requireOrganizationGovernance
                requireActiveOrganization
              >
                <OrganizationOnboardingPage />
              </ProtectedRoute>
            }
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

          <Route path="/candidate/access" element={<CandidateAccessPage />} />
          <Route path="/candidate/interview/:applicationId" element={<CandidateInterrogationPage />} />
          <Route path="/invite/:token" element={<InvitationAcceptPage />} />

          <Route
            path="/interview/interrogation/:applicationId"
            element={
              <ProtectedRoute disallowUserTypes={["applicant"]}>
                <HeyGenInterrogationPage />
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
          <Route
            path="/fraud-insights"
            element={
              <ProtectedRoute
                disallowUserTypes={["applicant"]}
                requiredCapabilities={[...INTERNAL_WORKFLOW_ROUTE_CAPABILITIES]}
                legacyUserTypeFallback={LEGACY_INTERNAL_FALLBACK}
              >
                <FraudInsightsPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/background-checks"
            element={
              <ProtectedRoute
                disallowUserTypes={["applicant"]}
                requiredCapabilities={[...INTERNAL_WORKFLOW_ROUTE_CAPABILITIES]}
                legacyUserTypeFallback={LEGACY_INTERNAL_FALLBACK}
              >
                <BackgroundChecksPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/audit-logs"
            element={
              <ProtectedRoute
                requiredCapabilities={["gams.audit.view"]}
                legacyUserTypeFallback={["admin"]}
              >
                <AuditLogsPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/ml-monitoring"
            element={
              <ProtectedRoute adminOnly>
                <MlMonitoringPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/ai-monitor"
            element={
              <ProtectedRoute adminOnly>
                <AiMonitorPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/applications"
            element={
              <ProtectedRoute
                disallowUserTypes={["applicant"]}
                requiredCapabilities={[...INTERNAL_WORKFLOW_ROUTE_CAPABILITIES]}
                legacyUserTypeFallback={LEGACY_INTERNAL_FALLBACK}
              >
                <ApplicationsPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/applications/:caseId"
            element={
              <ProtectedRoute
                disallowUserTypes={["applicant"]}
                requiredCapabilities={[...INTERNAL_WORKFLOW_ROUTE_CAPABILITIES]}
                legacyUserTypeFallback={LEGACY_INTERNAL_FALLBACK}
              >
                <ApplicationDetailPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/notifications"
            element={
              <ProtectedRoute disallowUserTypes={["applicant"]}>
                <NotificationsPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/notifications/:notificationId"
            element={
              <ProtectedRoute disallowUserTypes={["applicant"]}>
                <NotificationDetailPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/campaigns"
            element={
              <ProtectedRoute
                disallowUserTypes={["applicant"]}
                requiredCapabilities={[...INTERNAL_WORKFLOW_ROUTE_CAPABILITIES]}
                legacyUserTypeFallback={LEGACY_INTERNAL_FALLBACK}
              >
                <CampaignsPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/campaigns/:campaignId"
            element={
              <ProtectedRoute
                disallowUserTypes={["applicant"]}
                requiredCapabilities={[...INTERNAL_WORKFLOW_ROUTE_CAPABILITIES]}
                legacyUserTypeFallback={LEGACY_INTERNAL_FALLBACK}
              >
                <CampaignWorkspacePage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/video-calls"
            element={
              <ProtectedRoute
                disallowUserTypes={["applicant"]}
                requiredCapabilities={[...INTERNAL_WORKFLOW_ROUTE_CAPABILITIES]}
                legacyUserTypeFallback={LEGACY_INTERNAL_FALLBACK}
              >
                <VideoCallsPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/government/positions"
            element={
              <ProtectedRoute
                disallowUserTypes={["applicant"]}
                requiredCapabilities={[...REGISTRY_ROUTE_CAPABILITIES]}
                legacyUserTypeFallback={LEGACY_INTERNAL_FALLBACK}
              >
                <GovernmentPositionsPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/government/personnel"
            element={
              <ProtectedRoute
                disallowUserTypes={["applicant"]}
                requiredCapabilities={[...REGISTRY_ROUTE_CAPABILITIES]}
                legacyUserTypeFallback={LEGACY_INTERNAL_FALLBACK}
              >
                <GovernmentPersonnelPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/government/appointments"
            element={
              <ProtectedRoute
                disallowUserTypes={["applicant"]}
                requiredCapabilities={[...APPOINTMENT_ROUTE_CAPABILITIES]}
                legacyUserTypeFallback={LEGACY_INTERNAL_FALLBACK}
              >
                <AppointmentsRegistryPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/rubrics"
            element={
              <ProtectedRoute
                disallowUserTypes={["applicant"]}
                requiredCapabilities={[...RUBRIC_MANAGE_CAPABILITIES]}
                legacyUserTypeFallback={LEGACY_INTERNAL_FALLBACK}
              >
                <RubricsPage />
              </ProtectedRoute>
            }
          />

          <Route
            path="/rubrics/new"
            element={
              <ProtectedRoute
                disallowUserTypes={["applicant"]}
                requiredCapabilities={[...RUBRIC_MANAGE_CAPABILITIES]}
                legacyUserTypeFallback={LEGACY_INTERNAL_FALLBACK}
              >
                <RubricBuilderPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/rubrics/:rubricId/edit"
            element={
              <ProtectedRoute
                disallowUserTypes={["applicant"]}
                requiredCapabilities={[...RUBRIC_MANAGE_CAPABILITIES]}
                legacyUserTypeFallback={LEGACY_INTERNAL_FALLBACK}
              >
                <RubricBuilderPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/dashboard"
            element={
              <ProtectedRoute adminOnly>
                <AdminDashboardPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/analytics"
            element={
              <ProtectedRoute adminOnly>
                <AdminAnalyticsPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/register"
            element={
              <ProtectedRoute adminOnly>
                <AdminRegisterPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/control-center"
            element={
              <ProtectedRoute adminOnly>
                <AdminControlCenterPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/users"
            element={
              <ProtectedRoute adminOnly>
                <AdminUsersPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/rubrics"
            element={
              <ProtectedRoute adminOnly>
                <RubricsPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/applications"
            element={
              <ProtectedRoute adminOnly>
                <AdminCasesPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/cases"
            element={
              <ProtectedRoute adminOnly>
                <AdminCasesPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/cases/:caseId"
            element={
              <ProtectedRoute adminOnly>
                <AdminCaseReview />
              </ProtectedRoute>
            }
          />

          <Route path="/error" element={<ErrorPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </Suspense>
    </div>
  );
};

const App: React.FC = () => {
  const dispatch = useDispatch<AppDispatch>();
  const isRehydrated = useSelector((state: RootState) =>
    state._persist ? state._persist.rehydrated : true,
  );
  const isAuthenticated = useSelector((state: RootState) => state.auth.isAuthenticated);
  const accessToken = useSelector((state: RootState) => state.auth.tokens?.access);

  useEffect(() => {
    if (!isRehydrated || !isAuthenticated || !accessToken) {
      return;
    }

    void dispatch(fetchProfile());
  }, [dispatch, isRehydrated, isAuthenticated, accessToken]);

  if (!isRehydrated) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Loader size="lg" className="animate-spin" />
      </div>
    );
  }

  return (
    <Router>
      <AppShell />
    </Router>
  );
};

export default App;




