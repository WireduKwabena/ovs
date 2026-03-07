// src/components/auth/ProtectedRoute.tsx
import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useSelector } from 'react-redux';
import type { RootState } from '@/app/store';
import { Loader } from '../common/Loader';
import { resolveProtectedRouteRedirect } from '@/utils/authRouting';

interface ProtectedRouteProps {
  children: React.ReactNode;
  adminOnly?: boolean;
  disallowUserTypes?: Array<"applicant" | "hr_manager" | "admin">;
  requiredRoles?: string[];
  requiredCapabilities?: string[];
}

export const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ 
  children, 
  adminOnly = false,
  disallowUserTypes = [],
  requiredRoles = [],
  requiredCapabilities = [],
}) => {
  const { isAuthenticated, userType, user, roles, capabilities, twoFactorRequired, twoFactorToken } = useSelector(
    (state: RootState) => state.auth,
  );
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

  const resolvedRoles = Array.from(
    new Set([
      ...(Array.isArray(roles) ? roles : []),
      ...((user as { roles?: string[] } | null)?.roles ?? []),
    ]),
  );
  const hasAdminAccess =
    userType === "admin" ||
    resolvedRoles.includes("admin") ||
    Boolean(user && user.is_superuser);

  if (adminOnly && !hasAdminAccess) {
    return <Navigate to="/dashboard" replace />;
  }

  if (userType && disallowUserTypes.includes(userType)) {
    return <Navigate to="/dashboard" replace />;
  }

  if (requiredRoles.length > 0 && !requiredRoles.some((role) => resolvedRoles.includes(role))) {
    return <Navigate to="/dashboard" replace />;
  }

  const resolvedCapabilities = Array.from(
    new Set([
      ...(Array.isArray(capabilities) ? capabilities : []),
      ...((user as { capabilities?: string[] } | null)?.capabilities ?? []),
    ]),
  );
  if (
    requiredCapabilities.length > 0 &&
    !requiredCapabilities.some((capability) => resolvedCapabilities.includes(capability))
  ) {
    return <Navigate to="/dashboard" replace />;
  }

  return <>{children}</>;
};
