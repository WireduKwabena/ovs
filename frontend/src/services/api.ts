// src/services/api.ts (Tweaked - Redux Migration)
import axios, { AxiosError, type InternalAxiosRequestConfig } from 'axios';
import { store } from '../app/store'; // Import store for dispatch
import type { ApiError } from '@/types';
import { logout, refreshToken } from '@/store/authSlice';
import { setError } from '@/store/errorSlice';

const API_URL = ((import.meta as any).env?.VITE_API_URL) || 'http://localhost:8000/api';

const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor - add auth token from Redux
api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = store.getState().auth.tokens?.access; // From Redux
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor - handle 401 with refresh
api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError<ApiError>) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean };
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;
      try {
        const refreshResult = await store.dispatch(refreshToken()).unwrap(); // Dispatch thunk
        originalRequest.headers.Authorization = `Bearer ${refreshResult.access}`;
        return api(originalRequest); // Retry original
      } catch (refreshError) {
        store.dispatch(logout()); // Fallback logout
      }
    } else if (error.response?.status === 401) {
      store.dispatch(logout());
    } else {
      // For other errors, dispatch the setError action
      const errorData = {
        message: error.response?.data?.message || error.message || 'An error occurred',
        status: error.response?.status || 500,
      };
      store.dispatch(setError(errorData));
    }
    return Promise.reject(error);
  }
);

export default api;

// Helper function to handle API errors
export const handleApiError = (error: unknown): string => {
  if (axios.isAxiosError(error)) {
    const apiError = error.response?.data as ApiError;
    return apiError?.message || error.message || 'An error occurred';
  }
  return 'An unexpected error occurred';
};