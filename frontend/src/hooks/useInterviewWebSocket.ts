import { useEffect, useRef, useCallback } from 'react';
import { useDispatch } from 'react-redux';
import {
  setWsConnected,
  setCurrentQuestion,
  setQuestionNumber,
  resolveFlag,
  setInterviewComplete,
  setProcessing,
  setError, // <--- Added setError
} from '../store/interviewSlice';
import {
  WebSocketMessage,
  QuestionAskedMessage,
  NextQuestionMessage,
  InterviewQuestionPayload,
} from '@/types/interview.types';

const MAX_RECONNECT_ATTEMPTS = 8;
const BASE_RECONNECT_DELAY_MS = 1000;
const MAX_RECONNECT_DELAY_MS = 15000;
const RECONNECT_JITTER_MS = 400;

export interface InterviewSocketConnectionEvent {
  event: 'connected' | 'error' | 'disconnected';
  details?: string;
  attempt?: number;
  maxAttempts?: number;
  delayMs?: number;
  recoveredAfterAttempts?: number;
}

interface UseInterviewWebSocketProps {
  wsUrl: string | null;
  onMessage?: (message: WebSocketMessage) => void;
  onBinaryMessage?: (data: Blob) => void;
  onConnectionEvent?: (payload: InterviewSocketConnectionEvent) => void;
  autoReconnectEnabled?: boolean;
}

export const useInterviewWebSocket = ({
  wsUrl,
  onMessage,
  onBinaryMessage,
  onConnectionEvent,
  autoReconnectEnabled = true,
}: UseInterviewWebSocketProps) => {
  const wsRef = useRef<WebSocket | null>(null);
  const connectFnRef = useRef<(() => void) | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const reconnectAttemptRef = useRef(0);
  const allowAutoReconnectRef = useRef(autoReconnectEnabled);
  const dispatch = useDispatch();

  const extractQuestionText = useCallback((question: InterviewQuestionPayload): string => {
    if (typeof question === 'string') {
      return question;
    }
    return question?.question || '';
  }, []);

  const extractQuestionNumber = useCallback(
    (
      message: QuestionAskedMessage | NextQuestionMessage
    ): number => {
      if (typeof message.question !== 'string' && message.question?.question_number) {
        return message.question.question_number;
      }
      return message.question_number || 0;
    },
    []
  );

  const handleWebSocketMessage = useCallback(
    (message: WebSocketMessage) => {
      if (onMessage) {
        onMessage(message);
      }
      switch (message.type) {
        case 'session_initialized':
          console.log('Session initialized:', message.session_id);
          dispatch(setError(null)); // Clear any previous errors on successful initialization
          break;

        case 'question_asked':
          {
            const questionText = extractQuestionText(message.question);
            const questionNumber = extractQuestionNumber(message);
            if (questionText) {
              dispatch(setCurrentQuestion(questionText));
            }
            if (questionNumber > 0) {
              dispatch(setQuestionNumber(questionNumber));
            }
          }
          dispatch(setProcessing(false));
          dispatch(setError(null)); // Clear errors on new question
          break;

        case 'next_question':
          {
            const questionText = extractQuestionText(message.question);
            const questionNumber = extractQuestionNumber(message);
            if (questionText) {
              dispatch(setCurrentQuestion(questionText));
            }
            if (questionNumber > 0) {
              dispatch(setQuestionNumber(questionNumber));
            }
          }
          dispatch(setProcessing(false));
          dispatch(setError(null)); // Clear errors on new question
          break;

        case 'flag_resolution':
          if (message.data?.resolved) {
            dispatch(resolveFlag(message.data.flag_id));
          }
          dispatch(setError(null)); // Clear errors on flag resolution
          break;

        case 'interview_complete':
          dispatch(setInterviewComplete());
          dispatch(setProcessing(false));
          dispatch(setError(null)); // Clear errors on interview completion
          break;

        case 'avatar_error':
          console.error('Avatar Error:', message.error);
          dispatch(setProcessing(false));
          dispatch(setError(message.error));
          break;

        case 'error':
          console.error('General Error:', message.message);
          dispatch(setProcessing(false));
          dispatch(setError(message.message));
          break;

        case 'captions':
          // Handled by TavusAvatarPlayer, but logged for diagnostics.
          console.log('Caption:', message.text);
          break;

        case 'avatar_stream_start':
          // Handled by TavusAvatarPlayer
          break;

        case 'avatar_stream_end':
          // Handled by TavusAvatarPlayer
          break;

        case 'pong':
          break;

        default:
          const unhandledMessage = message as { type?: string };
          console.warn(
            'Unhandled WebSocket message type:',
            unhandledMessage.type,
            unhandledMessage
          );
          // Optionally dispatch an error for unhandled types if that's considered an error state
          // dispatch(setError(`Unhandled WebSocket message type: ${unhandledMessage.type}`));
          break;
      }
    },
    [dispatch, extractQuestionNumber, extractQuestionText, onMessage]
  );

  const clearReconnectTimer = useCallback(() => {
    if (reconnectTimeoutRef.current !== null) {
      window.clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
  }, []);

  const resetReconnectState = useCallback(() => {
    reconnectAttemptRef.current = 0;
    clearReconnectTimer();
  }, [clearReconnectTimer]);

  const scheduleReconnect = useCallback(
    (details: string) => {
      if (!wsUrl || !allowAutoReconnectRef.current) {
        return;
      }
      if (reconnectTimeoutRef.current !== null) {
        return;
      }
      if (reconnectAttemptRef.current >= MAX_RECONNECT_ATTEMPTS) {
        dispatch(
          setError('Unable to reconnect interview socket automatically. Use "Reconnect Socket".')
        );
        return;
      }

      reconnectAttemptRef.current += 1;
      const attempt = reconnectAttemptRef.current;
      const exponentialDelay = Math.min(
        MAX_RECONNECT_DELAY_MS,
        BASE_RECONNECT_DELAY_MS * 2 ** (attempt - 1)
      );
      const jitter = Math.floor(Math.random() * RECONNECT_JITTER_MS);
      const delay = exponentialDelay + jitter;

      if (onConnectionEvent) {
        onConnectionEvent({
          event: 'disconnected',
          details,
          attempt,
          maxAttempts: MAX_RECONNECT_ATTEMPTS,
          delayMs: delay,
        });
      }

      reconnectTimeoutRef.current = window.setTimeout(() => {
        reconnectTimeoutRef.current = null;
        if (!allowAutoReconnectRef.current || !wsUrl) {
          return;
        }
        connectFnRef.current?.();
      }, delay);
    },
    [
      dispatch,
      onConnectionEvent,
      wsUrl,
    ]
  );

  const connect = useCallback(() => {
    if (!wsUrl) {
      return;
    }

    const existingSocket = wsRef.current;
    if (existingSocket && (existingSocket.readyState === WebSocket.OPEN || existingSocket.readyState === WebSocket.CONNECTING)) {
      dispatch(setWsConnected(false));
      wsRef.current = null;
      existingSocket.close(4001, 'reconnecting');
    }

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      if (wsRef.current !== ws) {
        return;
      }
      const recoveredAttempts = reconnectAttemptRef.current;
      resetReconnectState();
      console.log('WebSocket connected');
      dispatch(setWsConnected(true));
      dispatch(setError(null)); // Clear any errors on successful connection
      if (onConnectionEvent) {
        onConnectionEvent({
          event: 'connected',
          recoveredAfterAttempts: recoveredAttempts,
          details:
            recoveredAttempts > 0
              ? `recovered_after_${recoveredAttempts}_attempts`
              : undefined,
        });
      }
    };

    ws.onmessage = (event: MessageEvent) => {
      if (wsRef.current !== ws) {
        return;
      }
      if (event.data instanceof Blob) {
        if (onBinaryMessage) {
          onBinaryMessage(event.data);
        }
        return;
      }

      try {
        const message: WebSocketMessage = JSON.parse(event.data);
        handleWebSocketMessage(message);
      } catch (parseError: unknown) {
        console.error('Failed to parse message:', parseError);
        dispatch(
          setError(
            'Failed to parse WebSocket message: ' +
              (parseError instanceof Error ? parseError.message : 'unknown error')
          )
        );
      }
    };

    ws.onerror = (error) => {
      if (wsRef.current !== ws) {
        return;
      }
      console.error('WebSocket error:', error);
      dispatch(setError('WebSocket connection error.'));
      dispatch(setProcessing(false));
      dispatch(setWsConnected(false));
      if (onConnectionEvent) {
        onConnectionEvent({ event: 'error' });
      }
    };

    ws.onclose = (event) => {
      if (wsRef.current !== ws) {
        return;
      }
      console.log('WebSocket closed', event.code, event.reason);
      wsRef.current = null;
      dispatch(setWsConnected(false));
      // Set error only if the close was abnormal (e.g., not a normal shutdown)
      if (!event.wasClean) {
        dispatch(
          setError(
            `WebSocket connection closed unexpectedly. Code: ${event.code}, Reason: ${event.reason}`
          )
        );
      } else {
        dispatch(setError(null)); // Clear error if closed cleanly
      }
      dispatch(setProcessing(false));
      const closeDetails = `${event.code}:${event.reason}`;
      const shouldReconnect =
        allowAutoReconnectRef.current &&
        Boolean(wsUrl) &&
        event.code !== 1000;
      if (shouldReconnect) {
        scheduleReconnect(closeDetails);
      } else if (onConnectionEvent) {
        onConnectionEvent({ event: 'disconnected', details: closeDetails });
      }
    };
  }, [
    wsUrl,
    dispatch,
    handleWebSocketMessage,
    onBinaryMessage,
    onConnectionEvent,
    resetReconnectState,
    scheduleReconnect,
  ]);

  useEffect(() => {
    connectFnRef.current = connect;
    return () => {
      if (connectFnRef.current === connect) {
        connectFnRef.current = null;
      }
    };
  }, [connect]);

  const sendMessage = useCallback((message: Record<string, unknown>): boolean => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message));
      return true;
    }
    return false;
  }, []);

  const disconnect = useCallback(() => {
    allowAutoReconnectRef.current = false;
    resetReconnectState();
    const socket = wsRef.current;
    if (socket) {
      wsRef.current = null;
      socket.close();
    }
  }, [resetReconnectState]);

  const reconnect = useCallback(() => {
    allowAutoReconnectRef.current = true;
    resetReconnectState();
    connect();
  }, [connect, resetReconnectState]);

  useEffect(() => {
    allowAutoReconnectRef.current = autoReconnectEnabled;
    if (autoReconnectEnabled) {
      return;
    }

    resetReconnectState();
    const socket = wsRef.current;
    if (!socket) {
      return;
    }

    wsRef.current = null;
    socket.close(1000, 'auto_reconnect_disabled');
    dispatch(setWsConnected(false));
    dispatch(setProcessing(false));
    if (onConnectionEvent) {
      onConnectionEvent({
        event: 'disconnected',
        details: 'auto_reconnect_disabled',
      });
    }
  }, [autoReconnectEnabled, dispatch, onConnectionEvent, resetReconnectState]);

  useEffect(() => {
    if (!wsUrl) {
      allowAutoReconnectRef.current = false;
      resetReconnectState();
      return;
    }
    if (!autoReconnectEnabled) {
      return;
    }
    allowAutoReconnectRef.current = true;
    connect();
    return () => disconnect();
  }, [autoReconnectEnabled, connect, disconnect, resetReconnectState, wsUrl]);

  return {
    sendMessage,
    disconnect,
    reconnect,
  };
};
