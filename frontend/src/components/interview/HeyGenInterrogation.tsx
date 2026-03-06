// ============================================================================
// Main Interview Component
// Location: frontend/src/components/interview/HeyGenInterrogation.tsx
// ============================================================================

import React, { useState, useRef, useEffect, useCallback } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { useNavigate } from 'react-router-dom';
import Webcam from 'react-webcam';
import RecordRTC from 'recordrtc';
import { HeyGenAvatarPlayer } from './HeyGenAvatarPlayer';
import { useInterviewWebSocket } from '../../hooks/useInterviewWebSocket';
import type { InterviewSocketConnectionEvent } from '../../hooks/useInterviewWebSocket';
import type { AppDispatch, RootState } from '../../app/store';

import {
  setSessionId,
  addFlag,
  setRecording,
  setProcessing,
  resetInterview,
} from '../../store/interviewSlice';
import type {
  AvatarTransportMode,
  InterrogationFlag,
  InterrogationFlagStatus,
  WebSocketMessage,
} from '../../types/interview.types';
import { interviewService } from '@/services/interview.service';
import type { HeyGenAvatarSdkConfig } from '@/services/interview.service';

interface HeyGenInterrogationProps {
  applicationId: string;
  completionRedirectPath?: string;
}

interface RecorderHandle {
  startRecording: () => void;
  stopRecording: (callback: () => void) => void;
  getBlob: () => Blob;
  destroy?: () => void;
}

interface SessionInitFlagPayload {
  id?: string | number;
  type?: string;
  severity?: string;
  status?: string;
  context?: string;
  description?: string;
}

const normalizeSeverity = (severity?: string): InterrogationFlag['severity'] => {
  if (severity === 'critical' || severity === 'high' || severity === 'medium') {
    return severity;
  }
  return 'low';
};

const normalizeStatus = (status?: string): InterrogationFlagStatus => {
  if (status === 'pending' || status === 'addressed' || status === 'resolved') {
    return status;
  }
  return 'unresolved';
};

export const HeyGenInterrogation: React.FC<HeyGenInterrogationProps> = ({
  applicationId,
  completionRedirectPath = '/dashboard',
}) => {
  const dispatch = useDispatch<AppDispatch>();
  const navigate = useNavigate();

  const {
    sessionId,
    currentQuestion,
    questionNumber,
    flags,
    isComplete,
    isRecording,
    isProcessing,
    wsConnected,
    error: interviewError,
  } = useSelector((state: RootState) => state.interview);

  const [websocketUrl, setWebsocketUrl] = useState<string | null>(null);
  const [localError, setLocalError] = useState<string | null>(null);
  const [binaryMessage, setBinaryMessage] = useState<Blob | null>(null);
  const [currentText, setCurrentText] = useState<string>('');
  const [avatarSpeechText, setAvatarSpeechText] = useState<string>('');
  const [avatarSdkConfig, setAvatarSdkConfig] = useState<HeyGenAvatarSdkConfig | null>(null);
  const [avatarTransportMode, setAvatarTransportMode] = useState<AvatarTransportMode>('server');
  const [lastWsEvent, setLastWsEvent] = useState<string>('idle');
  const [lastWsEventAt, setLastWsEventAt] = useState<string>('n/a');
  const [copiedDiagnostics, setCopiedDiagnostics] = useState(false);
  const [isReconnecting, setIsReconnecting] = useState(false);
  const [reconnectState, setReconnectState] = useState<{
    attempt: number;
    maxAttempts: number;
    delayMs: number;
  } | null>(null);

  const webcamRef = useRef<Webcam>(null);
  const recorderRef = useRef<RecorderHandle | null>(null);
  const effectiveError = localError || interviewError;

  const markWsEvent = useCallback((eventType: string) => {
    setLastWsEvent(eventType);
    setLastWsEventAt(new Date().toLocaleTimeString());
  }, []);

  const handleBinaryMessage = useCallback(
    (blob: Blob) => {
      setBinaryMessage(blob);
      markWsEvent('binary_chunk');
    },
    [markWsEvent]
  );

  const handleSocketMessage = useCallback(
    (message: WebSocketMessage) => {
      markWsEvent(message.type);
      if (message.type === 'avatar_stream_start') {
        setCurrentText(message.text || '');
        setAvatarSpeechText(message.text || '');
      } else if (message.type === 'avatar_stream_end') {
        setCurrentText('');
      }
    },
    [markWsEvent]
  );

  const handleSocketLifecycle = useCallback(
    (payload: InterviewSocketConnectionEvent) => {
      if (payload.event === 'connected') {
        setReconnectState(null);
        setIsReconnecting(false);
        if (payload.recoveredAfterAttempts && payload.recoveredAfterAttempts > 0) {
          markWsEvent(`ws_connected (recovered after ${payload.recoveredAfterAttempts})`);
          return;
        }
        markWsEvent('ws_connected');
        return;
      }

      if (payload.event === 'error') {
        markWsEvent('ws_error');
        return;
      }

      if (
        payload.attempt &&
        payload.maxAttempts &&
        typeof payload.delayMs === 'number'
      ) {
        setReconnectState({
          attempt: payload.attempt,
          maxAttempts: payload.maxAttempts,
          delayMs: payload.delayMs,
        });
        setIsReconnecting(true);
        markWsEvent(
          `${payload.details || 'ws_disconnected'}; retry ${payload.attempt}/${payload.maxAttempts} in ${payload.delayMs}ms`
        );
        return;
      }

      setReconnectState(null);
      setIsReconnecting(false);
      markWsEvent(
        payload.details ? `ws_disconnected (${payload.details})` : 'ws_disconnected'
      );
    },
    [markWsEvent]
  );

  const { sendMessage, reconnect } = useInterviewWebSocket({
    wsUrl: websocketUrl,
    onBinaryMessage: handleBinaryMessage,
    onMessage: handleSocketMessage,
    onConnectionEvent: handleSocketLifecycle,
    autoReconnectEnabled: !isComplete,
  });

  useEffect(() => {
    let mounted = true;

    const initialize = async () => {
      try {
        const data = await interviewService.startInterview(applicationId);

        if (!mounted) {
          return;
        }

        dispatch(setSessionId(data.session_id));
        data.interrogation_flags.forEach((flag: SessionInitFlagPayload, index: number) => {
          const normalizedFlag: InterrogationFlag = {
            id: String(flag.id ?? `flag-${index + 1}`),
            type: flag.type || 'consistency',
            severity: normalizeSeverity(flag.severity),
            context: flag.context || flag.description || 'Potential inconsistency detected.',
            status: normalizeStatus(flag.status),
          };
          dispatch(addFlag(normalizedFlag));
        });
        setWebsocketUrl(data.websocket_url);
        markWsEvent('session_bootstrap_ready');

        const avatarConfig = await interviewService.getAvatarSessionConfig(data.session_id);
        if (mounted) {
          setAvatarSdkConfig(avatarConfig);
        }
      } catch (initError) {
        console.error('Failed to initialize interview:', initError);
        if (mounted) {
          setLocalError('Failed to start interview. Please try again.');
        }
      }
    };

    void initialize();

    return () => {
      mounted = false;
      if (recorderRef.current && typeof recorderRef.current.destroy === 'function') {
        recorderRef.current.destroy();
      }
      recorderRef.current = null;
      setAvatarSpeechText('');
      setAvatarSdkConfig(null);
      setAvatarTransportMode('server');
      setLastWsEvent('idle');
      setLastWsEventAt('n/a');
      setReconnectState(null);
      setIsReconnecting(false);
      dispatch(resetInterview());
    };
  }, [applicationId, dispatch, markWsEvent]);

  

  const startRecording = () => {
    if (!wsConnected) {
      setLocalError('Connection is not ready. Please wait for reconnection.');
      return;
    }

    if (!webcamRef.current || !webcamRef.current.stream) {
      setLocalError('Camera not ready. Please refresh the page.');
      return;
    }

    setLocalError(null);
    const stream = webcamRef.current.stream;

    const recorder = new RecordRTC(stream, {
      type: 'video',
      mimeType: 'video/webm;codecs=vp9',
      videoBitsPerSecond: 2500000,
      frameRate: 30,
    }) as unknown as RecorderHandle;

    recorder.startRecording();
    recorderRef.current = recorder;
    dispatch(setRecording(true));
  };

  const stopRecording = () => {
    if (!recorderRef.current) return;

    dispatch(setRecording(false));
    dispatch(setProcessing(true));

    const recorder = recorderRef.current;
    recorder.stopRecording(async () => {
      const blob = recorder.getBlob();
      await submitResponse(blob);
      if (typeof recorder.destroy === 'function') {
        recorder.destroy();
      }
      recorderRef.current = null;
    });
  };

  const submitResponse = async (videoBlob: Blob) => {
    if (!sessionId) {
      dispatch(setProcessing(false));
      setLocalError('Interview session is not ready yet.');
      return;
    }

    try {
      setLocalError(null);
      let videoPath = '';
      try {
        const uploadResult = await interviewService.uploadResponse(sessionId, videoBlob);
        videoPath = uploadResult.video_path || '';
      } catch (uploadError) {
        console.warn('Upload endpoint unavailable. Continuing without stored video path.', uploadError);
      }

      // Extract audio for transcription
      const audioBase64 = await blobToBase64(await extractAudio(videoBlob));

      // Send completion message via WebSocket
      const wasSent = sendMessage({
        type: 'response_complete',
        video_path: videoPath,
        audio_data: audioBase64,
      });

      if (!wasSent) {
        dispatch(setProcessing(false));
        setLocalError('Connection lost before sending your response. Please retry.');
      }
    } catch (error) {
      console.error('Failed to submit response:', error);
      dispatch(setProcessing(false));
      setLocalError('Failed to submit response. Please try again.');
    }
  };

  const extractAudio = async (videoBlob: Blob): Promise<Blob> => {
    const AudioContextClass = (window.AudioContext || (window as any).webkitAudioContext) as
      | typeof AudioContext
      | undefined;

    if (!AudioContextClass) {
      console.warn('Web Audio API is unavailable. Sending video blob as transcription fallback.');
      return videoBlob;
    }

    let audioContext: AudioContext | null = null;

    try {
      const arrayBuffer = await videoBlob.arrayBuffer();
      audioContext = new AudioContextClass();
      const decodedBuffer = await audioContext.decodeAudioData(arrayBuffer.slice(0));

      const channels = decodedBuffer.numberOfChannels;
      const sampleRate = decodedBuffer.sampleRate;
      const samples = decodedBuffer.length;
      const channelData = Array.from({ length: channels }, (_, index) => decodedBuffer.getChannelData(index));

      const interleaved = new Float32Array(samples * channels);
      for (let sampleIndex = 0; sampleIndex < samples; sampleIndex += 1) {
        for (let channelIndex = 0; channelIndex < channels; channelIndex += 1) {
          interleaved[sampleIndex * channels + channelIndex] = channelData[channelIndex][sampleIndex] || 0;
        }
      }

      const bytesPerSample = 2;
      const blockAlign = channels * bytesPerSample;
      const byteRate = sampleRate * blockAlign;
      const dataSize = interleaved.length * bytesPerSample;
      const buffer = new ArrayBuffer(44 + dataSize);
      const view = new DataView(buffer);

      const writeString = (offset: number, value: string) => {
        for (let i = 0; i < value.length; i += 1) {
          view.setUint8(offset + i, value.charCodeAt(i));
        }
      };

      writeString(0, 'RIFF');
      view.setUint32(4, 36 + dataSize, true);
      writeString(8, 'WAVE');
      writeString(12, 'fmt ');
      view.setUint32(16, 16, true);
      view.setUint16(20, 1, true);
      view.setUint16(22, channels, true);
      view.setUint32(24, sampleRate, true);
      view.setUint32(28, byteRate, true);
      view.setUint16(32, blockAlign, true);
      view.setUint16(34, 16, true);
      writeString(36, 'data');
      view.setUint32(40, dataSize, true);

      let offset = 44;
      for (let i = 0; i < interleaved.length; i += 1) {
        const sample = Math.max(-1, Math.min(1, interleaved[i]));
        const pcm = sample < 0 ? sample * 0x8000 : sample * 0x7fff;
        view.setInt16(offset, pcm, true);
        offset += 2;
      }

      return new Blob([buffer], { type: 'audio/wav' });
    } catch (extractError) {
      console.warn('Audio extraction failed. Sending original video blob as fallback.', extractError);
      return videoBlob;
    } finally {
      if (audioContext) {
        try {
          await audioContext.close();
        } catch {
          // Ignore close failures.
        }
      }
    }
  };

  const blobToBase64 = (blob: Blob): Promise<string> => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onloadend = () => {
        const result = reader.result as string;
        resolve(result.split(',')[1]);
      };
      reader.onerror = reject;
      reader.readAsDataURL(blob);
    });
  };

  const transportModeLabel =
    avatarTransportMode === 'sdk'
      ? 'SDK'
      : avatarTransportMode === 'fallback'
      ? 'FALLBACK'
      : 'SERVER';
  const websocketStatus = !websocketUrl
    ? 'idle'
    : wsConnected
    ? 'connected'
    : reconnectState
    ? `reconnecting (${reconnectState.attempt}/${reconnectState.maxAttempts})`
    : 'disconnected';

  const copyDiagnostics = useCallback(async () => {
    const payload = {
      sessionId,
      transport: avatarTransportMode,
      websocketStatus,
      lastEvent: lastWsEvent,
      lastEventAt: lastWsEventAt,
      hasSdkConfig: Boolean(avatarSdkConfig),
      hasCurrentQuestion: Boolean(currentQuestion),
      questionNumber,
      isRecording,
      isProcessing,
      wsUrlPresent: Boolean(websocketUrl),
      reconnectState,
    };

    try {
      await navigator.clipboard.writeText(JSON.stringify(payload, null, 2));
      setCopiedDiagnostics(true);
      window.setTimeout(() => {
        setCopiedDiagnostics(false);
      }, 1800);
    } catch (error) {
      console.error('Failed to copy diagnostics:', error);
      setLocalError('Unable to copy diagnostics to clipboard.');
    }
  }, [
    sessionId,
    avatarTransportMode,
    websocketStatus,
    lastWsEvent,
    lastWsEventAt,
    avatarSdkConfig,
    currentQuestion,
    questionNumber,
    isRecording,
    isProcessing,
    websocketUrl,
    reconnectState,
  ]);

  const reconnectSocket = useCallback(() => {
    if (!websocketUrl) {
      setLocalError('WebSocket is not initialized yet.');
      return;
    }

    setLocalError(null);
    markWsEvent('ws_reconnect_requested');
    setReconnectState(null);
    setIsReconnecting(true);
    reconnect();
  }, [markWsEvent, reconnect, websocketUrl]);

  if (effectiveError) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-red-50">
        <div className="bg-white rounded-lg shadow-lg p-8 max-w-md">
          <h2 className="text-2xl font-bold text-red-600 mb-4">Error</h2>
          <p className="text-slate-800 mb-6">{effectiveError}</p>
          <button
            onClick={() => navigate(-1)}
            className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          >
            Go Back
          </button>
        </div>
      </div>
    );
  }

  if (isComplete) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-green-900 to-blue-900 flex items-center justify-center p-8">
        <div className="max-w-2xl w-full bg-white rounded-2xl shadow-2xl p-12 text-center">
          <div className="w-20 h-20 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-6">
            <svg
              className="w-12 h-12 text-green-600"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M5 13l4 4L19 7"
              />
            </svg>
          </div>
          <h1 className="text-4xl font-bold text-gray-900 mb-4">
            Interview Complete
          </h1>
          <p className="text-xl text-slate-700 mb-4">
            You answered {questionNumber} questions
          </p>
          <p className="text-slate-700 mb-8">
            All inconsistencies have been addressed. Your responses are being
            analyzed.
          </p>
          <button
            onClick={() => navigate(completionRedirectPath)}
            className="px-8 py-4 bg-blue-600 text-white rounded-xl font-semibold text-lg hover:bg-blue-700"
          >
            Continue
          </button>
        </div>
      </div>
    );
  }

  if (!sessionId) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-16 w-16 border-t-4 border-b-4 border-blue-600 mx-auto mb-4"></div>
          <p className="text-xl text-slate-700">Initializing interview...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-red-900 via-gray-900 to-black">
      {/* Warning Banner */}
      <div className="bg-yellow-600 text-white p-4 text-center font-semibold">
        ⚠️ LIVE AI INTERROGATION - All responses analyzed in real-time
      </div>

      <div className="max-w-7xl mx-auto p-8">
        <div className="grid lg:grid-cols-2 gap-8">
          {/* Left: AI Avatar */}
          <div className="space-y-4">
            <div className="bg-black rounded-2xl overflow-hidden shadow-2xl border-4 border-red-600">
              <div className="bg-red-600 text-white p-3 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-2xl">🛡️</span>
                  <span className="font-bold">AI INVESTIGATOR</span>
                </div>
                {wsConnected && (
                  <div className="flex items-center gap-2 bg-green-500 px-3 py-1 rounded-full">
                    <div className="w-2 h-2 bg-white rounded-full animate-pulse"></div>
                    <span className="text-sm font-bold">CONNECTED</span>
                  </div>
                )}
              </div>

              <HeyGenAvatarPlayer
                binaryMessage={binaryMessage}
                currentText={currentText}
                speakText={avatarSpeechText}
                sdkConfig={avatarSdkConfig}
                onTransportChange={setAvatarTransportMode}
                className="h-96"
              />
            </div>

            <div className="bg-gray-900 text-gray-100 rounded-xl p-4 border border-gray-700">
              <div className="text-xs uppercase tracking-wide text-slate-700 mb-3">Runtime Diagnostics</div>
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div className="rounded-md bg-gray-800 px-3 py-2">
                  <div className="text-slate-700 text-xs mb-1">Avatar Transport</div>
                  <div className="font-mono font-semibold">{transportModeLabel}</div>
                </div>
                <div className="rounded-md bg-gray-800 px-3 py-2">
                  <div className="text-slate-700 text-xs mb-1">WebSocket</div>
                  <div className="font-mono font-semibold">{websocketStatus}</div>
                </div>
                <div className="rounded-md bg-gray-800 px-3 py-2 col-span-2">
                  <div className="text-slate-700 text-xs mb-1">Last Event</div>
                  <div className="font-mono break-all">{lastWsEvent}</div>
                </div>
                <div className="rounded-md bg-gray-800 px-3 py-2 col-span-2">
                  <div className="text-slate-700 text-xs mb-1">Updated</div>
                  <div className="font-mono">{lastWsEventAt}</div>
                </div>
                <div className="rounded-md bg-gray-800 px-3 py-2 col-span-2">
                  <div className="text-slate-700 text-xs mb-1">Reconnect State</div>
                  <div className="font-mono">
                    {reconnectState
                      ? `${reconnectState.attempt}/${reconnectState.maxAttempts} in ${reconnectState.delayMs}ms`
                      : 'none'}
                  </div>
                </div>
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={copyDiagnostics}
                  className="px-3 py-1.5 rounded-md bg-gray-700 hover:bg-gray-600 text-xs font-semibold"
                >
                  {copiedDiagnostics ? 'Copied' : 'Copy Diagnostics'}
                </button>
                <button
                  type="button"
                  onClick={reconnectSocket}
                  disabled={!websocketUrl || isReconnecting}
                  className="px-3 py-1.5 rounded-md bg-blue-700 hover:bg-blue-600 disabled:opacity-60 disabled:cursor-not-allowed text-xs font-semibold"
                >
                  {isReconnecting ? 'Reconnecting...' : 'Reconnect Socket'}
                </button>
              </div>
            </div>

            {/* Current Question */}
            <div className="bg-white rounded-xl shadow-2xl p-6">
              <div className="flex items-start gap-4">
                <div className="flex-shrink-0 w-10 h-10 bg-red-600 text-white rounded-full flex items-center justify-center font-bold">
                  {questionNumber}
                </div>
                <div className="flex-1">
                  <div className="text-sm text-slate-700 mb-2 uppercase font-semibold">
                    Current Question
                  </div>
                  <p className="text-xl font-bold text-gray-900">
                    {currentQuestion || 'Waiting for connection...'}
                  </p>
                </div>
              </div>
            </div>

            {/* Flags Status */}
            <div className="bg-gray-800 text-white rounded-xl p-6 max-h-96 overflow-y-auto">
              <h3 className="font-bold text-lg mb-4">
                Inconsistencies Being Addressed
              </h3>

              <div className="space-y-3">
                {flags
                  .filter((f) => f.status !== 'resolved')
                  .map((_flag, index) => (
                    <div key={index} className="p-3 bg-gray-700 rounded-lg">
                      <div className="flex justify-between items-start mb-2">
                        <span className="text-sm font-medium">
                          {_flag.context}
                        </span>
                        <span
                          className={`text-xs font-bold px-2 py-1 rounded ${
                            _flag.severity === 'critical'
                              ? 'bg-red-600'
                              : _flag.severity === 'high'
                              ? 'bg-orange-600'
                              : _flag.severity === 'medium'
                              ? 'bg-yellow-600'
                              : 'bg-blue-600'
                          }`}
                        >
                          {_flag.severity.toUpperCase()}
                        </span>
                      </div>
                    </div>
                  ))}

                {flags
                  .filter((f) => f.status === 'resolved')
                  .map((_flag, index) => (
                    <div
                      key={index}
                      className="p-3 bg-green-900 bg-opacity-50 rounded-lg"
                    >
                      <div className="flex justify-between items-center">
                        <span className="text-sm line-through opacity-60">
                          Resolved
                        </span>
                        <span className="text-green-400 text-sm font-bold">
                          ✓
                        </span>
                      </div>
                    </div>
                  ))}
              </div>
            </div>
          </div>

          {/* Right: Your Video */}
          <div className="space-y-4">
            <div className="bg-black rounded-2xl overflow-hidden shadow-2xl border-4 border-blue-600">
              <div className="bg-blue-600 text-white p-3 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-2xl">🎥</span>
                  <span className="font-bold">YOUR VIDEO</span>
                </div>
                {isRecording && (
                  <div className="flex items-center gap-2 bg-red-600 px-3 py-1 rounded-full animate-pulse">
                    <div className="w-2 h-2 bg-white rounded-full"></div>
                    <span className="text-sm font-bold">RECORDING</span>
                  </div>
                )}
              </div>

              <Webcam
                ref={webcamRef}
                audio={true}
                mirrored={true}
                className="w-full h-96 object-cover"
              />
            </div>

            {/* Controls */}
            <div className="flex justify-center gap-4">
              {!isRecording && !isProcessing ? (
                <button
                  onClick={startRecording}
                  disabled={!currentQuestion || !wsConnected}
                  className="flex items-center gap-3 px-10 py-5 bg-gradient-to-r from-green-600 to-blue-600 text-white rounded-2xl font-bold text-xl hover:from-green-700 hover:to-blue-700 disabled:opacity-50 disabled:cursor-not-allowed shadow-2xl"
                >
                  <span className="text-2xl">🎤</span>
                  Start Speaking
                </button>
              ) : isRecording ? (
                <button
                  onClick={stopRecording}
                  className="flex items-center gap-3 px-10 py-5 bg-gradient-to-r from-red-600 to-pink-600 text-white rounded-2xl font-bold text-xl hover:from-red-700 hover:to-pink-700 shadow-2xl"
                >
                  <span className="text-2xl">⏹️</span>
                  Stop & Submit
                </button>
              ) : (
                <div className="flex items-center gap-3 px-10 py-5 bg-gray-700 text-white rounded-2xl font-bold text-xl">
                  <div className="animate-spin rounded-full h-6 w-6 border-t-2 border-b-2 border-white"></div>
                  Analyzing...
                </div>
              )}
            </div>

            {/* Instructions */}
            <div className="bg-gray-800 rounded-xl p-6 text-white">
              <h3 className="font-bold mb-3">⚠️ Interview Guidelines</h3>
              <ul className="space-y-2 text-sm">
                <li>1. Listen to the AI investigator&apos;s questions carefully</li>
                <li>2. Click &quot;Start Speaking&quot; when ready to answer</li>
                <li>3. Maintain eye contact with the camera</li>
                <li>
                  4. Be honest - all answers are cross-referenced with documents
                </li>
                <li>
                  5. Your facial expressions and body language are being
                  analyzed
                </li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};


