// src/services/auth.service.ts (Tweaked)
import api from './api';
import type { User, AdminUser, AuthTokens, ApiError } from '@/types';  // Add ApiError

export interface LoginCredentials {
  email: string;
  password: string;
}

export interface RegisterData {
  email: string;
  password: string;
  password_confirm: string;
  first_name: string;
  last_name: string;
  phone_number: string;
  organization: string;
  department: string;
}

export interface LoginResponse {
  user: User | AdminUser;
  tokens: AuthTokens;
  user_type?: 'applicant' | 'hr_manager' | 'admin';
}

export const authService = {
  async login(credentials: LoginCredentials): Promise<LoginResponse> {
    try {
      const response = await api.post<LoginResponse>('/auth/login/', credentials);
      return response.data;
    } catch (error: any) {
      throw new Error((error.response?.data as ApiError)?.message || 'Login failed');  // Typed error
    }
  },

  async register(data: RegisterData): Promise<LoginResponse> {
    try {
      const response = await api.post<LoginResponse>('/auth/register/', data);
      return response.data;
    } catch (error: any) {
      throw new Error((error.response?.data as ApiError)?.message || 'Registration failed');
    }
  },

  async logout(refreshToken: string): Promise<void> {
    try {
      await api.post('/auth/logout/', { refresh: refreshToken });
    } catch (error: any) {
      // Logout even on error (blacklist best-effort)
      console.warn('Logout API failed:', error);
    }
  },

  async getProfile(): Promise<{ user: User | AdminUser; user_type: string }> {
    try {
      const response = await api.get('/auth/profile/');
      return response.data;
    } catch (error: any) {
      throw new Error((error.response?.data as ApiError)?.message || 'Profile fetch failed');
    }
  },

  async updateProfile(data: Partial<User | AdminUser>): Promise<User | AdminUser> {
    try {
      const response = await api.put('/auth/profile/update/', data);
      return response.data;
    } catch (error: any) {
      throw new Error((error.response?.data as ApiError)?.message || 'Update failed');
    }
  },

  async changePassword(data: {
    old_password: string;
    new_password: string;
    new_password_confirm: string;
  }): Promise<void> {
    try {
      await api.post('/auth/change-password/', data);
    } catch (error: any) {
      throw new Error((error.response?.data as ApiError)?.message || 'Password change failed');
    }
  },

  async resetPassword(token: string, data: {
    new_password1: string;
    new_password2: string;
  }): Promise<void> {
    try {
      await api.post('/auth/password-reset/confirm/', { ...data, token });
    } catch (error: any) {
      throw new Error((error.response?.data as ApiError)?.message || 'Password reset failed');
    }
  },

  async requestPasswordReset(email: string): Promise<void> {
    try {
      await api.post('/auth/password-reset/', { email });
    } catch (error: any) {
      throw new Error((error.response?.data as ApiError)?.message || 'Reset request failed');
    }
  },

  async refreshToken(refreshToken: string): Promise<AuthTokens> {
    try {
      const response = await api.post<AuthTokens>('/auth/token/refresh/', {
        refresh: refreshToken,
      });
      return response.data;
    } catch (error: any) {
      throw new Error((error.response?.data as ApiError)?.message || 'Refresh failed');
    }
  },

};
