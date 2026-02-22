// frontend/src/App.tsx
import React from "react";
import {
  BrowserRouter as Router,
  Routes,
  Route,
  Navigate,
  useParams,
} from "react-router-dom";

import LoginPage from "./pages/LoginPage";
import RegisterPage from "./pages/RegisterPage";
import { DashboardPage } from "./pages/DashboardPage";
import { ApplicationsPage } from "./pages/ApplicationsPage";
import { RubricsPage } from "./pages/RubricsPage";
import { ProtectedRoute } from "./components/auth/ProtectedRoute";
import { Navbar } from "./components/common/Navbar";

import { NewApplicationPage } from "@/pages/NewApplicationPage";
import { ApplicationDetailPage } from "./pages/ApplicationDetailPage";
import { NotificationsPage } from "./pages/NotificationsPage";
import NotFoundPage from "./pages/NotFoundPage";
import { AdminDashboardPage } from "./pages/admin/AdminDashboardPage";
import RubricBuilderPage from "./pages/RubricBuilderPage";
import UploadDocumentsPage from "./pages/UploadDocumentPage";
import ForgotPasswordPage from "./pages/ForgotPasswordPage";
import ResetPasswordPage from "./pages/ResetPasswordPage";
import ChangePasswordPage from "./pages/ChangePasswordPage";
import EmailSentPage from "./pages/EmailSentPage";
import ErrorPage from "./pages/ErrorPage";
import HomePage from "./pages/HomePage";

import { RootState } from "./app/store";
import { useSelector } from "react-redux";
import { Loader } from "lucide-react";
import {HeyGenInterrogation} from "./components/interview/HeyGenInterrogation";



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
      </div>
    </Router>
  );
};

export default App;
