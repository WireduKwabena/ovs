// ============================================================================
// Redux Slice
// Location: frontend/src/store/slices/interviewSlice.ts
// ============================================================================

import { InterrogationFlag, InterrogationFlagStatus, InterviewState } from '@/types/interview.types';
import { createSlice, PayloadAction } from '@reduxjs/toolkit';

const initialState: InterviewState = {
  sessionId: null,
  currentQuestion: null,
  questionNumber: 0,
  flags: [],
  resolvedFlags: [],
  isComplete: false,
  isRecording: false,
  isProcessing: false,
  wsConnected: false,
  error: null,
};

const interviewSlice = createSlice({
  name: 'interview',
  initialState,
  reducers: {
    setSessionId: (state, action: PayloadAction<string>) => {
      state.sessionId = action.payload;
      state.error = null; // Clear error on successful session init
    },
    setCurrentQuestion: (state, action: PayloadAction<string>) => {
      state.currentQuestion = action.payload;
      state.error = null; // Clear error on new question
    },
    setQuestionNumber: (state, action: PayloadAction<number>) => {
      state.questionNumber = action.payload;
    },
    addFlag: (state, action: PayloadAction<InterrogationFlag>) => {
      state.flags.push(action.payload);
    },
    updateFlagStatus: (
      state,
      action: PayloadAction<{ id: string; status: InterrogationFlagStatus }>
    ) => {
      const flag = state.flags.find((f) => f.id === action.payload.id);
      if (flag) {
        flag.status = action.payload.status;
      }
    },
    resolveFlag: (state, action: PayloadAction<string>) => {
      const flag = state.flags.find((f) => f.id === action.payload);
      if (flag) {
        flag.status = 'resolved';
        state.resolvedFlags.push(action.payload);
      }
    },
    setInterviewComplete: (state) => {
      state.isComplete = true;
      state.isRecording = false;
      state.isProcessing = false;
      state.error = null; // Clear error on completion
    },
    setRecording: (state, action: PayloadAction<boolean>) => {
      state.isRecording = action.payload;
    },
    setProcessing: (state, action: PayloadAction<boolean>) => {
      state.isProcessing = action.payload;
    },
    setWsConnected: (state, action: PayloadAction<boolean>) => {
      state.wsConnected = action.payload;
    },
    setError: (state, action: PayloadAction<string | null>) => {
      state.error = action.payload;
    },
    resetInterview: () => initialState,
  },
});

export const {
  setSessionId,
  setCurrentQuestion,
  setQuestionNumber,
  addFlag,
  updateFlagStatus,
  resolveFlag,
  setInterviewComplete,
  setRecording,
  setProcessing,
  setWsConnected,
  setError,
  resetInterview,
} = interviewSlice.actions;

export default interviewSlice.reducer;