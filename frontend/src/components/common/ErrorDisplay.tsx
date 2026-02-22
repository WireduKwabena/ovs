// src/components/common/ErrorDisplay.tsx

import { AlertTriangle } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface ErrorDisplayProps {
  title?: string;
  message: string;
  onRetry?: () => void;
  onGoHome?: () => void;
}

export default function ErrorDisplay({
  title = 'Something went wrong',
  message,
  onRetry,
  onGoHome,
}: ErrorDisplayProps) {
  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-background text-foreground p-4">
      <div className="text-center max-w-md">
        <div className="flex justify-center mb-4">
          <AlertTriangle className="w-16 h-16 text-destructive" />
        </div>
        <h1 className="text-3xl font-bold mb-2">{title}</h1>
        <p className="text-muted-foreground mb-6">{message}</p>
        <div className="flex gap-4 justify-center">
          {onGoHome && (
            <Button variant="outline" onClick={onGoHome}>
              Go to Homepage
            </Button>
          )}
          {onRetry && <Button onClick={onRetry}>Try Again</Button>}
        </div>
      </div>
    </div>
  );
}