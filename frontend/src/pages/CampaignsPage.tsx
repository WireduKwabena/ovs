import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { Plus, FolderKanban, CalendarDays, RefreshCw, Info } from 'lucide-react';
import { HelpTooltip, FieldLabel } from '@/components/common/FieldHelp';
import type { DocumentType, VettingCampaign } from '@/types';
import { campaignService } from '@/services/campaign.service';
import { billingService, type BillingQuotaCandidate } from '@/services/billing.service';
import { formatDate } from '@/utils/helper';
import { useAuth } from '@/hooks/useAuth';
import { Input } from '@/components/ui/input';
import { applyQueryUpdates, normalizeQueryValue } from '@/utils/queryParams';
import { DOCUMENT_TYPE_OPTIONS, getDocumentTypeLabel } from '@/constants/documentTypes';

const statusBadgeClass: Record<string, string> = {
  draft: 'bg-slate-200 text-slate-800',
  active: 'bg-emerald-100 text-emerald-700',
  closed: 'bg-amber-100 text-amber-700',
  archived: 'bg-zinc-100 text-zinc-700',
};

type CampaignListStatusFilter = VettingCampaign['status'] | 'all';

const CAMPAIGN_LIST_STATUS_VALUES: CampaignListStatusFilter[] = ['all', 'draft', 'active', 'closed', 'archived'];

const parseCampaignListStatusFilter = (value: string | null): CampaignListStatusFilter => {
  const normalized = normalizeQueryValue(value);
  return CAMPAIGN_LIST_STATUS_VALUES.includes(normalized as CampaignListStatusFilter)
    ? (normalized as CampaignListStatusFilter)
    : 'all';
};

const CampaignsPage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const { canManageRegistry, userType } = useAuth();
  const [campaigns, setCampaigns] = useState<VettingCampaign[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [quota, setQuota] = useState<BillingQuotaCandidate | null>(null);
  const [quotaLoading, setQuotaLoading] = useState(false);
  const [quotaError, setQuotaError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [form, setForm] = useState({
    name: '',
    description: '',
    status: 'draft' as VettingCampaign['status'],
    starts_at: '',
    ends_at: '',
    required_document_types: ['id_card'] as DocumentType[],
  });
  const [campaignSearchFilter, setCampaignSearchFilter] = useState<string>(() =>
    normalizeQueryValue(searchParams.get('q')),
  );
  const [campaignStatusFilter, setCampaignStatusFilter] = useState<CampaignListStatusFilter>(() =>
    parseCampaignListStatusFilter(searchParams.get('status')),
  );
  const [officeFilter, setOfficeFilter] = useState<string>(() => normalizeQueryValue(searchParams.get('office')));

  const canManageCampaigns = canManageRegistry;
  const shouldShowQuota = canManageCampaigns && userType !== "applicant";

  const fetchCampaigns = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await campaignService.list();
      setCampaigns(data);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || 'Failed to load appointment exercises.');
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchQuota = useCallback(async () => {
    if (!shouldShowQuota) {
      setQuota(null);
      setQuotaError(null);
      return;
    }

    setQuotaLoading(true);
    setQuotaError(null);
    try {
      const data = await billingService.getQuota();
      setQuota(data.candidate);
    } catch (err: any) {
      setQuotaError(err?.response?.data?.detail || err?.message || 'Failed to load quota.');
    } finally {
      setQuotaLoading(false);
    }
  }, [shouldShowQuota]);

  useEffect(() => {
    void fetchCampaigns();
  }, [fetchCampaigns]);

  useEffect(() => {
    void fetchQuota();
  }, [fetchQuota]);

  useEffect(() => {
    const currentSearch = normalizeQueryValue(searchParams.get('q'));
    const currentStatus = parseCampaignListStatusFilter(searchParams.get('status'));
    const currentOffice = normalizeQueryValue(searchParams.get('office'));
    if (
      currentSearch === campaignSearchFilter &&
      currentStatus === campaignStatusFilter &&
      currentOffice === officeFilter
    ) {
      return;
    }

    const nextParams = applyQueryUpdates(
      searchParams,
      {
        q: campaignSearchFilter || null,
        status: campaignStatusFilter,
        office: officeFilter || null,
      },
      { keepPage: true },
    );
    setSearchParams(nextParams, { replace: true });
  }, [campaignSearchFilter, campaignStatusFilter, officeFilter, searchParams, setSearchParams]);

  useEffect(() => {
    const nextOffice = normalizeQueryValue(searchParams.get('office'));
    if (nextOffice !== officeFilter) {
      setOfficeFilter(nextOffice);
    }
  }, [officeFilter, searchParams]);

  const totalByStatus = useMemo(() => {
    return campaigns.reduce(
      (acc, campaign) => {
        acc[campaign.status] = (acc[campaign.status] || 0) + 1;
        return acc;
      },
      {} as Record<string, number>
    );
  }, [campaigns]);

  const filteredCampaigns = useMemo(() => {
    const normalizedSearch = campaignSearchFilter.toLowerCase();
    return campaigns.filter((campaign) => {
      const linkedOfficeIds =
        (Array.isArray(campaign.office_ids) && campaign.office_ids.length > 0
          ? campaign.office_ids
          : campaign.position_ids) || [];
      if (officeFilter && !linkedOfficeIds.includes(officeFilter)) {
        return false;
      }
      if (campaignStatusFilter !== 'all' && campaign.status !== campaignStatusFilter) {
        return false;
      }
      if (normalizedSearch) {
        const haystack = `${campaign.name} ${campaign.description || ''} ${campaign.status} ${
          campaign.initiated_by_email || ''
        }`.toLowerCase();
        if (!haystack.includes(normalizedSearch)) {
          return false;
        }
      }
      return true;
    });
  }, [campaignSearchFilter, campaignStatusFilter, campaigns, officeFilter]);

  const isCampaignSearchFilterActive = campaignSearchFilter.length > 0;
  const isCampaignStatusFilterActive = campaignStatusFilter !== 'all';
  const isCampaignOfficeFilterActive = officeFilter.length > 0;
  const hasCampaignListFilters =
    isCampaignSearchFilterActive || isCampaignStatusFilterActive || isCampaignOfficeFilterActive;

  const quotaBadge = useMemo(() => {
    if (!shouldShowQuota) {
      return null;
    }
    if (quotaLoading) {
      return { label: 'Quota: loading', className: 'bg-slate-100 text-slate-800' };
    }
    if (quotaError || !quota) {
      return { label: 'Quota: unavailable', className: 'bg-amber-100 text-amber-800' };
    }
    if (quota.limit === null) {
      return {
        label: `Quota: ${quota.used}/∞`,
        className: 'bg-emerald-100 text-emerald-800',
      };
    }
    const label = `Quota: ${quota.used}/${quota.limit}`;
    if (quota.remaining !== null && quota.remaining <= 0) {
      return { label, className: 'bg-red-100 text-red-800' };
    }
    if (quota.remaining !== null && quota.remaining <= 10) {
      return { label, className: 'bg-amber-100 text-amber-800' };
    }
    return { label, className: 'bg-cyan-100 text-cyan-800' };
  }, [quota, quotaError, quotaLoading, shouldShowQuota]);

  const handleCreateCampaign = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!form.name.trim()) {
      setError('Appointment exercise name is required.');
      return;
    }
    if (form.required_document_types.length === 0) {
      setError('Select at least one required document type for this appointment exercise.');
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      const created = await campaignService.create({
        name: form.name.trim(),
        description: form.description.trim(),
        status: form.status,
        starts_at: form.starts_at || null,
        ends_at: form.ends_at || null,
        required_document_types: form.required_document_types,
      });
      setCampaigns((prev) => [created, ...prev]);
      setForm({
        name: '',
        description: '',
        status: 'draft',
        starts_at: '',
        ends_at: '',
        required_document_types: ['id_card'],
      });
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || 'Failed to create appointment exercise.');
    } finally {
      setSubmitting(false);
    }
  };

  if (!canManageCampaigns) {
    return (
      <main className="mx-auto max-w-4xl px-4 py-10 sm:px-6 lg:px-6 xl:px-8">
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-6 text-amber-800">
          Your account does not have appointment-exercise management access.
        </div>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-7xl space-y-6 px-4 py-8 sm:px-6 lg:px-6 xl:px-8">
      <section className="rounded-2xl bg-slate-900 text-white p-6">
        <div className="flex flex-wrap gap-4 items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold">Appointment Exercises</h1>
            <p className="mt-1 text-slate-200">
              Open and manage appointment exercises that drive nomination vetting and review.
            </p>
          </div>
          <button
            type="button"
            onClick={() => {
              void fetchCampaigns();
              void fetchQuota();
            }}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
            Refresh
          </button>
        </div>
      </section>

      <section className="rounded-xl border border-cyan-200 bg-cyan-50 p-4">
        <p className="text-xs font-semibold uppercase tracking-wide text-cyan-900">Office-Centered Sequence</p>
        <p className="mt-2 text-sm text-cyan-900">
          Offices define what is being filled. Exercises operationalize vetting for those offices before nomination,
          review, approval, appointment, and publication.
        </p>
        <div className="mt-3 flex flex-wrap gap-2">
          <Link
            to="/government/positions"
            className="inline-flex rounded-md border border-cyan-300 bg-white px-3 py-1.5 text-xs font-semibold text-cyan-900 hover:bg-cyan-100"
          >
            1. Offices
          </Link>
          <Link
            to="/government/appointments"
            className="inline-flex rounded-md border border-cyan-300 bg-white px-3 py-1.5 text-xs font-semibold text-cyan-900 hover:bg-cyan-100"
          >
            3. Nomination Files
          </Link>
          <Link
            to="/applications"
            className="inline-flex rounded-md border border-cyan-300 bg-white px-3 py-1.5 text-xs font-semibold text-cyan-900 hover:bg-cyan-100"
          >
            4. Vetting Dossiers
          </Link>
        </div>
      </section>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 text-red-700 px-4 py-3">
          {error}
        </div>
      )}

      <section className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <p className="text-sm text-slate-700">Total</p>
          <p className="text-2xl font-semibold">{campaigns.length}</p>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <p className="text-sm text-slate-700">Active</p>
          <p className="text-2xl font-semibold">{totalByStatus.active || 0}</p>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <p className="text-sm text-slate-700">Draft</p>
          <p className="text-2xl font-semibold">{totalByStatus.draft || 0}</p>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <p className="text-sm text-slate-700">Closed</p>
          <p className="text-2xl font-semibold">{totalByStatus.closed || 0}</p>
        </div>
      </section>

      {shouldShowQuota && (
        <section className="rounded-xl border border-cyan-200 bg-cyan-50 p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-base font-semibold text-cyan-900">Monthly Vetting Intake Quota</h2>
              <p className="text-sm text-cyan-800">
                Subscription-based intake limit (tracked on nominee intake enrollments) for your current monthly window.
              </p>
            </div>
            {quotaLoading ? (
              <span className="text-sm text-cyan-800">Loading...</span>
            ) : quota ? (
              <span className="rounded-full bg-cyan-100 px-3 py-1 text-sm font-semibold text-cyan-900">
                {quota.limit === null ? 'Unlimited' : `${quota.used}/${quota.limit}`} used
              </span>
            ) : (
              <span className="text-sm text-cyan-800">Unavailable</span>
            )}
          </div>

          {quotaError && (
            <p className="mt-2 text-sm text-red-700">{quotaError}</p>
          )}

          {!quotaLoading && quota && (
            <div className="mt-3 grid gap-2 text-sm text-cyan-900 sm:grid-cols-4">
              <p>
                <span className="font-semibold">Plan:</span>{' '}
                {quota.plan_name || quota.plan_id || 'Unassigned'}
              </p>
              <p>
                <span className="font-semibold">Used:</span> {quota.used}
              </p>
              <p>
                <span className="font-semibold">Remaining:</span>{' '}
                {quota.remaining === null ? 'Unlimited' : quota.remaining}
              </p>
              <p>
                <span className="font-semibold">Window:</span>{' '}
                {formatDate(quota.period_start)} - {formatDate(quota.period_end)}
              </p>
            </div>
          )}
        </section>
      )}

      <section className="grid grid-cols-1 lg:grid-cols-5 gap-6">
        <div className="lg:col-span-2 rounded-xl border border-slate-200 bg-white p-5">
          <div className="mb-4">
              <h2 className="text-lg font-semibold inline-flex items-center gap-2">
              <Plus className="w-5 h-5 text-indigo-600" />
              Create Appointment Exercise
            </h2>
            <div className="mt-3 rounded-lg border border-indigo-200 bg-indigo-50 px-3 py-2 text-xs text-indigo-900">
              Hover or focus the <Info className="mx-1 inline h-3.5 w-3.5 align-text-bottom" /> icons beside labels for guidance.
            </div>
          </div>
          <form className="space-y-3" onSubmit={handleCreateCampaign}>
            <div>
              <FieldLabel
                htmlFor="campaign-name"
                label="Name"
                required
                help="Use a clear exercise name like 'Ministerial Appointments 2026 - Q2'."
                className="mb-1 flex items-center gap-1.5"
                textClassName="block text-sm font-medium text-slate-700"
              />
              <input
                id="campaign-name"
                required
                value={form.name}
                onChange={(event) => setForm((prev) => ({ ...prev, name: event.target.value }))}
                className="w-full rounded-lg border border-slate-700 px-3 py-2 focus:ring-2 focus:ring-indigo-400 outline-none"
                placeholder="Ministerial Appointments 2026 - Q2"
              />
            </div>
            <div>
              <FieldLabel
                htmlFor="campaign-description"
                label="Description"
                help="Describe office scope, nomination context, and vetting policy notes for reviewers."
                className="mb-1 flex items-center gap-1.5"
                textClassName="block text-sm font-medium text-slate-700"
              />
              <textarea
                id="campaign-description"
                rows={3}
                value={form.description}
                onChange={(event) => setForm((prev) => ({ ...prev, description: event.target.value }))}
                className="w-full rounded-lg border border-slate-700 px-3 py-2 focus:ring-2 focus:ring-indigo-400 outline-none"
                placeholder="Describe this appointment exercise scope and rules."
              />
            </div>
            <div>
              <FieldLabel
                htmlFor="campaign-required-doc-types"
                label="Required Document Types"
                required
                help="Nominee dossiers can include only these document categories for this exercise."
                className="mb-2 flex items-center gap-1.5"
                textClassName="block text-sm font-medium text-slate-700"
              />
              <div
                id="campaign-required-doc-types"
                className="grid grid-cols-1 gap-2 rounded-lg border border-slate-200 bg-slate-50 p-3 sm:grid-cols-2"
              >
                {DOCUMENT_TYPE_OPTIONS.map((option) => {
                  const checked = form.required_document_types.includes(option.value);
                  return (
                    <label key={option.value} className="inline-flex items-center gap-2 text-sm text-slate-800">
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={(event) => {
                          const isChecked = event.target.checked;
                          setForm((prev) => {
                            const current = prev.required_document_types;
                            if (isChecked) {
                              if (current.includes(option.value)) {
                                return prev;
                              }
                              return {
                                ...prev,
                                required_document_types: [...current, option.value],
                              };
                            }
                            return {
                              ...prev,
                              required_document_types: current.filter((item) => item !== option.value),
                            };
                          });
                        }}
                      />
                      <span>{option.label}</span>
                    </label>
                  );
                })}
              </div>
              <p className="mt-2 text-xs text-slate-700">
                Selected: {form.required_document_types.length}
              </p>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div>
                <FieldLabel
                  htmlFor="campaign-starts-at"
                  label="Starts At"
                  help="Optional. Set when nomination vetting intake should begin for this exercise."
                  className="mb-1 flex items-center gap-1.5"
                  textClassName="block text-sm font-medium text-slate-700"
                />
                <Input
                  id="campaign-starts-at"
                  type="datetime-local"
                  value={form.starts_at}
                  onChange={(event) => setForm((prev) => ({ ...prev, starts_at: event.target.value }))}
                  className="w-full rounded-lg border border-slate-700 px-3 py-2 focus:ring-2 focus:ring-indigo-400 outline-none"
                />
              </div>
              <div>
                <FieldLabel
                  htmlFor="campaign-ends-at"
                  label="Ends At"
                  help="Optional. Use to enforce a cutoff date for submissions and interview activity."
                  className="mb-1 flex items-center gap-1.5"
                  textClassName="block text-sm font-medium text-slate-700"
                />
                <Input
                  id="campaign-ends-at"
                  type="datetime-local"
                  value={form.ends_at}
                  onChange={(event) => setForm((prev) => ({ ...prev, ends_at: event.target.value }))}
                  className="w-full rounded-lg border border-slate-700 px-3 py-2 focus:ring-2 focus:ring-indigo-400 outline-none"
                />
              </div>
            </div>
            <div>
              <FieldLabel
                htmlFor="campaign-status"
                label="Status"
                help="Draft keeps setup internal. Active allows ongoing operation. Closed/Archived indicate completed cycles."
                className="mb-1 flex items-center gap-1.5"
                textClassName="block text-sm font-medium text-slate-700"
              />
              <select
                title='appointment exercise status'
                id="campaign-status"
                value={form.status}
                onChange={(event) =>
                  setForm((prev) => ({ ...prev, status: event.target.value as VettingCampaign['status'] }))
                }
                className="w-full rounded-lg border border-slate-700 px-3 py-2 focus:ring-2 focus:ring-indigo-400 outline-none"
              >
                <option value="draft">Draft</option>
                <option value="active">Active</option>
                <option value="closed">Closed</option>
                <option value="archived">Archived</option>
              </select>
            </div>
            <button
              type="submit"
              disabled={submitting}
              className="w-full rounded-lg bg-indigo-600 text-white px-4 py-2 font-medium hover:bg-indigo-700 disabled:opacity-60"
            >
              {submitting ? 'Creating...' : 'Create Exercise'}
            </button>
          </form>
        </div>

        <div className="lg:col-span-3 rounded-xl border border-slate-200 bg-white p-5">
          <h2 className="text-lg font-semibold mb-4 inline-flex items-center gap-2">
            <FolderKanban className="w-5 h-5 text-indigo-600" />
            Exercise List
            <HelpTooltip text="Open Workspace to assign route rubric versions, import nominee pools, and manage invitation intake for an exercise." />
          </h2>

          <div className="mb-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div>
              <label htmlFor="campaign-list-search" className="mb-1 block text-xs font-semibold uppercase text-slate-700">
                Search
              </label>
              <Input
                id="campaign-list-search"
                value={campaignSearchFilter}
                onChange={(event) => setCampaignSearchFilter(event.target.value)}
                placeholder="Search name, description, owner"
              />
            </div>
            <div>
              <label htmlFor="campaign-list-status-filter" className="mb-1 block text-xs font-semibold uppercase text-slate-700">
                Status
              </label>
              <select
                id="campaign-list-status-filter"
                value={campaignStatusFilter}
                onChange={(event) => setCampaignStatusFilter(event.target.value as CampaignListStatusFilter)}
                className="w-full rounded-lg border border-slate-700 bg-white px-3 py-2 text-sm text-slate-900 focus:ring-2 focus:ring-indigo-400 outline-none"
              >
                <option value="all">All statuses</option>
                <option value="draft">Draft</option>
                <option value="active">Active</option>
                <option value="closed">Closed</option>
                <option value="archived">Archived</option>
              </select>
            </div>
          </div>

          {hasCampaignListFilters && (
            <div className="mb-4 rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-800">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-xs font-semibold uppercase tracking-wide text-slate-700">Active filters</span>
                {isCampaignSearchFilterActive && (
                  <button
                    type="button"
                    onClick={() => setCampaignSearchFilter('')}
                    className="inline-flex items-center rounded-full border border-slate-300 bg-slate-100 px-3 py-1 text-xs font-medium text-slate-800 hover:bg-slate-200"
                  >
                    Search: {campaignSearchFilter} x
                  </button>
                )}
                {isCampaignStatusFilterActive && (
                  <button
                    type="button"
                    onClick={() => setCampaignStatusFilter('all')}
                    className="inline-flex items-center rounded-full border border-slate-300 bg-slate-100 px-3 py-1 text-xs font-medium text-slate-800 hover:bg-slate-200"
                  >
                    Status: {campaignStatusFilter} x
                  </button>
                )}
                {isCampaignOfficeFilterActive && (
                  <button
                    type="button"
                    onClick={() => setOfficeFilter('')}
                    className="inline-flex items-center rounded-full border border-slate-300 bg-slate-100 px-3 py-1 text-xs font-medium text-slate-800 hover:bg-slate-200"
                  >
                    Office context x
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => {
                    setCampaignSearchFilter('');
                    setCampaignStatusFilter('all');
                    setOfficeFilter('');
                  }}
                  className="ml-auto inline-flex items-center rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-800 hover:bg-slate-100"
                >
                  Clear exercise filters
                </button>
              </div>
            </div>
          )}

          {loading ? (
            <div className="py-12 text-center text-slate-700">Loading appointment exercises...</div>
          ) : campaigns.length === 0 ? (
            <div className="py-12 text-center text-slate-700">No appointment exercises yet. Create your first one.</div>
          ) : filteredCampaigns.length === 0 ? (
            <div className="py-12 text-center text-slate-700">No appointment exercises match current filters.</div>
          ) : (
            <div className="space-y-3">
              {filteredCampaigns.map((campaign) => (
                <article
                  key={campaign.id}
                  className="rounded-lg border border-slate-200 px-4 py-3 hover:border-indigo-300 transition-colors"
                >
                  <div className="flex flex-wrap gap-3 items-center justify-between">
                    <div>
                      <h3 className="font-semibold text-slate-900">{campaign.name}</h3>
                      <p className="text-sm text-slate-700">
                        Created {formatDate(campaign.created_at)}
                        {campaign.initiated_by_email ? ` by ${campaign.initiated_by_email}` : ''}
                      </p>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      <span
                        className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-medium ${
                          statusBadgeClass[campaign.status] || 'bg-slate-200 text-slate-800'
                        }`}
                      >
                        {campaign.status}
                      </span>
                      {quotaBadge && (
                        <span
                          className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-medium ${quotaBadge.className}`}
                          title="Exercise monthly intake quota status"
                        >
                          {quotaBadge.label}
                        </span>
                      )}
                    </div>
                  </div>
                  {campaign.description && (
                    <p className="text-sm text-slate-700 mt-2 line-clamp-2">{campaign.description}</p>
                  )}
                  <p className="text-xs text-slate-700 mt-2">
                    Linked offices:{" "}
                    {(campaign.office_ids?.length ?? campaign.position_ids?.length ?? 0)}
                  </p>
                  {Array.isArray(campaign.required_document_types) && campaign.required_document_types.length > 0 && (
                    <p className="text-xs text-slate-700 mt-2">
                      Required docs:{" "}
                      {campaign.required_document_types.map((value) => getDocumentTypeLabel(value)).join(', ')}
                    </p>
                  )}
                  <div className="mt-3 flex items-center justify-between">
                    <div className="text-xs text-slate-700 inline-flex items-center gap-1">
                      <CalendarDays className="w-3.5 h-3.5" />
                      {campaign.starts_at ? formatDate(campaign.starts_at) : 'No start date'}
                    </div>
                    <div className="flex items-center gap-3">
                      <Link
                        to={`/government/appointments?exercise=${campaign.id}`}
                        className="text-xs text-cyan-700 hover:text-cyan-800 font-semibold"
                      >
                        Nomination Files
                      </Link>
                      <Link
                        to={`/applications?exercise=${campaign.id}`}
                        className="text-xs text-slate-700 hover:text-slate-900 font-semibold"
                      >
                        Vetting Dossiers
                      </Link>
                      <Link
                        to={`/campaigns/${campaign.id}`}
                        className="text-sm text-indigo-600 hover:text-indigo-700 font-medium"
                      >
                        Open Workspace
                      </Link>
                    </div>
                  </div>
                </article>
              ))}
            </div>
          )}
        </div>
      </section>
    </main>
  );
};

export default CampaignsPage;

