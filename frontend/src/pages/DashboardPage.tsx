import React from "react";
import { Navigate } from "react-router-dom";

import { useAuth } from "@/hooks/useAuth";

export const DashboardPage: React.FC = () => {
  const {
    userType,
    hasAnyRole,
    canAccessInternalWorkflow,
    canAccessApplications,
    canAccessCampaigns,
    canAccessVideoCalls,
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

  if (canManageActiveOrganizationGovernance) {
    if (activeOrganizationId) {
      return <Navigate to="/organization/dashboard" replace />;
    }
    return <Navigate to="/organization/setup?next=/organization/dashboard" replace />;
  }

  const isCommitteeActor =
    typeof hasAnyRole === "function" &&
    hasAnyRole(["committee_member", "committee_chair"]);
  const canAccessSharedWorkspace =
    userType === "internal" ||
    canAccessInternalWorkflow ||
    canAccessApplications ||
    canAccessCampaigns ||
    canAccessVideoCalls ||
    canManageRegistry ||
    canAccessAppointments ||
    canViewAuditLogs ||
    isCommitteeActor;

  if (canAccessSharedWorkspace) {
    return <Navigate to="/workspace" replace />;
  }

  return <Navigate to="/candidate/access" replace />;
};

export default DashboardPage;
