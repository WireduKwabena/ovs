// src/components/auth/ProtectedRoute.tsx
import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useSelector } from 'react-redux';
import type { RootState } from '@/app/store';  // Fixed: space + path
import { Loader } from '../common/Loader';

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
  const { isAuthenticated, userType } = useSelector((state: RootState) => state.auth);
  const location = useLocation();

   const isRehydrated = useSelector(
    (state: RootState) => state._persist?.rehydrated
  );

  if (!isRehydrated) {
    return <Loader size="lg" />;  // Show loader during auth rehydration
  }
  
  // 2️⃣ Redirect to login if not authenticated

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (adminOnly && userType !== 'admin') {
    return <Navigate to="/dashboard" replace />;
  }

  if (userType && disallowUserTypes.includes(userType)) {
    return <Navigate to="/dashboard" replace />;
  }

  return <>{children}</>;
};
