// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

import CampaignWorkspacePage from './CampaignWorkspacePage';
import type { BillingQuotaResponse } from '@/services/billing.service';

const mocks = vi.hoisted(() => ({
  campaignService: {
    getById: vi.fn(),
    getDashboard: vi.fn(),
    getEnrollments: vi.fn(),
    getInvitations: vi.fn(),
    listRubricVersions: vi.fn(),
    importCandidates: vi.fn(),
    addRubricVersion: vi.fn(),
    activateRubricVersion: vi.fn(),
  },
  rubricService: {
    getAll: vi.fn(),
  },
  billingService: {
    getQuota: vi.fn(),
  },
  useAuth: vi.fn(),
}));

vi.mock('@/services/campaign.service', () => ({
  campaignService: mocks.campaignService,
}));

vi.mock('@/services/rubric.service', () => ({
  rubricService: mocks.rubricService,
}));

vi.mock('@/services/billing.service', () => ({
  billingService: mocks.billingService,
}));

vi.mock('@/services/invitation.service', () => ({
  invitationService: {
    sendNow: vi.fn(),
  },
}));

vi.mock('@/services/candidate.service', () => ({
  candidateService: {
    markEnrollmentComplete: vi.fn(),
  },
}));

vi.mock('@/hooks/useAuth', () => ({
  useAuth: () => mocks.useAuth(),
}));

vi.mock('react-toastify', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
    warning: vi.fn(),
  },
}));

const baseQuota = (overrides: Partial<BillingQuotaResponse['candidate']> = {}): BillingQuotaResponse => ({
  status: 'ok',
  candidate: {
    enforced: true,
    scope: 'org',
    reason: null,
    plan_id: 'starter',
    plan_name: 'Starter',
    limit: 10,
    used: 0,
    remaining: 10,
    period_start: '2026-03-01T00:00:00Z',
    period_end: '2026-03-31T23:59:59Z',
    ...overrides,
  },
});

const configureDefaultServices = () => {
  mocks.useAuth.mockReturnValue({ userType: 'hr_manager' });
  mocks.campaignService.getById.mockResolvedValue({
    id: 'camp-1',
    name: 'March Vetting',
    description: 'Campaign for March',
    status: 'active',
    starts_at: null,
    ends_at: null,
    settings_json: {},
    initiated_by: 'u-1',
    initiated_by_email: 'hr@example.com',
    created_at: '2026-03-01T00:00:00Z',
    updated_at: '2026-03-01T00:00:00Z',
  });
  mocks.campaignService.getDashboard.mockResolvedValue({
    total_candidates: 0,
    invited: 0,
    registered: 0,
    in_progress: 0,
    completed: 0,
    reviewed: 0,
    approved: 0,
    rejected: 0,
    escalated: 0,
  });
  mocks.campaignService.getEnrollments.mockResolvedValue([]);
  mocks.campaignService.getInvitations.mockResolvedValue([]);
  mocks.campaignService.listRubricVersions.mockResolvedValue([]);
  mocks.rubricService.getAll.mockResolvedValue([]);
};

const renderPage = () =>
  render(
    <MemoryRouter initialEntries={['/campaigns/camp-1/workspace']}>
      <Routes>
        <Route path="/campaigns/:campaignId/workspace" element={<CampaignWorkspacePage />} />
      </Routes>
    </MemoryRouter>,
  );

describe('CampaignWorkspacePage import guard', () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('disables import submit when payload JSON is invalid', async () => {
    configureDefaultServices();
    mocks.billingService.getQuota.mockResolvedValue(baseQuota({ used: 1, limit: 10, remaining: 9 }));

    renderPage();

    const importButton = await screen.findByRole('button', { name: /^import candidates$/i });
    expect((importButton as HTMLButtonElement).disabled).toBe(false);

    const payloadTextarea = screen.getByLabelText(/payload \(json array\)/i);
    fireEvent.change(payloadTextarea, { target: { value: 'not-json' } });

    await waitFor(() => {
      expect((importButton as HTMLButtonElement).disabled).toBe(true);
    });
  });

  it('disables import submit when projected usage exceeds quota', async () => {
    configureDefaultServices();
    mocks.billingService.getQuota.mockResolvedValue(baseQuota({ used: 10, limit: 10, remaining: 0 }));

    renderPage();

    const importButton = await screen.findByRole('button', { name: /^import candidates$/i });
    expect((importButton as HTMLButtonElement).disabled).toBe(true);

    await waitFor(() => {
      expect(screen.getByText(/projected import exceeds quota/i)).toBeTruthy();
    });
  });

  it('renders backend quota detail when import request is rejected', async () => {
    configureDefaultServices();
    mocks.billingService.getQuota.mockResolvedValue(baseQuota({ used: 0, limit: 10, remaining: 10 }));
    mocks.campaignService.importCandidates.mockRejectedValue({
      response: {
        data: {
          detail:
            "Candidate quota exceeded for plan 'Starter'. Monthly limit 10, current usage 10, requested additional 1.",
          code: 'quota_exceeded',
        },
      },
    });

    renderPage();

    const importButton = await screen.findByRole('button', { name: /^import candidates$/i });
    expect((importButton as HTMLButtonElement).disabled).toBe(false);

    fireEvent.click(importButton);

    await waitFor(() => {
      expect(mocks.campaignService.importCandidates).toHaveBeenCalledTimes(1);
    });

    await waitFor(() => {
      expect(screen.getByText(/candidate quota exceeded for plan/i)).toBeTruthy();
      expect(screen.getByText(/monthly limit 10/i)).toBeTruthy();
    });
  });

  it('updates quota badge from backend quota payload on rejected import', async () => {
    configureDefaultServices();
    mocks.billingService.getQuota.mockResolvedValue(baseQuota({ used: 0, limit: 10, remaining: 10 }));
    mocks.campaignService.importCandidates.mockRejectedValue({
      response: {
        data: {
          detail:
            "Candidate quota exceeded for plan 'Starter'. Monthly limit 10, current usage 10, requested additional 1.",
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

    renderPage();

    expect(await screen.findByText(/0\/10 used/i)).toBeTruthy();

    const importButton = await screen.findByRole('button', { name: /^import candidates$/i });
    fireEvent.click(importButton);

    await waitFor(() => {
      expect(mocks.campaignService.importCandidates).toHaveBeenCalledTimes(1);
    });

    await waitFor(() => {
      expect(screen.getByText(/10\/10 used/i)).toBeTruthy();
      expect(
        screen.getAllByText((_, element) =>
          String(element?.textContent || '').includes('Projected usage: 11/10'),
        ).length,
      ).toBeGreaterThan(0);
    });
  });

  it('renders backend subscription-required message when no active subscription exists', async () => {
    configureDefaultServices();
    mocks.billingService.getQuota.mockResolvedValue(baseQuota({ used: 0, limit: 10, remaining: 10 }));
    mocks.campaignService.importCandidates.mockRejectedValue({
      response: {
        data: {
          detail:
            'No active paid subscription found for this workspace. Complete subscription setup before adding candidates.',
          code: 'subscription_required',
        },
      },
    });

    renderPage();

    const importButton = await screen.findByRole('button', { name: /^import candidates$/i });
    expect((importButton as HTMLButtonElement).disabled).toBe(false);

    fireEvent.click(importButton);

    await waitFor(() => {
      expect(mocks.campaignService.importCandidates).toHaveBeenCalledTimes(1);
    });

    await waitFor(() => {
      expect(screen.getByText(/no active paid subscription found/i)).toBeTruthy();
      expect(screen.getByText(/complete subscription setup before adding candidates/i)).toBeTruthy();
    });
  });
});
