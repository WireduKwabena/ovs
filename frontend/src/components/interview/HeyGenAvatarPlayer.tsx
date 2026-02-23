import React, { useCallback, useEffect, useRef, useState } from 'react';
import type { HeyGenAvatarSdkConfig } from '@/services/interview.service';
import type { AvatarTransportMode } from '@/types/interview.types';

type StreamingAvatarModule = typeof import('@heygen/streaming-avatar');
type StreamingAvatarInstance = InstanceType<StreamingAvatarModule['default']>;

interface HeyGenAvatarPlayerProps {
  binaryMessage: Blob | null;
  currentText: string;
  speakText?: string;
  sdkConfig?: HeyGenAvatarSdkConfig | null;
  onTransportChange?: (mode: AvatarTransportMode) => void;
  className?: string;
}

interface SdkAvatarPlayerProps {
  config: HeyGenAvatarSdkConfig;
  currentText: string;
  speakText?: string;
  className: string;
  onFatalError: () => void;
}

interface TransportBadgeProps {
  label: string;
  className: string;
  description: string;
}

const TransportBadge: React.FC<TransportBadgeProps> = ({ label, className, description }) => {
  return (
    <div
      className={`group absolute top-4 left-4 px-3 py-1 rounded-full text-xs font-bold text-white ${className}`}
      aria-label={`${label}: ${description}`}
      title={`${label}: ${description}`}
    >
      <span>{label}</span>
      <div className="pointer-events-none absolute left-0 top-9 z-20 hidden w-56 rounded-md bg-black/85 p-2 text-[11px] font-medium text-white shadow-lg group-hover:block">
        {description}
      </div>
    </div>
  );
};

const toAvatarQuality = (
  quality: string | undefined,
  avatarQuality: StreamingAvatarModule['AvatarQuality']
) => {
  if (quality === 'low') {
    return avatarQuality.Low;
  }
  if (quality === 'high') {
    return avatarQuality.High;
  }
  return avatarQuality.Medium;
};

const SdkAvatarPlayer: React.FC<SdkAvatarPlayerProps> = ({
  config,
  currentText,
  speakText = '',
  className,
  onFatalError,
}) => {
  const videoRef = useRef<HTMLVideoElement>(null);
  const avatarRef = useRef<StreamingAvatarInstance | null>(null);
  const avatarModuleRef = useRef<StreamingAvatarModule | null>(null);
  const readyRef = useRef(false);
  const lastSpokenTextRef = useRef('');
  const keepAliveIntervalRef = useRef<number | null>(null);
  const [isBuffering, setIsBuffering] = useState(true);
  const [sdkLoadError, setSdkLoadError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    let avatar: StreamingAvatarInstance | null = null;
    let avatarModule: StreamingAvatarModule | null = null;
    const videoElement = videoRef.current;
    avatarRef.current = null;
    avatarModuleRef.current = null;
    readyRef.current = false;
    setSdkLoadError(false);

    const handleStreamReady = (stream: MediaStream) => {
      if (cancelled) {
        return;
      }

      readyRef.current = true;
      setIsBuffering(false);

      if (videoElement) {
        videoElement.srcObject = stream;
        videoElement.play().catch(() => {
          // Autoplay can be blocked by browser policy.
        });
      }
    };

    const handleDisconnected = () => {
      if (cancelled) {
        return;
      }
      readyRef.current = false;
      setIsBuffering(false);
    };

    const startSession = async () => {
      try {
        const sdk = await import('@heygen/streaming-avatar');
        if (cancelled) {
          return;
        }

        avatarModule = sdk;
        avatarModuleRef.current = sdk;
        const avatarInstance = new sdk.default({ token: config.token });
        avatar = avatarInstance;
        avatarRef.current = avatarInstance;

        avatarInstance.on(sdk.StreamingEvents.STREAM_READY, handleStreamReady);
        avatarInstance.on(sdk.StreamingEvents.STREAM_DISCONNECTED, handleDisconnected);

        await avatarInstance.createStartAvatar({
          avatarName: config.avatarName,
          quality: toAvatarQuality(config.quality, sdk.AvatarQuality),
          language: config.language,
          activityIdleTimeout: config.activityIdleTimeout,
          voice: config.voiceId
            ? {
                voiceId: config.voiceId,
              }
            : undefined,
        });

        if (!cancelled) {
          keepAliveIntervalRef.current = window.setInterval(() => {
            void avatarInstance.keepAlive().catch(() => undefined);
          }, 60_000);
        }
      } catch (error) {
        console.error('Failed to initialize HeyGen SDK avatar session:', error);
        if (!cancelled) {
          setSdkLoadError(true);
          setIsBuffering(false);
          onFatalError();
        }
      }
    };

    void startSession();

    return () => {
      cancelled = true;
      readyRef.current = false;
      lastSpokenTextRef.current = '';

      if (avatar && avatarModule) {
        avatar.off(avatarModule.StreamingEvents.STREAM_READY, handleStreamReady);
        avatar.off(avatarModule.StreamingEvents.STREAM_DISCONNECTED, handleDisconnected);
      }

      if (keepAliveIntervalRef.current !== null) {
        window.clearInterval(keepAliveIntervalRef.current);
        keepAliveIntervalRef.current = null;
      }

      if (avatar) {
        void avatar.stopAvatar().catch(() => undefined);
      }
      avatarRef.current = null;
      avatarModuleRef.current = null;

      if (videoElement) {
        videoElement.pause();
        videoElement.srcObject = null;
      }
    };
  }, [
    config.activityIdleTimeout,
    config.avatarName,
    config.language,
    config.quality,
    config.token,
    config.voiceId,
    onFatalError,
  ]);

  useEffect(() => {
    if (!speakText.trim()) {
      lastSpokenTextRef.current = '';
      return;
    }
    if (!readyRef.current) {
      return;
    }
    if (lastSpokenTextRef.current === speakText) {
      return;
    }

    const avatar = avatarRef.current;
    const avatarModule = avatarModuleRef.current;
    if (!avatar) {
      return;
    }
    if (!avatarModule) {
      return;
    }

    let cancelled = false;
    const speak = async () => {
      try {
        lastSpokenTextRef.current = speakText;
        await avatar.speak({
          text: speakText,
          taskType: avatarModule.TaskType.REPEAT,
          taskMode: avatarModule.TaskMode.SYNC,
        });
      } catch (error) {
        if (!cancelled) {
          console.error('HeyGen SDK speak failed:', error);
        }
      }
    };

    void speak();

    return () => {
      cancelled = true;
    };
  }, [speakText]);

  return (
    <div className={`relative ${className}`}>
      <video
        ref={videoRef}
        autoPlay
        playsInline
        muted={false}
        className="w-full h-full object-cover rounded-lg"
      >
        <track kind="captions" />
      </video>

      {isBuffering && (
        <div className="absolute inset-0 bg-black bg-opacity-50 flex items-center justify-center">
          <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-white"></div>
        </div>
      )}
      {sdkLoadError && !isBuffering && (
        <div className="absolute inset-x-0 bottom-16 mx-4 rounded-md bg-red-600 px-3 py-2 text-center text-xs font-semibold text-white">
          SDK unavailable. Falling back to server stream.
        </div>
      )}

      {currentText && (
        <div
          className="absolute bottom-0 left-0 right-0 bg-black bg-opacity-75 text-white p-4"
          aria-live="polite"
        >
          <p className="text-center text-lg">{currentText}</p>
        </div>
      )}

      <TransportBadge
        label="SDK"
        className="bg-emerald-600"
        description="Client uses HeyGen Streaming Avatar SDK with LiveKit transport."
      />

      <div className="absolute top-4 right-4 flex items-center gap-2 bg-red-600 text-white px-3 py-1 rounded-full">
        <div className="w-2 h-2 bg-white rounded-full animate-pulse"></div>
        <span className="text-sm font-bold">LIVE</span>
      </div>
    </div>
  );
};

const BinaryAvatarPlayer: React.FC<
  Pick<HeyGenAvatarPlayerProps, 'binaryMessage' | 'currentText' | 'className'> & {
    transportLabel: string;
    transportBadgeClass: string;
    transportDescription: string;
  }
> = ({
  binaryMessage,
  currentText,
  className = '',
  transportLabel,
  transportBadgeClass,
  transportDescription,
}) => {
  const videoRef = useRef<HTMLVideoElement>(null);
  const mediaSourceRef = useRef<MediaSource | null>(null);
  const sourceBufferRef = useRef<SourceBuffer | null>(null);
  const videoUrlRef = useRef<string | null>(null);
  const pendingChunksRef = useRef<ArrayBuffer[]>([]);
  const [isBuffering, setIsBuffering] = useState(false);

  const appendNextChunk = () => {
    const sourceBuffer = sourceBufferRef.current;
    if (!sourceBuffer || sourceBuffer.updating) {
      return;
    }

    const nextChunk = pendingChunksRef.current.shift();
    if (!nextChunk) {
      setIsBuffering(false);
      return;
    }

    try {
      setIsBuffering(true);
      sourceBuffer.appendBuffer(nextChunk);
    } catch (error) {
      console.error('Error appending media chunk:', error);
      setIsBuffering(false);
    }
  };

  useEffect(() => {
    const mediaSource = new MediaSource();
    const videoElement = videoRef.current;
    mediaSourceRef.current = mediaSource;

    if (videoElement) {
      const objectUrl = URL.createObjectURL(mediaSource);
      videoUrlRef.current = objectUrl;
      videoElement.src = objectUrl;
    }

    let createdSourceBuffer: SourceBuffer | null = null;

    const onUpdateEnd = () => {
      appendNextChunk();
    };

    const onBufferError = (event: Event) => {
      console.error('Source buffer error:', event);
      setIsBuffering(false);
    };

    const onSourceOpen = () => {
      try {
        const sourceBuffer = mediaSource.addSourceBuffer(
          'video/mp4; codecs="avc1.42E01E, mp4a.40.2"'
        );
        createdSourceBuffer = sourceBuffer;
        sourceBufferRef.current = sourceBuffer;
        sourceBuffer.addEventListener('updateend', onUpdateEnd);
        sourceBuffer.addEventListener('error', onBufferError);
        appendNextChunk();
      } catch (e) {
        console.error('Error creating source buffer:', e);
      }
    };

    mediaSource.addEventListener('sourceopen', onSourceOpen);

    return () => {
      mediaSource.removeEventListener('sourceopen', onSourceOpen);
      if (createdSourceBuffer) {
        createdSourceBuffer.removeEventListener('updateend', onUpdateEnd);
        createdSourceBuffer.removeEventListener('error', onBufferError);
      }

      pendingChunksRef.current = [];
      setIsBuffering(false);

      const currentMediaSource = mediaSourceRef.current;
      if (
        currentMediaSource &&
        currentMediaSource.readyState === 'open' &&
        sourceBufferRef.current &&
        !sourceBufferRef.current.updating
      ) {
        try {
          currentMediaSource.endOfStream();
        } catch (error) {
          console.warn('Unable to end media stream cleanly:', error);
        }
      }

      sourceBufferRef.current = null;
      mediaSourceRef.current = null;

      if (videoElement) {
        videoElement.pause();
        videoElement.removeAttribute('src');
        videoElement.load();
      }

      if (videoUrlRef.current) {
        URL.revokeObjectURL(videoUrlRef.current);
        videoUrlRef.current = null;
      }
    };
  }, []);

  useEffect(() => {
    if (!binaryMessage) {
      return;
    }

    let cancelled = false;
    const queueIncomingChunk = async () => {
      try {
        const arrayBuffer = await binaryMessage.arrayBuffer();
        if (cancelled) {
          return;
        }

        pendingChunksRef.current.push(arrayBuffer);
        appendNextChunk();

        if (videoRef.current && videoRef.current.paused) {
          videoRef.current.play().catch(() => {
            // Autoplay can be blocked by browser policy.
          });
        }
      } catch (error) {
        console.error('Error queueing buffer:', error);
      }
    };

    void queueIncomingChunk();

    return () => {
      cancelled = true;
    };
  }, [binaryMessage]);

  return (
    <div className={`relative ${className}`}>
      <video
        ref={videoRef}
        autoPlay
        playsInline
        muted={false}
        className="w-full h-full object-cover rounded-lg"
      >
        <track kind="captions" />
      </video>

      {isBuffering && (
        <div className="absolute inset-0 bg-black bg-opacity-50 flex items-center justify-center">
          <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-white"></div>
        </div>
      )}

      {currentText && (
        <div
          className="absolute bottom-0 left-0 right-0 bg-black bg-opacity-75 text-white p-4"
          aria-live="polite"
        >
          <p className="text-center text-lg">{currentText}</p>
        </div>
      )}

      <TransportBadge
        label={transportLabel}
        className={transportBadgeClass}
        description={transportDescription}
      />

      <div className="absolute top-4 right-4 flex items-center gap-2 bg-red-600 text-white px-3 py-1 rounded-full">
        <div className="w-2 h-2 bg-white rounded-full animate-pulse"></div>
        <span className="text-sm font-bold">LIVE</span>
      </div>
    </div>
  );
};

export const HeyGenAvatarPlayer: React.FC<HeyGenAvatarPlayerProps> = ({
  binaryMessage,
  currentText,
  speakText,
  sdkConfig,
  onTransportChange,
  className = '',
}) => {
  const [failedSdkKey, setFailedSdkKey] = useState<string | null>(null);
  const hasSdkConfig = Boolean(sdkConfig?.token && sdkConfig?.avatarName);
  const sdkKey = hasSdkConfig && sdkConfig ? `${sdkConfig.avatarName}:${sdkConfig.token}` : null;
  const fallbackToBinary = Boolean(sdkKey && failedSdkKey === sdkKey);
  const activeTransport: AvatarTransportMode =
    hasSdkConfig && !fallbackToBinary ? 'sdk' : hasSdkConfig ? 'fallback' : 'server';
  const binaryTransportLabel = hasSdkConfig ? 'FALLBACK' : 'SERVER';
  const binaryTransportBadgeClass = hasSdkConfig ? 'bg-amber-600' : 'bg-slate-700';
  const binaryTransportDescription = hasSdkConfig
    ? 'SDK session failed. Streaming continues using server byte-stream fallback.'
    : 'Using server-side avatar stream over interview websocket.';
  const handleFatalError = useCallback(() => {
    if (!sdkKey) {
      return;
    }
    setFailedSdkKey(sdkKey);
  }, [sdkKey]);

  useEffect(() => {
    if (onTransportChange) {
      onTransportChange(activeTransport);
    }
  }, [activeTransport, onTransportChange]);

  if (hasSdkConfig && sdkConfig && !fallbackToBinary) {
    return (
      <SdkAvatarPlayer
        key={sdkKey}
        config={sdkConfig}
        currentText={currentText}
        speakText={speakText}
        className={className}
        onFatalError={handleFatalError}
      />
    );
  }

  return (
    <BinaryAvatarPlayer
      binaryMessage={binaryMessage}
      currentText={currentText}
      className={className}
      transportLabel={binaryTransportLabel}
      transportBadgeClass={binaryTransportBadgeClass}
      transportDescription={binaryTransportDescription}
    />
  );
};
