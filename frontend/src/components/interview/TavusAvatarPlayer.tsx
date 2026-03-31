import React, { useCallback, useEffect, useRef, useState } from 'react';
import type { LiveKitAvatarSessionConfig } from '@/services/interview.service';
import type { AvatarTransportMode } from '@/types/interview.types';

// ---------------------------------------------------------------------------
// Shared UI helpers
// ---------------------------------------------------------------------------

interface TransportBadgeProps {
  label: string;
  className: string;
  description: string;
}

const TransportBadge: React.FC<TransportBadgeProps> = ({ label, className, description }) => (
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

const LiveBadge: React.FC = () => (
  <div className="absolute top-4 right-4 flex items-center gap-2 bg-red-600 text-white px-3 py-1 rounded-full">
    <div className="w-2 h-2 bg-white rounded-full animate-pulse"></div>
    <span className="text-sm font-bold">LIVE</span>
  </div>
);

// ---------------------------------------------------------------------------
// Tavus iframe player
// ---------------------------------------------------------------------------

interface TavusIframePlayerProps {
  conversationUrl: string;
  currentText: string;
  className: string;
}

const TavusIframePlayer: React.FC<TavusIframePlayerProps> = ({
  conversationUrl,
  currentText,
  className,
}) => {
  const [isLoading, setIsLoading] = useState(true);

  return (
    <div className={`relative ${className}`}>
      <iframe
        src={conversationUrl}
        allow="camera; microphone; autoplay; display-capture; fullscreen"
        className="w-full h-full rounded-lg border-0"
        title="AI Interviewer"
        onLoad={() => setIsLoading(false)}
      />

      {isLoading && (
        <div className="absolute inset-0 bg-black bg-opacity-70 flex items-center justify-center rounded-lg">
          <div className="text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-white mx-auto mb-3"></div>
            <p className="text-white text-sm">Starting AI interviewer…</p>
          </div>
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
        label="TAVUS"
        className="bg-emerald-600"
        description="AI avatar powered by Tavus video AI with Claude interview intelligence."
      />
      <LiveBadge />
    </div>
  );
};

// ---------------------------------------------------------------------------
// Binary (server stream) fallback player
// ---------------------------------------------------------------------------

interface BinaryAvatarPlayerProps {
  binaryMessage: Blob | null;
  currentText: string;
  className: string;
}

const BinaryAvatarPlayer: React.FC<BinaryAvatarPlayerProps> = ({
  binaryMessage,
  currentText,
  className,
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
        label="SERVER"
        className="bg-slate-700"
        description="Using server-side avatar stream over interview websocket."
      />
      <LiveBadge />
    </div>
  );
};

// ---------------------------------------------------------------------------
// Root export
// ---------------------------------------------------------------------------

export interface TavusAvatarPlayerProps {
  binaryMessage: Blob | null;
  currentText: string;
  sessionConfig?: LiveKitAvatarSessionConfig | null;
  onTransportChange?: (mode: AvatarTransportMode) => void;
  className?: string;
}

export const TavusAvatarPlayer: React.FC<TavusAvatarPlayerProps> = ({
  binaryMessage,
  currentText,
  sessionConfig,
  onTransportChange,
  className = '',
}) => {
  const hasTavusUrl = Boolean(sessionConfig?.conversationUrl);
  const activeTransport: AvatarTransportMode = hasTavusUrl ? 'tavus' : 'server';

  const stableOnTransportChange = useCallback(
    (mode: AvatarTransportMode) => {
      if (onTransportChange) {
        onTransportChange(mode);
      }
    },
    [onTransportChange]
  );

  useEffect(() => {
    stableOnTransportChange(activeTransport);
  }, [activeTransport, stableOnTransportChange]);

  if (hasTavusUrl && sessionConfig) {
    return (
      <TavusIframePlayer
        conversationUrl={sessionConfig.conversationUrl}
        currentText={currentText}
        className={className}
      />
    );
  }

  return (
    <BinaryAvatarPlayer
      binaryMessage={binaryMessage}
      currentText={currentText}
      className={className}
    />
  );
};
