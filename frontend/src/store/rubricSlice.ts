// src/store/rubricSlice.ts
import { createSlice, createAsyncThunk, type PayloadAction } from '@reduxjs/toolkit';
import { rubricService } from '../services/rubric.service';
import type { VettingRubric, ApiError, CreateRubricData } from '../types';

interface RubricState {
  rubrics: VettingRubric[];
  loading: boolean;
  error: ApiError | null;
}

const initialState: RubricState = {
  rubrics: [],
  loading: false,
  error: null,
};

export const fetchRubrics = createAsyncThunk<VettingRubric[], { status?: string }, { rejectValue: ApiError }>(
  'rubrics/fetchAll',
  async (params, { rejectWithValue }) => {
    try {
      return await rubricService.getAll(params);
    } catch (error: any) {
      return rejectWithValue(error.response?.data || { message: 'Failed to fetch rubrics' });
    }
  }
);

export const createRubric = createAsyncThunk<VettingRubric, CreateRubricData, { rejectValue: ApiError }>(
  'rubrics/create',
  async (data, { rejectWithValue }) => {
    try {
      return await rubricService.create(data);
    } catch (error: any) {
      return rejectWithValue(error.response?.data || { message: 'Creation failed' });
    }
  }
);

const rubricSlice = createSlice({
  name: 'rubrics',
  initialState,
  reducers: {
    clearError: (state) => { 
      state.error = null; 
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchRubrics.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(fetchRubrics.fulfilled, (state, action: PayloadAction<VettingRubric[]>) => {
        state.rubrics = action.payload;
        state.loading = false;
      })
      .addCase(fetchRubrics.rejected, (state, action) => {
        state.loading = false;
        state.error = action.payload as ApiError || { message: 'Fetch failed' };
      })
      .addCase(createRubric.fulfilled, (state, action: PayloadAction<VettingRubric>) => {
        state.rubrics.unshift(action.payload);  // Optimistic add to top
        state.loading = false;
      })
      .addCase(createRubric.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(createRubric.rejected, (state, action) => {
        state.loading = false;
        state.error = action.payload as ApiError || { message: 'Creation failed' };
      });
  },
});

export const { clearError } = rubricSlice.actions;
export default rubricSlice.reducer;