// src/components/common/StatusBadge.tsx
import React from 'react';
import { CheckCircle, XCircle, Clock, AlertTriangle } from 'lucide-react';
import type { ApplicationStatus, VerificationStatusType } from '@/types';
import { STATUS_COLORS } from '@/utils/constants';
import { cn } from '@/utils/helper';  // Fixed path

export interface StatusBadgeProps {
  status: ApplicationStatus | VerificationStatusType;
}

const statusConfig = {
  pending: { icon: Clock, label: 'Pending' },
  document_upload: { icon: Clock, label: 'Document Upload' },
  document_analysis: { icon: Clock, label: 'Document Analysis' },
  interview_scheduled: { icon: Clock, label: 'Interview Scheduled' },
  interview_in_progress: { icon: Clock, label: 'Interview In Progress' },
  under_review: { icon: AlertTriangle, label: 'Under Review' },
  approved: { icon: CheckCircle, label: 'Approved' },
  rejected: { icon: XCircle, label: 'Rejected' },
  on_hold: { icon: AlertTriangle, label: 'On Hold' },
  uploaded: { icon: Clock, label: 'Uploaded' },
  queued: { icon: Clock, label: 'Queued' },
  processing: { icon: Clock, label: 'Processing' },
  verified: { icon: CheckCircle, label: 'Verified' },
  failed: { icon: XCircle, label: 'Failed' },
  flagged: { icon: AlertTriangle, label: 'Flagged' },
} as const;

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status }) => {
  const config = statusConfig[status as keyof typeof statusConfig] || statusConfig.pending;
  const Icon = config.icon;
  const colorClass = STATUS_COLORS[status as keyof typeof STATUS_COLORS] || STATUS_COLORS.pending;

  return (
    <span
      className={cn(
        'inline-flex items-center gap-2 px-3 py-1 rounded-full font-medium text-sm border',
        colorClass
      )}
    >
      <Icon className="w-4 h-4" />
      {config.label}
    </span>
  );
};
