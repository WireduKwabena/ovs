import React from "react";
import { Navigate } from "react-router-dom";

import { Loader } from "@/components/common/Loader";
import { useAuth } from "@/hooks/useAuth";
import {
  getCandidatePath,
  getOrgAdminPath,
  getOrganizationSetupPath,
  getPlatformAdminPath,
  getWorkspacePath,
} from "@/utils/appPaths";

export const DashboardPage: React.FC = () => {
  const {
    loading,
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

  if (loading) {
    return <Loader size="lg" />;
  }

  if (userType === "admin") {
    return <Navigate to={getPlatformAdminPath("dashboard")} replace />;
  }

  if (userType === "applicant") {
    return <Navigate to={getCandidatePath("home")} replace />;
  }

  if (canManageActiveOrganizationGovernance) {
    if (activeOrganizationId) {
      return <Navigate to={getOrgAdminPath(activeOrganizationId, "dashboard")} replace />;
    }
    return <Navigate to={getOrganizationSetupPath("/dashboard")} replace />;
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
    return <Navigate to={getWorkspacePath("home")} replace />;
  }

  return <Navigate to={getCandidatePath("home")} replace />;
};

export default DashboardPage;
