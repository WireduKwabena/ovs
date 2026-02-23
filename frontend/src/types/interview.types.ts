// ============================================================================
// Types & Interfaces
// Location: frontend/src/types/interview.types.ts
// ============================================================================

export type InterrogationFlagStatus =
  | 'pending'
  | 'addressed'
  | 'resolved'
  | 'unresolved';

export type AvatarTransportMode = 'sdk' | 'fallback' | 'server';

export interface InterrogationFlag {
  id: string;
  type: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  context: string;
  status: InterrogationFlagStatus;
  data_point?: string;
}

export interface InterviewQuestion {
  question: string;
  question_number: number;
  intent: string;
  reasoning?: string;
  target_flag_id?: string;
}

export type InterviewQuestionPayload = InterviewQuestion | string;

export type WebSocketMessage =
  | SessionInitializedMessage
  | QuestionAskedMessage
  | NextQuestionMessage
  | FlagResolutionMessage
  | InterviewCompleteMessage
  | AvatarErrorMessage
  | GeneralErrorMessage
  | AvatarStreamStartMessage
  | AvatarStreamEndMessage
  | CaptionsMessage
  | PongMessage;

export interface SessionInitializedMessage {
  type: 'session_initialized';
  session_id: string;
}

export interface QuestionAskedMessage {
  type: 'question_asked';
  question: InterviewQuestionPayload;
  question_number?: number;
}

export interface NextQuestionMessage {
  type: 'next_question';
  question: InterviewQuestionPayload;
  question_number?: number;
}

export interface FlagResolutionMessage {
  type: 'flag_resolution';
  data: {
    resolved: boolean;
    flag_id: string;
  };
}

export interface InterviewCompleteMessage {
  type: 'interview_complete';
}

export interface AvatarErrorMessage {
  type: 'avatar_error';
  error: string;
}

export interface GeneralErrorMessage {
  type: 'error';
  message: string;
}

export interface AvatarStreamStartMessage {
  type: 'avatar_stream_start';
  text?: string;
}

export interface AvatarStreamEndMessage {
  type: 'avatar_stream_end';
}

export interface CaptionsMessage {
  type: 'captions';
  text: string;
}

export interface PongMessage {
  type: 'pong';
}

export interface NonVerbalData {
  deception_score: number;
  confidence_score: number;
  stress_level: number;
  eye_contact_percentage: number;
  average_emotion: string;
  behavioral_red_flags: string[];
}

export interface InterviewState {
  sessionId: string | null;
  currentQuestion: string | null;
  questionNumber: number;
  flags: InterrogationFlag[];
  resolvedFlags: string[];
  isComplete: boolean;
  isRecording: boolean;
  isProcessing: boolean;
  wsConnected: boolean;
  error: string | null;
}
