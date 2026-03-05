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
}

export const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ 
  children, 
  adminOnly = false,
  disallowUserTypes = [],
}) => {
  const { isAuthenticated, userType, user, twoFactorRequired, twoFactorToken } = useSelector(
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

  const hasAdminAccess = userType === 'admin' || Boolean(user && (user.is_staff || user.is_superuser));

  if (adminOnly && !hasAdminAccess) {
    return <Navigate to="/dashboard" replace />;
  }

  if (userType && disallowUserTypes.includes(userType)) {
    return <Navigate to="/dashboard" replace />;
  }

  return <>{children}</>;
};
