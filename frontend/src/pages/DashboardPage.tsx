import React, { Suspense } from "react";
import { Navigate } from "react-router-dom";

import { Loader } from "@/components/common/Loader";
import { useAuth } from "@/hooks/useAuth";

const OperationsDashboardPage = React.lazy(() => import("@/pages/OperationsDashboardPage"));

export const DashboardPage: React.FC = () => {
  const {
    userType,
    canAccessInternalWorkflow,
    activeOrganizationId,
    canManageActiveOrganizationGovernance,
    canAccessAppointments,
    canManageRegistry,
    canViewAuditLogs,
  } = useAuth();

  if (userType === "admin") {
    return <Navigate to="/admin/dashboard" replace />;
  }

  if (userType === "applicant") {
    return <Navigate to="/candidate/access" replace />;
  }

  if (canManageActiveOrganizationGovernance && activeOrganizationId) {
    return <Navigate to="/organization/dashboard" replace />;
  }

  if (canAccessAppointments) {
    return <Navigate to="/government/appointments" replace />;
  }

  if (canManageRegistry) {
    return <Navigate to="/government/positions" replace />;
  }

  if (canViewAuditLogs) {
    return <Navigate to="/audit-logs" replace />;
  }

  if (canAccessInternalWorkflow) {
    return (
      <Suspense
        fallback={
          <main className="max-w-7xl mx-auto px-4 py-10">
            <div className="rounded-xl border border-slate-200 bg-white p-10 flex items-center justify-center">
              <Loader size="lg" />
            </div>
          </main>
        }
      >
        <OperationsDashboardPage />
      </Suspense>
    );
  }

  return <Navigate to="/candidate/access" replace />;
};

export default DashboardPage;
