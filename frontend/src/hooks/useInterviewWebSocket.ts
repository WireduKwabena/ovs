import { useEffect, useRef, useCallback } from 'react';
import { useDispatch } from 'react-redux';
import {
  setWsConnected,
  setCurrentQuestion,
  setQuestionNumber,
  resolveFlag,
  setInterviewComplete,
  setError, // <--- Added setError
} from '../store/interviewSlice';
import {
  WebSocketMessage,
  SessionInitializedMessage,
  QuestionAskedMessage,
  NextQuestionMessage,
  FlagResolutionMessage,
  AvatarErrorMessage,
  GeneralErrorMessage,
  CaptionsMessage,
} from '@/types/interview.types';

interface UseInterviewWebSocketProps {
  wsUrl: string | null;
  onMessage?: (message: WebSocketMessage) => void;
  onBinaryMessage?: (data: Blob) => void;
}

export const useInterviewWebSocket = ({
  wsUrl,
  onMessage,
  onBinaryMessage,
}: UseInterviewWebSocketProps) => {
  const wsRef = useRef<WebSocket | null>(null);
  const dispatch = useDispatch();

  const handleWebSocketMessage = useCallback(
    (message: WebSocketMessage) => {
      if (onMessage) {
        onMessage(message);
      }
      switch (message.type) {
        case 'session_initialized':
          const sessionInitializedMsg = message as SessionInitializedMessage;
          console.log('Session initialized:', sessionInitializedMsg.session_id);
          dispatch(setError(null)); // Clear any previous errors on successful initialization
          break;

        case 'question_asked':
          const questionAskedMsg = message as QuestionAskedMessage;
          dispatch(setCurrentQuestion(questionAskedMsg.question.question));
          dispatch(setQuestionNumber(questionAskedMsg.question_number));
          dispatch(setError(null)); // Clear errors on new question
          break;

        case 'next_question':
          const nextQuestionMsg = message as NextQuestionMessage;
          dispatch(setCurrentQuestion(nextQuestionMsg.question.question));
          dispatch(setQuestionNumber(nextQuestionMsg.question_number));
          dispatch(setError(null)); // Clear errors on new question
          break;

        case 'flag_resolution':
          const flagResolutionMsg = message as FlagResolutionMessage;
          if (flagResolutionMsg.data?.resolved) {
            dispatch(resolveFlag(flagResolutionMsg.data.flag_id));
          }
          dispatch(setError(null)); // Clear errors on flag resolution
          break;

        case 'interview_complete':
          dispatch(setInterviewComplete());
          dispatch(setError(null)); // Clear errors on interview completion
          break;

        case 'avatar_error':
          const avatarErrorMsg = message as AvatarErrorMessage;
          console.error('Avatar Error:', avatarErrorMsg.error);
          dispatch(setError(avatarErrorMsg.error));
          break;

        case 'error':
          const generalErrorMsg = message as GeneralErrorMessage;
          console.error('General Error:', generalErrorMsg.message);
          dispatch(setError(generalErrorMsg.message));
          break;

        case 'captions':
          // Handled by HeyGenAvatarPlayer, but ensures type safety if passed through onMessage
          const captionsMsg = message as CaptionsMessage;
          console.log('Caption:', captionsMsg.text);
          break;

        case 'avatar_stream_start':
          // Handled by HeyGenAvatarPlayer
          break;

        default:
          const unhandledMessage = message as any;
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
    [dispatch, onMessage]
  );

  const connect = useCallback(() => {
    if (!wsUrl) {
      dispatch(setError('WebSocket URL is not provided.'));
      return;
    }

    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      console.log('WebSocket connected');
      dispatch(setWsConnected(true));
      dispatch(setError(null)); // Clear any errors on successful connection
    };

    ws.onmessage = (event: MessageEvent) => {
      if (event.data instanceof Blob) {
        if (onBinaryMessage) {
          onBinaryMessage(event.data);
        }
        return;
      }

      try {
        const message: WebSocketMessage = JSON.parse(event.data);
        handleWebSocketMessage(message);
      } catch (e: unknown) {
        console.error('Failed to parse message:', e);
        dispatch(
          setError('Failed to parse WebSocket message: ' + (e as Error).message)
        );
      }
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      dispatch(setError('WebSocket connection error.'));
      dispatch(setWsConnected(false));
    };

    ws.onclose = (event) => {
      console.log('WebSocket closed', event.code, event.reason);
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
    };

    wsRef.current = ws;
  }, [wsUrl, dispatch, handleWebSocketMessage, onBinaryMessage]);

  const sendMessage = useCallback((message: Record<string, unknown>) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message));
    }
  }, []);

  const disconnect = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
  }, []);

  useEffect(() => {
    connect();
    return () => disconnect();
  }, [connect, disconnect]);

  return {
    sendMessage,
    disconnect,
  };
};