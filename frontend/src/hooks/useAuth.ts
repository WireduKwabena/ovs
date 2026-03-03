// src/hooks/useAuth.ts (Redux-Migrated)
import { useSelector, useDispatch } from 'react-redux';
import type { RootState, AppDispatch } from '@/app/store';
import { login, logout, fetchProfile, clearError, updateUser, register } from '@/store/authSlice';
import type { AdminUser, LoginCredentials, RegisterData, User } from '@/types';
import { useCallback } from 'react';

export const useAuth = () => {
  const dispatch = useDispatch<AppDispatch>();
  const { user, tokens, isAuthenticated, userType, loading, error } = useSelector((state: RootState) => state.auth);

  const isAdmin = userType === 'admin';
  const isHrOrAdmin = userType === 'admin' || userType === 'hr_manager';
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
    isAdmin,
    isHrOrAdmin,
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
