// src/components/common/Loader.tsx
import React from 'react';
import { cn } from '@/utils/helper';  // Fixed path

interface LoaderProps {
  size?: 'sm' | 'md' | 'lg' | 'xl';
  color?: 'blue' | 'white' | 'gray';
}

export const Loader: React.FC<LoaderProps> = ({ size = 'md', color = 'blue' }) => {
  const sizes = {
    sm: 'w-4 h-4 border-2',
    md: 'w-8 h-8 border-4',
    lg: 'w-12 h-12 border-4',
    xl: 'w-16 h-16 border-4',
  };

  const colors = {
    blue: 'border-blue-600',
    white: 'border-white',
    gray: 'border-gray-600',
  };

  return (
    <div
      className={cn(
        'rounded-full animate-spin border-t-transparent',
        sizes[size],
        colors[color]
      )}
    />
  );
};