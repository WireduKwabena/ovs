// frontend/src/App.tsx
import React, { Suspense } from "react";
import {
  BrowserRouter as Router,
  Routes,
  Route,
  Navigate,
  useParams,
} from "react-router-dom";

import { ProtectedRoute } from "./components/auth/ProtectedRoute";
import { Navbar } from "./components/common/Navbar";

import { RootState } from "./app/store";
import { useSelector } from "react-redux";
import { Loader } from "lucide-react";

const HomePage = React.lazy(() => import("./pages/HomePage"));
const LoginPage = React.lazy(() => import("./pages/LoginPage"));
const RegisterPage = React.lazy(() => import("./pages/RegisterPage"));
const ForgotPasswordPage = React.lazy(() => import("./pages/ForgotPasswordPage"));
const EmailSentPage = React.lazy(() => import("./pages/EmailSentPage"));
const ResetPasswordPage = React.lazy(() => import("./pages/ResetPasswordPage"));
const CandidateAccessPage = React.lazy(() => import("./pages/CandidateAccessPage"));
const InvitationAcceptPage = React.lazy(() => import("./pages/InvitationAcceptPage"));
const DashboardPage = React.lazy(() => import("./pages/DashboardPage"));
const ChangePasswordPage = React.lazy(() => import("./pages/ChangePasswordPage"));
const UploadDocumentsPage = React.lazy(() => import("./pages/UploadDocumentPage"));
const CampaignsPage = React.lazy(() => import("./pages/CampaignsPage"));
const CampaignWorkspacePage = React.lazy(() => import("./pages/CampaignWorkspacePage"));
const RubricBuilderPage = React.lazy(() => import("./pages/RubricBuilderPage"));
const ErrorPage = React.lazy(() => import("./pages/ErrorPage"));
const NotFoundPage = React.lazy(() => import("./pages/NotFoundPage"));
const AdminDashboardPage = React.lazy(() => import("./pages/admin/AdminDashboardPage"));
const ApplicationsPage = React.lazy(() =>
  import("./pages/ApplicationsPage").then((module) => ({ default: module.ApplicationsPage }))
);
const RubricsPage = React.lazy(() =>
  import("./pages/RubricsPage").then((module) => ({ default: module.RubricsPage }))
);
const NewApplicationPage = React.lazy(() =>
  import("./pages/NewApplicationPage").then((module) => ({ default: module.NewApplicationPage }))
);
const ApplicationDetailPage = React.lazy(() =>
  import("./pages/ApplicationDetailPage").then((module) => ({ default: module.ApplicationDetailPage }))
);
const NotificationsPage = React.lazy(() =>
  import("./pages/NotificationsPage").then((module) => ({ default: module.NotificationsPage }))
);
const HeyGenInterrogation = React.lazy(() =>
  import("./components/interview/HeyGenInterrogation").then((module) => ({ default: module.HeyGenInterrogation }))
);



const HeyGenInterrogationPage: React.FC = () => {
    const { applicationId } = useParams<{ applicationId: string }>();
    
    if (!applicationId) {
      return <Navigate to="/dashboard" />;
    }
  
    return (
      <HeyGenInterrogation 
        applicationId={applicationId} 
      />
    );
  };

const App: React.FC = () => {
  const isAuthenticated = useSelector(
    (state: RootState) => state.auth.isAuthenticated
  );

  // redux-persist flag
  const isRehydrated = useSelector(
    (state: RootState) => state._persist?.rehydrated
  );

  if (!isRehydrated) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Loader size="lg" className="animate-spin" />
      </div>
    );
  }

  return (
    <Router>
      <div className="min-h-screen bg-gray-50">
        {/* Navbar for logged-in users */}
        {isAuthenticated && <Navbar />}

        <Suspense
          fallback={
            <div className="flex items-center justify-center min-h-[40vh]">
              <Loader size="lg" className="animate-spin" />
            </div>
          }
        >
          <Routes>
            {/* ----------------- PUBLIC ROUTES ----------------- */}
            <Route path="/" element={<HomePage />} />
            <Route
              path="/login"
              element={
                isAuthenticated ? <Navigate to="/dashboard" /> : <LoginPage />
              }
            />
            <Route
              path="/register"
              element={
                isAuthenticated ? <Navigate to="/dashboard" /> : <RegisterPage />
              }
            />
            <Route
              path="/forgot-password"
              element={
                isAuthenticated ? (
                  <Navigate to="/dashboard" />
                ) : (
                  <ForgotPasswordPage />
                )
              }
            />
            <Route
              path="/forgot-password/email-sent"
              element={
                isAuthenticated ? <Navigate to="/dashboard" /> : <EmailSentPage />
              }
            />
            <Route
              path="/reset-password/:token"
              element={
                isAuthenticated ? (
                  <Navigate to="/dashboard" />
                ) : (
                  <ResetPasswordPage />
                )
              }
            />
            <Route path="/candidate/access" element={<CandidateAccessPage />} />
            <Route path="/invite/:token" element={<InvitationAcceptPage />} />
            {/* ----------------- PROTECTED ROUTES (USER) ----------------- */}
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
              path="/rubrics"
              element={
                <ProtectedRoute>
                  <RubricsPage />
                </ProtectedRoute>
              }
            />
            {/* ----------------- ADMIN ROUTES ----------------- */}
            <Route
              path="/rubrics/new"
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
                  <ApplicationsPage />
                </ProtectedRoute>
              }
            />
            {/* ----------------- ERROR + FALLBACK ----------------- */}
            <Route path="/error" element={<ErrorPage />} />
            <Route path="*" element={<NotFoundPage />} />
          </Routes>
        </Suspense>
      </div>
    </Router>
  );
};

export default App;
