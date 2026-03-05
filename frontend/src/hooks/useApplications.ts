// src/hooks/useApplications.ts (New - Redux Wrapper)
import { useSelector, useDispatch } from 'react-redux';
import {
  fetchApplications,
  fetchCaseById,
  createApplication,
  updateApplication,
} from '../store/applicationSlice';
import type { FetchApplicationsOptions } from '../store/applicationSlice';
import type { AppDispatch, RootState } from '@/app/store';
import { useCallback } from 'react';
import { createSelector } from '@reduxjs/toolkit';

// ✅ Create memoized selector to prevent re-renders
const selectApplicationsState = (state: RootState) => state.applications;

const selectApplications = createSelector(
  [selectApplicationsState],
  (appState) => ({
    applications: Array.isArray(appState.applications) ? appState.applications : [],
    currentCase: appState.currentCase,
    loading: appState.loading,
    error: appState.error,
  })
);

export const useApplications = () => {
  const dispatch = useDispatch<AppDispatch>();
  const { applications, loading, error, currentCase } = useSelector(selectApplications);

  const refetch = useCallback((options?: FetchApplicationsOptions) => {
    dispatch(fetchApplications(options));
  }, [dispatch]);

  const loadApplication = useCallback(
    (caseId: string) => {
      dispatch(fetchCaseById(caseId));
    },
    [dispatch]
  );

  const create = useCallback(
    async (data: any) => {
      return await dispatch(createApplication(data)).unwrap();
    },
    [dispatch]
  );

  const update = useCallback(
    async (caseId: string, data: any) => {
      return await dispatch(updateApplication({ id: caseId, data })).unwrap();
    },
    [dispatch]
  );

  return {
    applications,
    currentCase,
    loading,
    error,
    loadApplication,
    createApplication: create,
    updateApplication: update,
    refetch,
  };
};

