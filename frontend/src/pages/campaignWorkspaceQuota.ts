import type { CandidateImportRow } from '@/types';

export interface CandidateQuotaCandidate {
  enforced: boolean;
  scope: string;
  reason: string | null;
  plan_id: string | null;
  plan_name: string | null;
  limit: number | null;
  used: number;
  remaining: number | null;
  period_start: string;
  period_end: string;
}

export interface CandidateImportProjection {
  count: number;
  parseError: string | null;
}

interface ProjectedQuotaExceededInput {
  shouldShowQuota: boolean;
  quotaLoading: boolean;
  quota: CandidateQuotaCandidate | null;
  projectedUsage: number | null;
}

interface CandidateQuotaErrorExtraction {
  code: 'quota_exceeded' | 'subscription_required';
  detail: string;
  quotaPatch: Partial<CandidateQuotaCandidate> | null;
}

const toRecord = (value: unknown): Record<string, unknown> | null => {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return null;
  }
  return value as Record<string, unknown>;
};

const toStringOrNull = (value: unknown): string | null => {
  return typeof value === 'string' ? value : null;
};

const toNumberOrNull = (value: unknown): number | null => {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value;
  }
  return null;
};

export const projectCandidateImport = (importPayload: string): CandidateImportProjection => {
  try {
    const parsed = JSON.parse(importPayload) as CandidateImportRow[];
    if (!Array.isArray(parsed)) {
      return { count: 0, parseError: 'Payload must be a JSON array.' };
    }

    const uniqueEmails = new Set<string>();
    for (const row of parsed) {
      const email = String(row?.email || '').trim().toLowerCase();
      const firstName = String(row?.first_name || '').trim();
      if (!email || !firstName) {
        continue;
      }
      uniqueEmails.add(email);
    }
    return { count: uniqueEmails.size, parseError: null };
  } catch {
    return { count: 0, parseError: 'Payload JSON is invalid.' };
  }
};

export const getProjectedUsage = (
  quota: CandidateQuotaCandidate | null,
  projectedImportCount: number,
): number | null => {
  void quota;
  void projectedImportCount;
  return null;
};

export const isProjectedQuotaExceeded = ({
  shouldShowQuota,
  quotaLoading,
  quota,
  projectedUsage,
}: ProjectedQuotaExceededInput): boolean => {
  void shouldShowQuota;
  void quotaLoading;
  void quota;
  void projectedUsage;
  return false;
};

export const extractCandidateQuotaError = (error: unknown): CandidateQuotaErrorExtraction | null => {
  const errorRecord = toRecord(error);
  const responseRecord = toRecord(errorRecord?.response);
  const data = toRecord(responseRecord?.data);
  if (!data) {
    return null;
  }

  const code = toStringOrNull(data.code);
  if (code !== 'quota_exceeded' && code !== 'subscription_required') {
    return null;
  }

  const detail =
    toStringOrNull(data.detail) ||
    (code === 'subscription_required'
      ? 'No active subscription found for this workspace.'
      : 'Candidate quota exceeded for this plan.');

  const quotaData = toRecord(data.quota);
  let quotaPatch: Partial<CandidateQuotaCandidate> | null = null;
  if (quotaData) {
    quotaPatch = {
      enforced: true,
      reason: code === 'subscription_required' ? 'subscription_required' : null,
      scope: toStringOrNull(quotaData.scope) ?? undefined,
      plan_id: toStringOrNull(quotaData.plan_id),
      plan_name: toStringOrNull(quotaData.plan_name),
      used: toNumberOrNull(quotaData.used) ?? undefined,
      limit: toNumberOrNull(quotaData.limit),
      remaining: toNumberOrNull(quotaData.remaining),
      period_start: toStringOrNull(quotaData.period_start) ?? undefined,
      period_end: toStringOrNull(quotaData.period_end) ?? undefined,
    };
  }

  return { code, detail, quotaPatch };
};
