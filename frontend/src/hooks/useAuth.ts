// src/hooks/useAuth.ts (Redux-Migrated)
import { useSelector, useDispatch } from 'react-redux';
import type { RootState, AppDispatch } from '@/app/store';
import {
  login,
  logout,
  fetchProfile,
  clearError,
  updateUser,
  register,
  switchActiveOrganization,
} from '@/store/authSlice';
import type {
  AdminUser,
  CommitteeContext,
  LoginCredentials,
  OrganizationMembershipContext,
  OrganizationSummary,
  RegisterData,
  User,
} from '@/types';
import { useCallback } from 'react';
import { canManageOrganizationGovernance } from '@/utils/organizationGovernance';
import {
  APPOINTMENT_ROUTE_CAPABILITIES,
  APPOINTMENT_WORKFLOW_ROLES,
  CAMPAIGN_MANAGE_CAPABILITIES,
  FINAL_DECISION_ROLES,
  GOVERNMENT_WORKFLOW_CAPABILITIES,
  PUBLICATION_ROLES,
  RUBRIC_MANAGE_CAPABILITIES,
  STAGE_ACTOR_ROLES,
  STAGE_HISTORY_ROLES,
  hasAnyCapability as hasAnyCapabilityValue,
  hasAnyRole as hasAnyRoleValue,
} from '@/utils/frontendAuthz';

export const useAuth = () => {
  const dispatch = useDispatch<AppDispatch>();
  const {
    user,
    tokens,
    isAuthenticated,
    userType,
    roles,
    capabilities,
    organizations,
    organizationMemberships,
    committees,
    activeOrganization,
    switchingActiveOrganization,
    loading,
    error,
  } = useSelector((state: RootState) => state.auth);
  const resolvedRoles = Array.from(
    new Set([
      ...(Array.isArray(roles) ? roles : []),
      ...((user as { roles?: string[] } | null)?.roles ?? []),
      ...((user as { group_roles?: string[] } | null)?.group_roles ?? []),
    ]),
  );
  const resolvedCapabilities = Array.from(
    new Set([
      ...(Array.isArray(capabilities) ? capabilities : []),
      ...((user as { capabilities?: string[] } | null)?.capabilities ?? []),
    ]),
  );
  const resolvedOrganizations = Array.isArray(organizations) ? organizations : [];
  const resolvedOrganizationMemberships = Array.isArray(organizationMemberships)
    ? organizationMemberships
    : [];
  const resolvedCommittees = Array.isArray(committees) ? committees : [];

  const hasRole = useCallback(
    (role: string) => resolvedRoles.includes(role),
    [resolvedRoles],
  );
  const hasAnyRole = useCallback(
    (requiredRoles: string[]) => requiredRoles.some((role) => resolvedRoles.includes(role)),
    [resolvedRoles],
  );
  const hasCapability = useCallback(
    (capability: string) => resolvedCapabilities.includes(capability),
    [resolvedCapabilities],
  );
  const hasAnyCapability = useCallback(
    (requiredCapabilities: string[]) =>
      requiredCapabilities.some((capability) => resolvedCapabilities.includes(capability)),
    [resolvedCapabilities],
  );
  const hasCommitteeMembership = useCallback(
    (committeeId: string) => {
      const normalizedCommitteeId = String(committeeId || "").trim();
      if (!normalizedCommitteeId) {
        return false;
      }
      return resolvedCommittees.some(
        (membership: CommitteeContext) =>
          String(membership.committee_id || "").trim() === normalizedCommitteeId,
      );
    },
    [resolvedCommittees],
  );

  const hasAdminRole = hasRole("admin");
  const isAdmin = userType === "admin" || hasAdminRole || Boolean(user && user.is_superuser);
  const activeOrganizationId = String(activeOrganization?.id || "").trim() || null;
  const hasMultipleOrganizations = resolvedOrganizations.length > 1;
  const hasGovernmentCapability = hasAnyCapabilityValue(
    resolvedCapabilities,
    GOVERNMENT_WORKFLOW_CAPABILITIES,
  );
  const isInternalOrAdmin = isAdmin || hasGovernmentCapability;
  const isApplicant = userType === 'applicant';
  const canViewAuditLogs = isAdmin || hasCapability("gams.audit.view");
  const canManageRegistry = isAdmin || hasCapability("gams.registry.manage");
  const canAccessAppointments =
    isAdmin ||
    hasAnyCapabilityValue(resolvedCapabilities, APPOINTMENT_ROUTE_CAPABILITIES) ||
    hasAnyRoleValue(resolvedRoles, APPOINTMENT_WORKFLOW_ROLES);
  const canAdvanceAppointmentStage =
    isAdmin ||
    hasAnyRoleValue(resolvedRoles, STAGE_ACTOR_ROLES) ||
    hasCapability("gams.appointment.stage");
  const canFinalizeAppointment =
    isAdmin ||
    hasAnyRoleValue(resolvedRoles, FINAL_DECISION_ROLES) ||
    hasCapability("gams.appointment.decide");
  const canPublishAppointment =
    isAdmin ||
    hasAnyRoleValue(resolvedRoles, PUBLICATION_ROLES) ||
    hasCapability("gams.appointment.publish");
  const canViewAppointmentStageActions = isAdmin || hasAnyRoleValue(resolvedRoles, STAGE_HISTORY_ROLES);
  const canAccessInternalWorkflow =
    isAdmin ||
    hasGovernmentCapability ||
    hasAnyRoleValue(resolvedRoles, APPOINTMENT_WORKFLOW_ROLES);
  const canAccessApplications = canAccessInternalWorkflow || canViewAuditLogs;
  const canAccessCampaigns =
    isAdmin ||
    hasAnyCapabilityValue(resolvedCapabilities, CAMPAIGN_MANAGE_CAPABILITIES);
  const canAccessVideoCalls = canAccessInternalWorkflow;
  const canManageRubrics =
    isAdmin ||
    hasAnyCapabilityValue(resolvedCapabilities, RUBRIC_MANAGE_CAPABILITIES);
  const canManageRegistryInActiveOrganization =
    canManageRegistry && (isAdmin || Boolean(activeOrganizationId));
  const canSwitchOrganization = isAuthenticated && userType !== "applicant" && hasMultipleOrganizations;
  const canManageActiveOrganizationGovernance =
    canManageOrganizationGovernance({
      isAdmin,
      roles: resolvedRoles,
      memberships: resolvedOrganizationMemberships as OrganizationMembershipContext[],
      activeOrganizationId,
    });

  const authLogin = useCallback(
    async (credentials: LoginCredentials) => {
      return dispatch(login(credentials)).unwrap();
    },
    [dispatch]
  );

  const authRegister = useCallback(
    async (data: RegisterData) => {
      return await dispatch(register(data)).unwrap();
    },
    [dispatch]
  );

  const authLogout = useCallback(async () => {
    await dispatch(logout()).unwrap();
  }, [dispatch]);

  const authUpdateUser = useCallback(
    (userData: Partial<User | AdminUser>) => {
      dispatch(updateUser(userData));
    },
    [dispatch]
  );

  const refreshProfile = useCallback(() => {
    dispatch(fetchProfile());
  }, [dispatch]);

  const selectActiveOrganization = useCallback(
    async (organizationId: string | null) => {
      return dispatch(switchActiveOrganization(organizationId)).unwrap();
    },
    [dispatch],
  );

  const clearAuthError = useCallback(() => {
    dispatch(clearError());
  }, [dispatch]);

  return {
    user,
    token: tokens?.access,  // Backward compat for single token if needed
    tokens,  // Full tokens
    isAuthenticated,
    userType,
    roles: resolvedRoles,
    capabilities: resolvedCapabilities,
    organizations: resolvedOrganizations as OrganizationSummary[],
    organizationMemberships: resolvedOrganizationMemberships as OrganizationMembershipContext[],
    committees: resolvedCommittees as CommitteeContext[],
    activeOrganization,
    activeOrganizationId,
    hasMultipleOrganizations,
    canSwitchOrganization,
    switchingActiveOrganization,
    hasRole,
    hasAnyRole,
    hasCapability,
    hasAnyCapability,
    hasCommitteeMembership,
    isAdmin,
    isInternalOrAdmin: isInternalOrAdmin,
    isApplicant,
    canViewAuditLogs,
    canManageRegistry,
    canManageRegistryInActiveOrganization,
    canAccessAppointments,
    canAdvanceAppointmentStage,
    canFinalizeAppointment,
    canPublishAppointment,
    canViewAppointmentStageActions,
    canAccessInternalWorkflow,
    canAccessApplications,
    canAccessCampaigns,
    canAccessVideoCalls,
    canManageRubrics,
    canManageActiveOrganizationGovernance,
    loading,
    error,
    login: authLogin,
    logout: authLogout,
    updateUser: authUpdateUser,
    register: authRegister,
    refreshProfile,
    selectActiveOrganization,
    clearError: clearAuthError,
  };
};

