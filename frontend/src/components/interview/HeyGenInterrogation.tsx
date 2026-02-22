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

import {
  setSessionId,
  addFlag,
  setRecording,
  setProcessing,
  resetInterview,
} from '../../store/interviewSlice';
import { RootState } from '../../app/store';
import { InterrogationFlag } from '../../types/interview.types';
import { interviewService } from '@/services/interview.service';

interface HeyGenInterrogationProps {
  applicationId: string;
}

export const HeyGenInterrogation: React.FC<HeyGenInterrogationProps> = ({
  applicationId,
}) => {
  const dispatch = useDispatch();
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
  } = useSelector((state: RootState) => state.interview);

  const [websocketUrl, setWebsocketUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [binaryMessage, setBinaryMessage] = useState<Blob | null>(null);
  const [currentText, setCurrentText] = useState<string>('');

  const webcamRef = useRef<Webcam>(null);
  // TODO: Fix this any type
  const recorderRef = useRef<any | null>(null);

  const initializeInterview = useCallback(async () => {
    try {
      const data = await interviewService.startInterview(applicationId);

      dispatch(setSessionId(data.session_id));

      // Set flags
      data.interrogation_flags.forEach((flag: InterrogationFlag) => {
        dispatch(addFlag(flag));
      });

      // Set WebSocket URL
      setWebsocketUrl(data.websocket_url);
    } catch (error) {
      console.error('Failed to initialize interview:', error);
      setError('Failed to start interview. Please try again.');
    }
  }, [applicationId, dispatch]);

  const { sendMessage } = useInterviewWebSocket({
    wsUrl: websocketUrl,
    onBinaryMessage: setBinaryMessage,
    onMessage: (message: any) => { // TODO: Fix this any type
      if (message.type === 'avatar_stream_start') {
        setCurrentText(message.text);
      } else if (message.type === 'avatar_stream_end') {
        setCurrentText('');
      }
    },
  });

  useEffect(() => {
    initializeInterview();

    return () => {
      dispatch(resetInterview());
    };
  }, [dispatch, initializeInterview]);

  

  const startRecording = () => {
    if (!webcamRef.current || !webcamRef.current.stream) {
      alert('Camera not ready. Please refresh the page.');
      return;
    }

    const stream = webcamRef.current.stream;

    const recorder = new RecordRTC(stream, {
      type: 'video',
      mimeType: 'video/webm;codecs=vp9',
      videoBitsPerSecond: 2500000,
      frameRate: 30,
    });

    recorder.startRecording();
    recorderRef.current = recorder;
    dispatch(setRecording(true));
  };

  const stopRecording = async () => {
    if (!recorderRef.current) return;

    dispatch(setRecording(false));
    dispatch(setProcessing(true));

    recorderRef.current.stopRecording(async () => {
      const blob = recorderRef.current!.getBlob();
      await submitResponse(blob);
    });
  };

  const submitResponse = async (videoBlob: Blob) => {
    try {
      // Upload video to Django
      const { video_path } = await interviewService.uploadResponse(
        sessionId!,
        videoBlob
      );

      // Extract audio for transcription
      const audioBase64 = await blobToBase64(await extractAudio());

      // Send completion message via WebSocket
      sendMessage({
        type: 'response_complete',
        video_path: video_path,
        audio_data: audioBase64,
      });
    } catch (error) {
      console.error('Failed to submit response:', error);
      dispatch(setProcessing(false));
      setError('Failed to submit response. Please try again.');
    }
  };

  const extractAudio = async (): Promise<Blob> => {
    // TODO: Implement proper audio extraction from the video blob.
    // The current implementation is a placeholder and returns an empty audio blob.
    console.warn(
      'Audio extraction is not fully implemented. Using a placeholder.'
    );
    return new Blob([], { type: 'audio/wav' });
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

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-red-50">
        <div className="bg-white rounded-lg shadow-lg p-8 max-w-md">
          <h2 className="text-2xl font-bold text-red-600 mb-4">Error</h2>
          <p className="text-gray-700 mb-6">{error}</p>
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
          <p className="text-xl text-gray-600 mb-4">
            You answered {questionNumber} questions
          </p>
          <p className="text-gray-700 mb-8">
            All inconsistencies have been addressed. Your responses are being
            analyzed.
          </p>
          <button
            onClick={() => navigate('/dashboard')}
            className="px-8 py-4 bg-blue-600 text-white rounded-xl font-semibold text-lg hover:bg-blue-700"
          >
            Return to Dashboard
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
          <p className="text-xl text-gray-700">Initializing interview...</p>
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
                className="h-96"
              />
            </div>

            {/* Current Question */}
            <div className="bg-white rounded-xl shadow-2xl p-6">
              <div className="flex items-start gap-4">
                <div className="flex-shrink-0 w-10 h-10 bg-red-600 text-white rounded-full flex items-center justify-center font-bold">
                  {questionNumber}
                </div>
                <div className="flex-1">
                  <div className="text-sm text-gray-600 mb-2 uppercase font-semibold">
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
                  disabled={!currentQuestion}
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