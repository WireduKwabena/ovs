import { createSlice, PayloadAction } from '@reduxjs/toolkit';
import { RootState } from '../app/store';

interface ErrorState {
  message: string | null;
  status: number | null;
}

const initialState: ErrorState = {
  message: null,
  status: null,
};

const errorSlice = createSlice({
  name: 'error',
  initialState,
  reducers: {
    setError: (state, action: PayloadAction<ErrorState>) => {
      state.message = action.payload.message;
      state.status = action.payload.status;
    },
    clearError: (state) => {
      state.message = null;
      state.status = null;
    },
  },
});

export const { setError, clearError } = errorSlice.actions;

export const selectError = (state: RootState) => state.error;

export default errorSlice.reducer;
