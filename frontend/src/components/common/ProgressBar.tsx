// src/components/common/ProgressBar.tsx
import React from 'react';
import { cn } from '@/lib/utils';

interface ProgressBarProps {
  value: number;
  color?: string;
  className?: string;
}

export const ProgressBar: React.FC<ProgressBarProps> = ({ value, color = 'bg-blue-600', className }) => {
  return (
    <div className={cn('w-full bg-gray-200 rounded-full h-2', className)}>
      <div
        className={cn('h-2 rounded-full transition-all duration-300', color)}
        style={{ width: `${Math.min(value, 100)}%` }}
      />
    </div>
  );
};