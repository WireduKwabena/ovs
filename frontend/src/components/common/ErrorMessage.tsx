// src/components/common/ErrorMessage.tsx

import { AlertCircle } from 'lucide-react';

interface ErrorMessageProps {
  error: string | Error | null | undefined;
  onRetry?: () => void;
}

export default function ErrorMessage({ error, onRetry }: ErrorMessageProps) {
  if (!error) return null;

  const message = typeof error === 'string'
    ? error
    : error.message || 'An error occurred';

  return (
    <div className="p-4 bg-red-50 border-l-4 border-red-500 rounded">
      <div className="flex items-start gap-3">
        <AlertCircle className="w-5 h-5 text-red-600 shrink-0 mt-0.5" />
        <div className="flex-1">
          <p className="text-red-800 font-medium">Error</p>
          <p className="text-red-700 text-sm mt-1">{message}</p>
          {onRetry && (
            <button
              onClick={onRetry}
              className="mt-2 text-sm text-red-600 hover:text-red-700 font-medium"
            >
              Try again
            </button>
          )}
        </div>
      </div>
    </div>
  );
}