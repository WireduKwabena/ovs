// ============================================================================
// HeyGen Avatar Player Component
// Location: frontend/src/components/interview/HeyGenAvatarPlayer.tsx
// ============================================================================

import React, { useRef, useEffect, useState } from 'react';

interface HeyGenAvatarPlayerProps {
  binaryMessage: Blob | null;
  currentText: string;
  className?: string;
}

export const HeyGenAvatarPlayer: React.FC<HeyGenAvatarPlayerProps> = ({
  binaryMessage,
  currentText,
  className = '',
}) => {
  const videoRef = useRef<HTMLVideoElement>(null);
  const mediaSourceRef = useRef<MediaSource | null>(null);
  const sourceBufferRef = useRef<SourceBuffer | null>(null);
  const [isBuffering, setIsBuffering] = useState(false);

  useEffect(() => {
    const mediaSource = new MediaSource();
    mediaSourceRef.current = mediaSource;

    if (videoRef.current) {
      videoRef.current.src = URL.createObjectURL(mediaSource);
    }

    const onSourceOpen = () => {
      try {
        const sourceBuffer = mediaSource.addSourceBuffer(
          'video/mp4; codecs="avc1.42E01E, mp4a.40.2"'
        );
        sourceBufferRef.current = sourceBuffer;

        sourceBuffer.addEventListener('updateend', () => {
          setIsBuffering(false);
        });
      } catch (e) {
        console.error('Error creating source buffer:', e);
      }
    };

    mediaSource.addEventListener('sourceopen', onSourceOpen);

    return () => {
      mediaSource.removeEventListener('sourceopen', onSourceOpen);
      if (
        mediaSourceRef.current &&
        mediaSourceRef.current.readyState === 'open'
      ) {
        mediaSourceRef.current.endOfStream();
      }
    };
  }, []);

  useEffect(() => {
    if (binaryMessage && sourceBufferRef.current && !sourceBufferRef.current.updating) {
      const appendBuffer = async () => {
        try {
          const arrayBuffer = await binaryMessage.arrayBuffer();
          sourceBufferRef.current?.appendBuffer(arrayBuffer);
          setIsBuffering(true);

          if (videoRef.current && videoRef.current.paused) {
            videoRef.current.play().catch(() => {
              // Autoplay was prevented
            });
          }
        } catch (error) {
          console.error('Error appending buffer:', error);
        }
      };

      appendBuffer();
    }
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

      {/* Loading overlay */}
      {isBuffering && (
        <div className="absolute inset-0 bg-black bg-opacity-50 flex items-center justify-center">
          <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-white"></div>
        </div>
      )}

      {/* Live caption */}
      {currentText && (
        <div className="absolute bottom-0 left-0 right-0 bg-black bg-opacity-75 text-white p-4">
          <p className="text-center text-lg">{currentText}</p>
        </div>
      )}

      {/* Live indicator */}
      <div className="absolute top-4 right-4 flex items-center gap-2 bg-red-600 text-white px-3 py-1 rounded-full">
        <div className="w-2 h-2 bg-white rounded-full animate-pulse"></div>
        <span className="text-sm font-bold">LIVE</span>
      </div>
    </div>
  );
};