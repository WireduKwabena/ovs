// src/services/api.ts
import axios, { AxiosError, type InternalAxiosRequestConfig } from 'axios';
import { store } from '../app/store';
import type { ApiError } from '@/types';
import { logout, refreshToken } from '@/store/authSlice';
import { setError } from '@/store/errorSlice';
import { API_URL } from '@/config/env';
import { getApiErrorMessage as _getApiErrorMessage } from '@/utils/apiError';

const AUTH_ENDPOINTS = [
  '/auth/login/',
  '/auth/login/verify/',
  '/auth/admin/login/',
  '/auth/admin/login/verify/',
  '/auth/register/',
  '/auth/register/organization-admin/',
  '/auth/logout/',
  '/auth/token/refresh/',
  '/auth/password-reset/',
  '/auth/password-reset-confirm/',
];

const CANDIDATE_SESSION_ENDPOINT_PREFIXES = [
  '/invitations/access/',
  '/applications/cases/',
  '/applications/documents/',
  '/interviews/sessions/',
  '/interviews/responses/',
];

const isAuthEndpoint = (url?: string) => {
  if (!url) return false;
  return AUTH_ENDPOINTS.some((endpoint) => url.includes(endpoint));
};

const isCandidateSessionEndpoint = (url?: string) => {
  if (!url) return false;
  return CANDIDATE_SESSION_ENDPOINT_PREFIXES.some((prefix) => url.includes(prefix));
};

const api = axios.create({
  baseURL: API_URL,
  withCredentials: false,
  headers: {
    'Content-Type': 'application/json',
  },
});

// ---------------------------------------------------------------------------
// Request interceptor
// ---------------------------------------------------------------------------

api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const authState = store.getState().auth;
    const token = authState.tokens?.access;

    // Attach Bearer token
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }

    return config;
  },
  (error) => Promise.reject(error)
);

// ---------------------------------------------------------------------------
// Token-refresh serialization
// ---------------------------------------------------------------------------

let _isRefreshing = false;
interface _QueueEntry { resolve: (token: string) => void; reject: (err: unknown) => void }
let _refreshQueue: _QueueEntry[] = [];

function _processRefreshQueue(newAccessToken: string) {
  _refreshQueue.forEach(({ resolve }) => resolve(newAccessToken));
  _refreshQueue = [];
}

function _drainRefreshQueueWithError(err: unknown) {
  _refreshQueue.forEach(({ reject }) => reject(err));
  _refreshQueue = [];
}

// ---------------------------------------------------------------------------
// Response interceptor
// ---------------------------------------------------------------------------

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError<ApiError>) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean };
    const statusCode = error.response?.status;
    const requestUrl = originalRequest?.url;

    if (statusCode === 401 && (isAuthEndpoint(requestUrl) || isCandidateSessionEndpoint(requestUrl))) {
      return Promise.reject(error);
    }

    if (statusCode === 401 && originalRequest && !originalRequest._retry) {
      originalRequest._retry = true;

      if (_isRefreshing) {
        return new Promise<string>((resolve, reject) => {
          _refreshQueue.push({ resolve, reject });
        }).then((newToken) => {
          if (originalRequest.headers) {
            originalRequest.headers.Authorization = `Bearer ${newToken}`;
          }
          return api(originalRequest);
        });
      }

      _isRefreshing = true;
      try {
        const refreshResult = await store.dispatch(refreshToken()).unwrap();
        _processRefreshQueue(refreshResult.access);
        if (originalRequest.headers) {
          originalRequest.headers.Authorization = `Bearer ${refreshResult.access}`;
        }
        return api(originalRequest);
      } catch (refreshErr) {
        _drainRefreshQueueWithError(refreshErr);
        await store.dispatch(logout());
        store.dispatch(
          setError({
            message: 'Session expired. Please sign in again.',
            status: 401,
          })
        );
      } finally {
        _isRefreshing = false;
      }
    } else if (statusCode === 401) {
      await store.dispatch(logout());
      store.dispatch(
        setError({
          message: 'Session expired. Please sign in again.',
          status: 401,
        })
      );
    } else {
      const errorData = {
        message: _getApiErrorMessage(error, 'An error occurred'),
        status: statusCode || 500,
      };
      store.dispatch(setError(errorData));
    }
    return Promise.reject(error);
  }
);

export default api;

export const handleApiError = (error: unknown): string => {
  if (axios.isAxiosError(error)) {
    const apiError = error.response?.data as ApiError;
    return apiError?.message || error.message || 'An error occurred';
  }
  return 'An unexpected error occurred';
};