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

import { Navbar } from "./components/common/Navbar";
import { ProtectedRoute } from "./components/auth/ProtectedRoute";
import { UnauthenticatedRoute } from "./components/auth/UnauthenticatedRoute";
import { fetchProfile } from "./store/authSlice";
import { type AppDispatch, type RootState } from "./app/store";

const HomePage = React.lazy(() => import("./pages/HomePage"));
const SubscriptionPlansPage = React.lazy(() => import("./pages/SubscriptionPlansPage"));
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
const UploadDocumentsPage = React.lazy(() => import("./pages/UploadDocumentPage"));
const CampaignsPage = React.lazy(() => import("./pages/CampaignsPage"));
const CampaignWorkspacePage = React.lazy(() => import("./pages/CampaignWorkspacePage"));
const VideoCallsPage = React.lazy(() => import("./pages/VideoCallsPage"));
const RubricBuilderPage = React.lazy(() => import("./pages/RubricBuilderPage"));
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
const NewApplicationPage = React.lazy(() =>
  import("./pages/NewApplicationPage").then((module) => ({ default: module.NewApplicationPage })),
);
const ApplicationDetailPage = React.lazy(() =>
  import("./pages/ApplicationDetailPage").then((module) => ({ default: module.ApplicationDetailPage })),
);
const NotificationsPage = React.lazy(() =>
  import("./pages/NotificationsPage").then((module) => ({ default: module.NotificationsPage })),
);
const HeyGenInterrogation = React.lazy(() =>
  import("./components/interview/HeyGenInterrogation").then((module) => ({
    default: module.HeyGenInterrogation,
  })),
);

const HIDE_NAVBAR_PREFIXES = [
  "/",
  "/subscribe",
  "/login",
  "/register",
  "/forgot-password",
  "/reset-password",
  "/billing",
];

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

const AppShell: React.FC = () => {
  const isAuthenticated = useSelector((state: RootState) => state.auth.isAuthenticated);
  const location = useLocation();
  const hideNavbar = shouldHideNavbar(location.pathname);

  return (
    <div className="min-h-screen bg-gray-50">
      {isAuthenticated && !hideNavbar && <Navbar />}

      <Suspense
        fallback={
          <div className="flex min-h-[40vh] items-center justify-center">
            <Loader size="lg" className="animate-spin" />
          </div>
        }
      >
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/subscribe" element={<SubscriptionPlansPage />} />
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
          <Route path="/invite/:token" element={<InvitationAcceptPage />} />

          <Route
            path="/interview/interrogation/:applicationId"
            element={
              <ProtectedRoute>
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
              <ProtectedRoute disallowUserTypes={["applicant"]}>
                <FraudInsightsPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/background-checks"
            element={
              <ProtectedRoute disallowUserTypes={["applicant"]}>
                <BackgroundChecksPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/audit-logs"
            element={
              <ProtectedRoute disallowUserTypes={["applicant"]}>
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
              <ProtectedRoute disallowUserTypes={["applicant"]}>
                <AiMonitorPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/applications"
            element={
              <ProtectedRoute>
                <ApplicationsPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/applications/new"
            element={
              <ProtectedRoute>
                <NewApplicationPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/applications/:caseId"
            element={
              <ProtectedRoute>
                <ApplicationDetailPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/applications/:caseId/upload"
            element={
              <ProtectedRoute>
                <UploadDocumentsPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/notifications"
            element={
              <ProtectedRoute>
                <NotificationsPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/campaigns"
            element={
              <ProtectedRoute>
                <CampaignsPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/campaigns/:campaignId"
            element={
              <ProtectedRoute>
                <CampaignWorkspacePage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/video-calls"
            element={
              <ProtectedRoute>
                <VideoCallsPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/rubrics"
            element={
              <ProtectedRoute>
                <RubricsPage />
              </ProtectedRoute>
            }
          />

          <Route
            path="/rubrics/new"
            element={
              <ProtectedRoute adminOnly>
                <RubricBuilderPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/rubrics/:rubricId/edit"
            element={
              <ProtectedRoute adminOnly>
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




