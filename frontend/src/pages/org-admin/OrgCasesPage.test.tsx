// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

import OrgCasesPage from './OrgCasesPage';

const mocks = vi.hoisted(() => ({
  adminService: {
    getOrgCases: vi.fn(),
    updateOrgCaseStatus: vi.fn(),
  },
}));

vi.mock('@/services/admin.service', () => ({
  adminService: mocks.adminService,
}));

describe('OrgCasesPage filters', () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('hydrates URL filters and clears active filter set', async () => {
    mocks.adminService.getOrgCases.mockResolvedValue({
      results: [
        {
          id: 'case-row-1',
          case_id: 'CASE-001',
          applicant_name: 'Jane Candidate',
          applicant_email: 'jane@example.com',
          status: 'pending',
          application_type: 'employment',
          priority: 'high',
          consistency_score: 83.4,
          fraud_risk_score: 22.1,
          created_at: '2026-03-01T10:00:00Z',
          updated_at: '2026-03-01T10:00:00Z',
          admin: null,
        },
      ],
      count: 1,
      page: 1,
      page_size: 20,
      total_pages: 1,
      ordering: '-created_at',
    });

    render(
      <MemoryRouter
        initialEntries={['/admin/org/org-1/cases?status=pending&priority=high&application_type=employment']}
      >
        <Routes>
          <Route path="/admin/org/:orgId/cases" element={<OrgCasesPage />} />
        </Routes>
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(mocks.adminService.getOrgCases).toHaveBeenCalledWith(
        'org-1',
        expect.objectContaining({
          status: 'pending',
          priority: 'high',
          application_type: 'employment',
        }),
      );
    });

    expect(await screen.findByText(/active filters/i)).toBeTruthy();
    expect(await screen.findByRole('button', { name: /clear case filters/i })).toBeTruthy();

    fireEvent.click(await screen.findByRole('button', { name: /clear case filters/i }));

    await waitFor(() => {
      expect(mocks.adminService.getOrgCases).toHaveBeenLastCalledWith(
        'org-1',
        expect.objectContaining({
          status: undefined,
          priority: undefined,
          application_type: undefined,
        }),
      );
    });

    const typeInput = await screen.findByLabelText(/application type/i);
    expect((typeInput as HTMLInputElement).value).toBe('');

    await waitFor(() => {
      expect(screen.queryByText(/active filters/i)).toBeNull();
    });
  });
});
