import { describe, expect, it } from 'vitest';

import type { BillingQuotaCandidate } from '@/services/billing.service';
import {
  extractCandidateQuotaError,
  getProjectedUsage,
  isProjectedQuotaExceeded,
  projectCandidateImport,
} from './campaignWorkspaceQuota';

const limitedQuota: BillingQuotaCandidate = {
  enforced: true,
  scope: 'org',
  reason: null,
  plan_id: 'starter',
  plan_name: 'Starter',
  limit: 10,
  used: 8,
  remaining: 2,
  period_start: '2026-03-01T00:00:00Z',
  period_end: '2026-03-31T23:59:59Z',
};

describe('campaignWorkspaceQuota', () => {
  it('projects unique candidate count from valid payload rows only', () => {
    const payload = JSON.stringify([
      { first_name: 'Ama', email: 'ama@example.com' },
      { first_name: 'Ama', email: 'AMA@example.com' },
      { first_name: 'Kofi', email: 'kofi@example.com' },
      { first_name: '', email: 'missing-name@example.com' },
      { first_name: 'NoEmail', email: '' },
    ]);

    expect(projectCandidateImport(payload)).toEqual({
      count: 2,
      parseError: null,
    });
  });

  it('returns parse error when payload is not an array', () => {
    expect(projectCandidateImport('{"email":"one@example.com"}')).toEqual({
      count: 0,
      parseError: 'Payload must be a JSON array.',
    });
  });

  it('returns parse error for invalid JSON', () => {
    expect(projectCandidateImport('not-json')).toEqual({
      count: 0,
      parseError: 'Payload JSON is invalid.',
    });
  });

  it('flags projected quota exceeded for limited plans', () => {
    const projectedUsage = getProjectedUsage(limitedQuota, 3);
    expect(projectedUsage).toBe(11);
    expect(
      isProjectedQuotaExceeded({
        shouldShowQuota: true,
        quotaLoading: false,
        quota: limitedQuota,
        projectedUsage,
      }),
    ).toBe(true);
  });

  it('does not flag projected quota exceeded for unlimited plans', () => {
    const unlimitedQuota: BillingQuotaCandidate = {
      ...limitedQuota,
      limit: null,
      remaining: null,
    };
    const projectedUsage = getProjectedUsage(unlimitedQuota, 1000);

    expect(projectedUsage).toBeNull();
    expect(
      isProjectedQuotaExceeded({
        shouldShowQuota: true,
        quotaLoading: false,
        quota: unlimitedQuota,
        projectedUsage,
      }),
    ).toBe(false);
  });

  it('extracts DRF quota_exceeded payload including quota patch fields', () => {
    const extracted = extractCandidateQuotaError({
      response: {
        data: {
          detail: "Candidate quota exceeded for plan 'Starter'. Monthly limit 10, current usage 10, requested additional 3.",
          code: 'quota_exceeded',
          quota: {
            scope: 'org',
            plan_id: 'starter',
            plan_name: 'Starter',
            used: 10,
            limit: 10,
            remaining: 0,
            period_start: '2026-03-01T00:00:00Z',
            period_end: '2026-03-31T23:59:59Z',
          },
        },
      },
    });

    expect(extracted).toEqual({
      code: 'quota_exceeded',
      detail:
        "Candidate quota exceeded for plan 'Starter'. Monthly limit 10, current usage 10, requested additional 3.",
      quotaPatch: {
        enforced: true,
        reason: null,
        scope: 'org',
        plan_id: 'starter',
        plan_name: 'Starter',
        used: 10,
        limit: 10,
        remaining: 0,
        period_start: '2026-03-01T00:00:00Z',
        period_end: '2026-03-31T23:59:59Z',
      },
    });
  });

  it('returns null for non-quota API errors', () => {
    expect(
      extractCandidateQuotaError({
        response: {
          data: {
            detail: 'Validation failed.',
            code: 'invalid_payload',
          },
        },
      }),
    ).toBeNull();
  });
});
