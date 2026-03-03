import React, { useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { ArrowDown, ArrowUp, CheckCheck, Filter, RefreshCw, Search, XCircle } from 'lucide-react';

import { StatusBadge } from '@/components/common/StatusBadge';
import { Loader } from '@/components/common/Loader';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { adminService } from '@/services/admin.service';
import type { AdminCase, AdminCasesResponse, ApplicationStatus } from '@/types';
import { formatDate } from '@/utils/helper';

type StatusFilter = 'all' | ApplicationStatus;
type PriorityFilter = 'all' | 'low' | 'medium' | 'high' | 'urgent';
type SortDirection = 'asc' | 'desc';
type SortField =
  | 'created_at'
  | 'updated_at'
  | 'case_id'
  | 'application_type'
  | 'status'
  | 'priority'
  | 'consistency_score'
  | 'fraud_risk_score';

const PAGE_SIZE_OPTIONS = ['20', '50', '100'];
const SORT_FIELDS: Array<{ value: SortField; label: string }> = [
  { value: 'created_at', label: 'Created Date' },
  { value: 'updated_at', label: 'Updated Date' },
  { value: 'case_id', label: 'Case ID' },
  { value: 'application_type', label: 'Application Type' },
  { value: 'status', label: 'Status' },
  { value: 'priority', label: 'Priority' },
  { value: 'consistency_score', label: 'Consistency Score' },
  { value: 'fraud_risk_score', label: 'Fraud Risk Score' },
];

const DEFAULT_ORDERING = '-created_at';

const parsePage = (value: string | null): number => {
  const parsed = Number(value);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : 1;
};

const parsePageSize = (value: string | null): string => {
  if (!value) return '20';
  return PAGE_SIZE_OPTIONS.includes(value) ? value : '20';
};

const parseStatus = (value: string | null): StatusFilter => {
  if (
    value === 'pending' ||
    value === 'under_review' ||
    value === 'approved' ||
    value === 'rejected'
  ) {
    return value;
  }
  return 'all';
};

const parsePriority = (value: string | null): PriorityFilter => {
  if (value === 'low' || value === 'medium' || value === 'high' || value === 'urgent') {
    return value;
  }
  return 'all';
};

const parseOrdering = (value: string | null): { field: SortField; direction: SortDirection } => {
  const raw = (value || DEFAULT_ORDERING).trim();
  const direction: SortDirection = raw.startsWith('-') ? 'desc' : 'asc';
  const candidate = (raw.startsWith('-') ? raw.slice(1) : raw) as SortField;
  const isSupported = SORT_FIELDS.some((option) => option.value === candidate);

  if (!isSupported) {
    return { field: 'created_at', direction: 'desc' };
  }

  return {
    field: candidate,
    direction,
  };
};

const toOrdering = (field: SortField, direction: SortDirection): string =>
  direction === 'desc' ? `-${field}` : field;

const scoreLabel = (value?: number | null): string => {
  if (typeof value !== 'number') return '-';
  return `${value.toFixed(1)}%`;
};

const AdminCasesPage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();

  const page = parsePage(searchParams.get('page'));
  const pageSize = parsePageSize(searchParams.get('page_size'));
  const statusFilter = parseStatus(searchParams.get('status'));
  const priorityFilter = parsePriority(searchParams.get('priority'));
  const typeFilter = searchParams.get('application_type') || '';
  const sorting = parseOrdering(searchParams.get('ordering'));

  const [typeFilterInput, setTypeFilterInput] = useState(typeFilter);
  const [response, setResponse] = useState<AdminCasesResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reloadCounter, setReloadCounter] = useState(0);

  const [selectedCaseIds, setSelectedCaseIds] = useState<string[]>([]);
  const [bulkActionLoading, setBulkActionLoading] = useState(false);
  const [bulkActionSummary, setBulkActionSummary] = useState<string | null>(null);

  useEffect(() => {
    setTypeFilterInput(typeFilter);
  }, [typeFilter]);

  useEffect(() => {
    setSelectedCaseIds([]);
    setBulkActionSummary(null);
  }, [page, pageSize, statusFilter, priorityFilter, typeFilter, sorting.field, sorting.direction]);

  const updateQuery = (
    updates: Record<string, string | null>,
    options: { keepPage?: boolean } = {},
  ) => {
    const nextParams = new URLSearchParams(searchParams);

    Object.entries(updates).forEach(([key, value]) => {
      if (value === null || value === '' || value === 'all') {
        nextParams.delete(key);
      } else {
        nextParams.set(key, value);
      }
    });

    if (!options.keepPage && !Object.prototype.hasOwnProperty.call(updates, 'page')) {
      nextParams.set('page', '1');
    }

    setSearchParams(nextParams, { replace: true });
  };

  useEffect(() => {
    const fetchCases = async () => {
      try {
        setLoading(true);
        setError(null);

        const data = await adminService.getCases({
          page,
          page_size: Number(pageSize),
          status: statusFilter === 'all' ? undefined : statusFilter,
          priority: priorityFilter === 'all' ? undefined : priorityFilter,
          application_type: typeFilter.trim() || undefined,
          ordering: toOrdering(sorting.field, sorting.direction),
        });

        setResponse(data);
      } catch (fetchError: any) {
        setError(fetchError?.message || 'Unable to load cases.');
      } finally {
        setLoading(false);
      }
    };

    fetchCases();
  }, [page, pageSize, statusFilter, priorityFilter, typeFilter, sorting.field, sorting.direction, reloadCounter]);

  const totalCount = response?.count || 0;
  const totalPages = response?.total_pages || 1;
  const cases = useMemo(() => response?.results ?? [], [response]);

  const pageCaseIds = useMemo(() => cases.map((item) => item.case_id), [cases]);
  const selectedCaseIdSet = useMemo(() => new Set(selectedCaseIds), [selectedCaseIds]);
  const allVisibleSelected = pageCaseIds.length > 0 && pageCaseIds.every((id) => selectedCaseIdSet.has(id));

  const pageStart = useMemo(() => {
    if (totalCount === 0) return 0;
    return (page - 1) * Number(pageSize) + 1;
  }, [page, pageSize, totalCount]);

  const pageEnd = useMemo(() => {
    if (totalCount === 0) return 0;
    return Math.min(page * Number(pageSize), totalCount);
  }, [page, pageSize, totalCount]);

  const toggleCaseSelection = (caseIdentifier: string) => {
    setSelectedCaseIds((current) =>
      current.includes(caseIdentifier)
        ? current.filter((value) => value !== caseIdentifier)
        : [...current, caseIdentifier],
    );
  };

  const toggleSelectAllVisible = () => {
    if (allVisibleSelected) {
      setSelectedCaseIds((current) => current.filter((id) => !pageCaseIds.includes(id)));
      return;
    }

    setSelectedCaseIds((current) => {
      const next = new Set(current);
      pageCaseIds.forEach((id) => next.add(id));
      return Array.from(next);
    });
  };

  const handleBulkStatusUpdate = async (nextStatus: 'approved' | 'rejected') => {
    if (selectedCaseIds.length === 0 || bulkActionLoading) return;

    setBulkActionLoading(true);
    setBulkActionSummary(null);

    const results = await Promise.allSettled(
      selectedCaseIds.map((caseIdentifier) => adminService.updateCaseStatus(caseIdentifier, nextStatus)),
    );

    const successCount = results.filter((result) => result.status === 'fulfilled').length;
    const failedCount = results.length - successCount;

    if (failedCount === 0) {
      setBulkActionSummary(`Updated ${successCount} case(s) to ${nextStatus}.`);
    } else {
      setBulkActionSummary(
        `Updated ${successCount} case(s) to ${nextStatus}; ${failedCount} failed.`,
      );
    }

    setSelectedCaseIds([]);
    setBulkActionLoading(false);
    setReloadCounter((value) => value + 1);
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
        <header className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Admin Case Queue</h1>
            <p className="mt-1 text-slate-800">Review vetting cases with server-side filters and pagination.</p>
          </div>
          <Button
            type="button"
            variant="outline"
            className="w-full border-slate-700 text-slate-900 hover:bg-slate-100 md:w-auto"
            onClick={() => setReloadCounter((value) => value + 1)}
            disabled={loading}
          >
            <RefreshCw className="h-4 w-4" />
            Refresh
          </Button>
        </header>

        <section className="bg-white rounded-lg shadow-sm p-4 md:p-6 space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
            <div className="md:col-span-2">
              <label htmlFor="application-type-filter" className="mb-1 block text-sm font-medium text-slate-800">
                Application Type
              </label>
              <div className="flex flex-col gap-2 sm:flex-row">
                <Input
                  id="application-type-filter"
                  value={typeFilterInput}
                  placeholder="employment, education, credential..."
                  onChange={(event) => setTypeFilterInput(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter') {
                      updateQuery({ application_type: typeFilterInput.trim() || null });
                    }
                  }}
                />
                <Button
                  type="button"
                  variant="outline"
                  className="w-full border-slate-700 text-slate-900 hover:bg-slate-100 sm:w-auto"
                  onClick={() => updateQuery({ application_type: typeFilterInput.trim() || null })}
                >
                  <Search className="h-4 w-4" />
                  Apply
                </Button>
              </div>
            </div>

            <div>
              <label htmlFor="status-filter" className="mb-1 block text-sm font-medium text-slate-800">
                Status
              </label>
              <Select
                value={statusFilter}
                onValueChange={(value) => updateQuery({ status: value })}
              >
                <SelectTrigger id="status-filter">
                  <SelectValue placeholder="All statuses" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All statuses</SelectItem>
                  <SelectItem value="pending">Pending</SelectItem>
                  <SelectItem value="under_review">Under Review</SelectItem>
                  <SelectItem value="approved">Approved</SelectItem>
                  <SelectItem value="rejected">Rejected</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div>
              <label htmlFor="priority-filter" className="mb-1 block text-sm font-medium text-slate-800">
                Priority
              </label>
              <Select
                value={priorityFilter}
                onValueChange={(value) => updateQuery({ priority: value })}
              >
                <SelectTrigger id="priority-filter">
                  <SelectValue placeholder="All priorities" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All priorities</SelectItem>
                  <SelectItem value="low">Low</SelectItem>
                  <SelectItem value="medium">Medium</SelectItem>
                  <SelectItem value="high">High</SelectItem>
                  <SelectItem value="urgent">Urgent</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="flex flex-col gap-3 border-t pt-4 md:flex-row md:items-center md:justify-between">
            <div className="text-sm text-slate-800">
              {loading ? 'Loading cases...' : `Showing ${pageStart}-${pageEnd} of ${totalCount} cases`}
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <Filter className="h-4 w-4 text-slate-800" />
              <span className="text-sm text-slate-800">Page size</span>
              <Select
                value={pageSize}
                onValueChange={(value) =>
                  updateQuery({ page_size: value, page: '1' }, { keepPage: true })
                }
              >
                <SelectTrigger className="w-full sm:w-24">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {PAGE_SIZE_OPTIONS.map((option) => (
                    <SelectItem key={option} value={option}>
                      {option}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>

              <span className="ml-2 text-sm text-slate-800">Sort</span>
              <Select
                value={sorting.field}
                onValueChange={(value) => updateQuery({ ordering: toOrdering(value as SortField, sorting.direction) })}
              >
                <SelectTrigger className="w-full sm:w-48">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {SORT_FIELDS.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>

              <Button
                type="button"
                variant="outline"
                className="w-full border-slate-700 text-slate-900 hover:bg-slate-100 sm:w-auto"
                onClick={() =>
                  updateQuery({
                    ordering: toOrdering(
                      sorting.field,
                      sorting.direction === 'asc' ? 'desc' : 'asc',
                    ),
                  })
                }
                title={sorting.direction === 'asc' ? 'Ascending' : 'Descending'}
              >
                {sorting.direction === 'asc' ? (
                  <>
                    <ArrowUp className="h-4 w-4" />
                    Asc
                  </>
                ) : (
                  <>
                    <ArrowDown className="h-4 w-4" />
                    Desc
                  </>
                )}
              </Button>
            </div>
          </div>
        </section>

        <section className="bg-white rounded-lg shadow-sm p-4 md:p-6 space-y-3">
          <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <p className="text-sm text-slate-900">
              Selected on current queue: <span className="font-semibold">{selectedCaseIds.length}</span>
            </p>
            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                variant="outline"
                className="w-full border-slate-700 text-slate-900 hover:bg-slate-100 sm:w-auto"
                disabled={selectedCaseIds.length === 0 || bulkActionLoading}
                onClick={() => handleBulkStatusUpdate('approved')}
              >
                <CheckCheck className="h-4 w-4" />
                Approve Selected
              </Button>
              <Button
                type="button"
                variant="destructive"
                disabled={selectedCaseIds.length === 0 || bulkActionLoading}
                onClick={() => handleBulkStatusUpdate('rejected')}
              >
                <XCircle className="h-4 w-4" />
                Reject Selected
              </Button>
            </div>
          </div>

          {bulkActionLoading && (
            <p className="text-sm text-slate-800">Applying bulk action...</p>
          )}
          {bulkActionSummary && (
            <p className="text-sm text-slate-800">{bulkActionSummary}</p>
          )}
        </section>

        <section className="bg-white rounded-lg shadow-sm overflow-hidden">
          {loading ? (
            <div className="py-16 flex items-center justify-center">
              <Loader size="lg" />
            </div>
          ) : error ? (
            <div className="p-8 text-center">
              <p className="text-red-600 font-medium">{error}</p>
              <Button
                type="button"
                variant="outline"
                className="mt-4 border-slate-700 text-slate-900 hover:bg-slate-100"
                onClick={() => setReloadCounter((value) => value + 1)}
              >
                Try Again
              </Button>
            </div>
          ) : cases.length === 0 ? (
            <div className="p-10 text-center text-slate-800">
              No cases matched your filters.
            </div>
          ) : (
            <>
              <div className="md:hidden px-4 pt-3 text-xs text-slate-800">
                Swipe horizontally to view all case columns.
              </div>
              <div className="overflow-x-auto">
                <table className="min-w-[1120px] w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="sticky left-0 z-30 w-12 bg-gray-50 px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-800">
                        <input
                          type="checkbox"
                          checked={allVisibleSelected}
                          onChange={toggleSelectAllVisible}
                          aria-label="Select all visible cases"
                        />
                      </th>
                      <th className="sticky left-12 z-20 min-w-[180px] bg-gray-50 px-6 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-800">Case</th>
                      <th className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-800">Applicant</th>
                      <th className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-800">Type</th>
                      <th className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-800">Status</th>
                      <th className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-800">Priority</th>
                      <th className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-800">Consistency</th>
                      <th className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-800">Fraud Risk</th>
                      <th className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-800">Created</th>
                      <th className="px-6 py-3 text-right text-xs font-semibold uppercase tracking-wider text-slate-800">Action</th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-100">
                    {cases.map((item: AdminCase) => (
                      <tr key={item.id} className="hover:bg-slate-100">
                        <td className="sticky left-0 z-20 w-12 whitespace-nowrap bg-white px-4 py-4">
                          <input
                            type="checkbox"
                            checked={selectedCaseIdSet.has(item.case_id)}
                            onChange={() => toggleCaseSelection(item.case_id)}
                            aria-label={`Select case ${item.case_id}`}
                          />
                        </td>
                        <td className="sticky left-12 z-10 min-w-[180px] whitespace-nowrap bg-white px-6 py-4 text-sm font-semibold text-gray-900">{item.case_id}</td>
                        <td className="px-6 py-4 text-sm text-slate-800">
                          <div className="font-medium">{item.applicant_name}</div>
                          <div className="text-slate-800">{item.applicant_email}</div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-800">{item.application_type || '-'}</td>
                        <td className="px-6 py-4 whitespace-nowrap"><StatusBadge status={item.status} /></td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-800 capitalize">{item.priority || '-'}</td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-800">{scoreLabel(item.consistency_score)}</td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-800">{scoreLabel(item.fraud_risk_score)}</td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-800">{formatDate(item.created_at)}</td>
                        <td className="px-6 py-4 whitespace-nowrap text-right">
                          <Button asChild size="sm">
                            <Link to={`/admin/cases/${item.case_id}`}>Review</Link>
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="flex flex-col gap-2 border-t px-6 py-4 sm:flex-row sm:items-center sm:justify-between">
                <p className="text-sm text-slate-800">
                  Page {page} of {totalPages}
                </p>
                <div className="flex flex-col gap-2 sm:flex-row">
                  <Button
                    type="button"
                    variant="outline"
                    className="w-full border-slate-700 text-slate-900 hover:bg-slate-100 sm:w-auto"
                    size="sm"
                    disabled={page <= 1}
                    onClick={() => updateQuery({ page: String(page - 1) }, { keepPage: true })}
                  >
                    Previous
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    className="w-full border-slate-700 text-slate-900 hover:bg-slate-100 sm:w-auto"
                    size="sm"
                    disabled={page >= totalPages}
                    onClick={() => updateQuery({ page: String(page + 1) }, { keepPage: true })}
                  >
                    Next
                  </Button>
                </div>
              </div>
            </>
          )}
        </section>
      </div>
    </div>
  );
};

export default AdminCasesPage;

