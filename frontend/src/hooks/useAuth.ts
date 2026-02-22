// src/hooks/useAuth.ts (Redux-Migrated)
import { useSelector, useDispatch } from 'react-redux';
import type { RootState, AppDispatch } from '@/app/store';  // Adjust path
import { login, logout, fetchProfile, clearError, updateUser, register } from '@/store/authSlice';  // Import thunks/actions
import type { AdminUser, LoginCredentials, RegisterData, User } from '@/types';
import { useCallback } from 'react';

export const useAuth = () => {
  const dispatch = useDispatch<AppDispatch>();
  const { user, tokens, isAuthenticated, userType, loading, error } = useSelector((state: RootState) => state.auth);

  const isAdmin = userType === 'admin' || userType === 'hr_manager';
  const isApplicant = userType === 'applicant';

  const authLogin = async (credentials: LoginCredentials) => {
    return dispatch(login(credentials)).unwrap();  // Returns promise for .then/toast
  };

  const authRegister = useCallback(
    async (data: RegisterData) => {
      return await dispatch(register(data)).unwrap();
    },
    [dispatch]
  );

  const authLogout = () => {
    dispatch(logout());
  };

  const authUpdateUser = (userData: Partial<User | AdminUser>) => {
    dispatch(updateUser(userData));
  };

  const refreshProfile = () => {
    dispatch(fetchProfile());
  };

  const clearAuthError = () => {
    dispatch(clearError());
  };

  return {
    user,
    token: tokens?.access,  // Backward compat for single token if needed
    tokens,  // Full tokens
    isAuthenticated,
    userType,
    isAdmin,
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
