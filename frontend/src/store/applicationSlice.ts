// src/store/applicationSlice.ts (Updated - Adds uploadDocument Thunk)
import { createSlice, createAsyncThunk, type PayloadAction, type Action } from '@reduxjs/toolkit';
import { applicationService } from '../services/application.service';
import type { VettingCase, CreateApplicationData, ApplicationWithDocuments, ApiError, Document } from '../types';

interface ApplicationState {
  applications: ApplicationWithDocuments[];
  currentCase: ApplicationWithDocuments | null;
  loading: boolean;
  error: ApiError | null;
}

export interface FetchApplicationsOptions {
  scope?: 'all' | 'assigned' | 'mine';
}

const initialState: ApplicationState = {
  applications: [],
  currentCase: null,
  loading: false,
  error: null,
};

// Async Thunks
export const fetchApplications = createAsyncThunk<
  ApplicationWithDocuments[],
  FetchApplicationsOptions | void,
  { rejectValue: ApiError }
>(
  'applications/fetchAll',
  async (options, { rejectWithValue }) => {
    try {
      return await applicationService.getAll(options || undefined);
    } catch (error: any) {
      return rejectWithValue(error.response?.data || { message: 'Failed to fetch' });
    }
  }
);

export const createApplication = createAsyncThunk<VettingCase, CreateApplicationData, { rejectValue: ApiError }>(
  'applications/create',
  async (data, { rejectWithValue }) => {
    try {
      return await applicationService.create(data);
    } catch (error: any) {
      return rejectWithValue(error.response?.data || { message: 'Creation failed' });
    }
  }
);

export const fetchCaseById = createAsyncThunk<ApplicationWithDocuments, string, { rejectValue: ApiError }>(
  'applications/fetchById',
  async (caseId, { rejectWithValue }) => {
    try {
      return await applicationService.getById(caseId);
    } catch (error: any) {
      return rejectWithValue(error.response?.data || { message: 'Fetch failed' });
    }
  }
);

export const updateApplication = createAsyncThunk<VettingCase, { id: string; data: Partial<VettingCase> }, { rejectValue: ApiError }>(
  'applications/update',
  async ({ id, data }, { rejectWithValue }) => {
    try {
      return await applicationService.update(id.toString(), data);
    } catch (error: any) {
      return rejectWithValue(error.response?.data || { message: 'Update failed' });
    }
  }
);

// New: uploadDocument Thunk (For FileUpload.tsx)
export const uploadDocument = createAsyncThunk<{ document: Document; message?: string }, { caseId: string; file: File; documentType: string }, { rejectValue: ApiError }>(
  'applications/uploadDocument',
  async ({ caseId, file, documentType }, { rejectWithValue }) => {
    try {
      return await applicationService.uploadDocument(caseId, file, documentType);
    } catch (error: any) {
      return rejectWithValue(error.response?.data || { message: 'Upload failed' });
    }
  }
);

const applicationSlice = createSlice({
  name: 'applications',
  initialState,
  reducers: {
    setCurrentCase: (state, action: PayloadAction<ApplicationWithDocuments | null>) => {
      state.currentCase = action.payload;
    },
    clearError: (state) => { 
      state.error = null; 
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchApplications.fulfilled, (state, action: PayloadAction<ApplicationWithDocuments[]>) => {
        state.applications = Array.isArray(action.payload) ? action.payload : [];
        state.loading = false;
        console.log('✅ Applications stored:', state.applications.length);
      })
      .addCase(fetchApplications.rejected, (state, action) => {
        state.loading = false;
        state.error = action.payload as ApiError;
        state.applications = []; // ✅ Reset to empty array on error
      })
      .addCase(createApplication.fulfilled, (state, action: PayloadAction<VettingCase>) => {
        state.applications.push(action.payload as ApplicationWithDocuments);
        state.loading = false;
      })
      .addCase(fetchCaseById.fulfilled, (state, action: PayloadAction<ApplicationWithDocuments>) => {
        state.currentCase = action.payload;
        state.loading = false;
      })
      .addCase(updateApplication.fulfilled, (state, action: PayloadAction<VettingCase>) => {
        state.applications = state.applications.map(app => 
          app.id === action.payload.id ? action.payload as ApplicationWithDocuments : app
        );
        if (state.currentCase && state.currentCase.id === action.payload.id) {
          state.currentCase = { ...state.currentCase, ...action.payload };  // Merge updates
        }
        state.loading = false;
      })
      // New: uploadDocument Cases
      .addCase(uploadDocument.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(uploadDocument.fulfilled, (state, action: PayloadAction<{ document: Document; message?: string }>) => {
        // Optimistic: Add to currentCase documents if available
        if (state.currentCase) {
          state.currentCase.documents.push(action.payload.document);
        }
        state.loading = false;
      })
      .addCase(uploadDocument.rejected, (state, action) => {
        state.loading = false;
        state.error = action.payload as ApiError || { message: 'Upload failed' };
      })
      .addMatcher(
        (action: Action) => action.type.endsWith('/pending') && !action.type.includes('uploadDocument'),  // Exclude upload for per-file loading
        (state) => {
          state.loading = true;
          state.error = null;
        }
      )
      .addMatcher(
        (action: Action) => action.type.endsWith('/rejected') && !action.type.includes('uploadDocument'),
        (state, action: PayloadAction<ApiError>) => {
          state.loading = false;
          if (action.payload && typeof action.payload === 'object') {
            state.error = action.payload as ApiError;
          } else {
            state.error = { message: 'An error occurred' };
          }
        }
      );
  },
});

export const { setCurrentCase, clearError } = applicationSlice.actions;
export default applicationSlice.reducer;
