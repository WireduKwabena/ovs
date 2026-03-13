// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

import CampaignsPage from './CampaignsPage';

const mocks = vi.hoisted(() => ({
  campaignService: {
    list: vi.fn(),
    create: vi.fn(),
  },
  billingService: {
    getQuota: vi.fn(),
  },
  useAuth: vi.fn(),
}));

vi.mock('@/services/campaign.service', () => ({
  campaignService: mocks.campaignService,
}));

vi.mock('@/services/billing.service', () => ({
  billingService: mocks.billingService,
}));

vi.mock('@/hooks/useAuth', () => ({
  useAuth: () => mocks.useAuth(),
}));

describe('CampaignsPage list filters', () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('hydrates list filters from URL and clears all active filters', async () => {
    mocks.useAuth.mockReturnValue({
      canManageRegistry: true,
      userType: 'internal',
    });
    mocks.billingService.getQuota.mockResolvedValue({
      status: 'ok',
      candidate: {
        enforced: true,
        scope: 'org',
        reason: null,
        plan_id: 'growth',
        plan_name: 'Growth',
        limit: 100,
        used: 5,
        remaining: 95,
        period_start: '2026-03-01T00:00:00Z',
        period_end: '2026-03-31T23:59:59Z',
      },
    });
    mocks.campaignService.list.mockResolvedValue([
      {
        id: 'campaign-1',
        name: 'Graduate Vetting 2026',
        description: 'Main graduate intake campaign',
        status: 'active',
        starts_at: null,
        ends_at: null,
        settings_json: {},
        initiated_by: 'hr-1',
        initiated_by_email: 'hr@example.com',
        created_at: '2026-03-01T10:00:00Z',
        updated_at: '2026-03-01T10:00:00Z',
      },
      {
        id: 'campaign-2',
        name: 'Archive Intake',
        description: 'Legacy archive process',
        status: 'draft',
        starts_at: null,
        ends_at: null,
        settings_json: {},
        initiated_by: 'hr-1',
        initiated_by_email: 'hr@example.com',
        created_at: '2026-03-01T10:00:00Z',
        updated_at: '2026-03-01T10:00:00Z',
      },
      {
        id: 'campaign-3',
        name: 'Executive Vetting',
        description: 'Senior role vetting',
        status: 'active',
        starts_at: null,
        ends_at: null,
        settings_json: {},
        initiated_by: 'hr-1',
        initiated_by_email: 'hr@example.com',
        created_at: '2026-03-01T10:00:00Z',
        updated_at: '2026-03-01T10:00:00Z',
      },
    ]);

    render(
      <MemoryRouter initialEntries={['/campaigns?q=graduate&status=active']}>
        <CampaignsPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(mocks.campaignService.list).toHaveBeenCalledTimes(1);
    });

    expect(await screen.findByText(/active filters/i)).toBeTruthy();
    expect(await screen.findByText(/Graduate Vetting 2026/i)).toBeTruthy();
    expect(screen.queryByText(/Archive Intake/i)).toBeNull();
    expect(screen.queryByText(/Executive Vetting/i)).toBeNull();

    fireEvent.click(await screen.findByRole('button', { name: /clear exercise filters/i }));

    await waitFor(() => {
      expect(screen.queryByText(/active filters/i)).toBeNull();
    });
    expect(await screen.findByText(/Archive Intake/i)).toBeTruthy();
    expect(await screen.findByText(/Executive Vetting/i)).toBeTruthy();
  });
});


