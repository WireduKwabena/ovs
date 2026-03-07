// src/hooks/useAuth.ts (Redux-Migrated)
import { useSelector, useDispatch } from 'react-redux';
import type { RootState, AppDispatch } from '@/app/store';
import { login, logout, fetchProfile, clearError, updateUser, register } from '@/store/authSlice';
import type { AdminUser, LoginCredentials, RegisterData, User } from '@/types';
import { useCallback } from 'react';

export const useAuth = () => {
  const dispatch = useDispatch<AppDispatch>();
  const { user, tokens, isAuthenticated, userType, roles, capabilities, loading, error } = useSelector(
    (state: RootState) => state.auth,
  );
  const resolvedRoles = Array.isArray(roles) ? roles : [];
  const resolvedCapabilities = Array.isArray(capabilities) ? capabilities : [];

  const hasAdminRole = resolvedRoles.includes("admin");
  const isAdmin = userType === "admin" || hasAdminRole || Boolean(user && user.is_superuser);
  const hasGovernmentCapability = resolvedCapabilities.some((capability) =>
    [
      "gams.registry.manage",
      "gams.appointment.stage",
      "gams.appointment.decide",
      "gams.appointment.publish",
      "gams.appointment.view_internal",
    ].includes(capability),
  );
  const isHrOrAdmin = userType === 'admin' || userType === 'hr_manager' || hasGovernmentCapability;
  const isApplicant = userType === 'applicant';

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
    isAdmin,
    isHrOrAdmin: isHrOrAdmin,
    isApplicant,
    loading,
    error,
    login: authLogin,
    logout: authLogout,
    updateUser: authUpdateUser,
    register: authRegister,
    refreshProfile,
    clearError: clearAuthError,
  };
};
