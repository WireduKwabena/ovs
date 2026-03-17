// src/components/auth/ProtectedRoute.tsx
import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useSelector } from 'react-redux';
import type { RootState } from '@/app/store';
import { Loader } from '../common/Loader';
import { getDashboardPathForUser, resolveProtectedRouteRedirect } from '@/utils/authRouting';
import { canManageOrganizationGovernance } from '@/utils/organizationGovernance';
import { mergeRolesFromStore, mergeCapabilitiesFromStore } from '@/utils/authUtils';

interface ProtectedRouteProps {
  children: React.ReactNode;
  adminOnly?: boolean;
  platformAdminOnly?: boolean;
  orgAdminOnly?: boolean;
  disallowUserTypes?: Array<"applicant" | "internal" | "org_admin" | "platform_admin">;
  requiredRoles?: string[];
  requiredCapabilities?: string[];
  legacyUserTypeFallback?: Array<"org_admin" | "platform_admin">;
  requireOrganizationGovernance?: boolean;
  requireActiveOrganization?: boolean;
  activeOrganizationRedirectPath?: string;
}

export const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ 
  children, 
  adminOnly = false,
  platformAdminOnly = false,
  orgAdminOnly = false,
  disallowUserTypes = [],
  requiredRoles = [],
  requiredCapabilities = [],
  legacyUserTypeFallback = [],
  requireOrganizationGovernance = false,
  requireActiveOrganization = false,
  activeOrganizationRedirectPath = "/organization/setup",
}) => {
  const {
    isAuthenticated,
    userType,
    user,
    roles,
    capabilities,
    organizationMemberships,
    activeOrganization,
    twoFactorRequired,
    twoFactorToken,
  } = useSelector((state: RootState) => state.auth);
  const location = useLocation();

  const isRehydrated = useSelector(
    (state: RootState) => (state._persist ? state._persist.rehydrated : true),
  );

  if (!isRehydrated) {
    return <Loader size="lg" />;
  }

  const routeRedirect = resolveProtectedRouteRedirect({
    isAuthenticated,
    twoFactorRequired,
    twoFactorToken,
  });
  if (routeRedirect) {
    return <Navigate to={routeRedirect} state={{ from: location }} replace />;
  }

  const resolvedRoles = mergeRolesFromStore(
    roles,
    user as { roles?: string[]; group_roles?: string[] } | null,
  );

  const isPlatformAdmin = userType === "platform_admin" || userType === "admin";
  const isOrgAdmin = userType === "org_admin";
  const hasAdminRole = resolvedRoles.includes("admin");
  // isAdminOrOrgAdmin: true for platform admins AND org admins.
  // Use this for guards that both admin tiers should pass (e.g. adminOnly routes).
  // For platform-admin-only guards use isPlatformAdmin directly.
  const isAdminOrOrgAdmin = isPlatformAdmin || isOrgAdmin || hasAdminRole || Boolean(user && user.is_superuser);

  const fallbackDashboardPath = getDashboardPathForUser(userType);

  if (adminOnly && !isAdminOrOrgAdmin) {
    return <Navigate to={fallbackDashboardPath} replace />;
  }

  if (platformAdminOnly && !isPlatformAdmin) {
    return <Navigate to={fallbackDashboardPath} replace />;
  }

  if (orgAdminOnly && !isOrgAdmin) {
    return <Navigate to={fallbackDashboardPath} replace />;
  }

  const effectiveType = isPlatformAdmin ? "platform_admin" : isOrgAdmin ? "org_admin" : userType;
  if (effectiveType && (disallowUserTypes as string[]).includes(effectiveType)) {
    return <Navigate to={fallbackDashboardPath} replace />;
  }

  if (requiredRoles.length > 0 && !requiredRoles.some((role) => resolvedRoles.includes(role))) {
    return <Navigate to={fallbackDashboardPath} replace />;
  }

  const resolvedCapabilities = mergeCapabilitiesFromStore(
    capabilities,
    user as { capabilities?: string[] } | null,
  );
  const resolvedMemberships = Array.isArray(organizationMemberships) ? organizationMemberships : [];

  if (
    requireOrganizationGovernance &&
    !canManageOrganizationGovernance({
      isAdmin: isAdminOrOrgAdmin,
      roles: resolvedRoles,
      memberships: resolvedMemberships,
      activeOrganizationId: String(activeOrganization?.id || "").trim() || null,
    })
  ) {
    return <Navigate to={fallbackDashboardPath} replace />;
  }

  if (requireActiveOrganization) {
    const activeOrganizationId = String(activeOrganization?.id || "").trim();
    if (!activeOrganizationId) {
      const currentPath = `${location.pathname}${location.search || ""}`;
      const separator = activeOrganizationRedirectPath.includes("?") ? "&" : "?";
      const redirectTo = `${activeOrganizationRedirectPath}${separator}next=${encodeURIComponent(currentPath)}`;
      return <Navigate to={redirectTo} replace />;
    }
  }
  if (
    requiredCapabilities.length > 0 &&
    !requiredCapabilities.some((capability) => resolvedCapabilities.includes(capability))
  ) {
    const fallbackSet = new Set(legacyUserTypeFallback);
    const canUseLegacyFallback = isAdminOrOrgAdmin && (fallbackSet.has("platform_admin") || fallbackSet.has("org_admin"));
    if (canUseLegacyFallback) {
      return <>{children}</>;
    }
    return <Navigate to={fallbackDashboardPath} replace />;
  }

  return <>{children}</>;
};

