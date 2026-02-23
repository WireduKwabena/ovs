import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { Plus, FolderKanban, CalendarDays, RefreshCw } from 'lucide-react';
import type { VettingCampaign } from '@/types';
import { campaignService } from '@/services/campaign.service';
import { formatDate } from '@/utils/helper';
import { useAuth } from '@/hooks/useAuth';

const statusBadgeClass: Record<string, string> = {
  draft: 'bg-slate-100 text-slate-700',
  active: 'bg-emerald-100 text-emerald-700',
  closed: 'bg-amber-100 text-amber-700',
  archived: 'bg-zinc-100 text-zinc-700',
};

const CampaignsPage: React.FC = () => {
  const { isAdmin, userType } = useAuth();
  const [campaigns, setCampaigns] = useState<VettingCampaign[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [form, setForm] = useState({
    name: '',
    description: '',
    status: 'draft' as VettingCampaign['status'],
    starts_at: '',
    ends_at: '',
  });

  const canManageCampaigns = isAdmin || userType === 'hr_manager';

  const fetchCampaigns = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await campaignService.list();
      setCampaigns(data);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || 'Failed to load campaigns.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchCampaigns();
  }, [fetchCampaigns]);

  const totalByStatus = useMemo(() => {
    return campaigns.reduce(
      (acc, campaign) => {
        acc[campaign.status] = (acc[campaign.status] || 0) + 1;
        return acc;
      },
      {} as Record<string, number>
    );
  }, [campaigns]);

  const handleCreateCampaign = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!form.name.trim()) {
      setError('Campaign name is required.');
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
      });
      setCampaigns((prev) => [created, ...prev]);
      setForm({
        name: '',
        description: '',
        status: 'draft',
        starts_at: '',
        ends_at: '',
      });
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || 'Failed to create campaign.');
    } finally {
      setSubmitting(false);
    }
  };

  if (!canManageCampaigns) {
    return (
      <main className="max-w-4xl mx-auto px-4 py-10">
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-6 text-amber-800">
          Your account does not have campaign-management access.
        </div>
      </main>
    );
  }

  return (
    <main className="max-w-7xl mx-auto px-4 py-8 space-y-6">
      <section className="rounded-2xl bg-slate-900 text-white p-6">
        <div className="flex flex-wrap gap-4 items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold">Vetting Campaigns</h1>
            <p className="text-slate-300 mt-1">
              Create campaigns, onboard candidates, and monitor vetting progress.
            </p>
          </div>
          <button
            type="button"
            onClick={() => void fetchCampaigns()}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
            Refresh
          </button>
        </div>
      </section>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 text-red-700 px-4 py-3">
          {error}
        </div>
      )}

      <section className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <p className="text-sm text-slate-500">Total</p>
          <p className="text-2xl font-semibold">{campaigns.length}</p>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <p className="text-sm text-slate-500">Active</p>
          <p className="text-2xl font-semibold">{totalByStatus.active || 0}</p>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <p className="text-sm text-slate-500">Draft</p>
          <p className="text-2xl font-semibold">{totalByStatus.draft || 0}</p>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <p className="text-sm text-slate-500">Closed</p>
          <p className="text-2xl font-semibold">{totalByStatus.closed || 0}</p>
        </div>
      </section>

      <section className="grid grid-cols-1 lg:grid-cols-5 gap-6">
        <div className="lg:col-span-2 rounded-xl border border-slate-200 bg-white p-5">
          <h2 className="text-lg font-semibold mb-4 inline-flex items-center gap-2">
            <Plus className="w-5 h-5 text-indigo-600" />
            Create Campaign
          </h2>
          <form className="space-y-3" onSubmit={handleCreateCampaign}>
            <div>
              <label htmlFor="campaign-name" className="block text-sm font-medium text-slate-700 mb-1">
                Name
              </label>
              <input
                id="campaign-name"
                required
                value={form.name}
                onChange={(event) => setForm((prev) => ({ ...prev, name: event.target.value }))}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 focus:ring-2 focus:ring-indigo-400 outline-none"
                placeholder="2026 Graduate Vetting"
              />
            </div>
            <div>
              <label htmlFor="campaign-description" className="block text-sm font-medium text-slate-700 mb-1">
                Description
              </label>
              <textarea
                id="campaign-description"
                rows={3}
                value={form.description}
                onChange={(event) => setForm((prev) => ({ ...prev, description: event.target.value }))}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 focus:ring-2 focus:ring-indigo-400 outline-none"
                placeholder="Describe this campaign's scope and rules."
              />
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div>
                <label htmlFor="campaign-starts-at" className="block text-sm font-medium text-slate-700 mb-1">
                  Starts At
                </label>
                <input
                  id="campaign-starts-at"
                  type="datetime-local"
                  value={form.starts_at}
                  onChange={(event) => setForm((prev) => ({ ...prev, starts_at: event.target.value }))}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 focus:ring-2 focus:ring-indigo-400 outline-none"
                />
              </div>
              <div>
                <label htmlFor="campaign-ends-at" className="block text-sm font-medium text-slate-700 mb-1">
                  Ends At
                </label>
                <input
                  id="campaign-ends-at"
                  type="datetime-local"
                  value={form.ends_at}
                  onChange={(event) => setForm((prev) => ({ ...prev, ends_at: event.target.value }))}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 focus:ring-2 focus:ring-indigo-400 outline-none"
                />
              </div>
            </div>
            <div>
              <label htmlFor="campaign-status" className="block text-sm font-medium text-slate-700 mb-1">
                Status
              </label>
              <select
                id="campaign-status"
                value={form.status}
                onChange={(event) =>
                  setForm((prev) => ({ ...prev, status: event.target.value as VettingCampaign['status'] }))
                }
                className="w-full rounded-lg border border-slate-300 px-3 py-2 focus:ring-2 focus:ring-indigo-400 outline-none"
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
              {submitting ? 'Creating...' : 'Create Campaign'}
            </button>
          </form>
        </div>

        <div className="lg:col-span-3 rounded-xl border border-slate-200 bg-white p-5">
          <h2 className="text-lg font-semibold mb-4 inline-flex items-center gap-2">
            <FolderKanban className="w-5 h-5 text-indigo-600" />
            Campaign List
          </h2>

          {loading ? (
            <div className="py-12 text-center text-slate-500">Loading campaigns...</div>
          ) : campaigns.length === 0 ? (
            <div className="py-12 text-center text-slate-500">No campaigns yet. Create your first one.</div>
          ) : (
            <div className="space-y-3">
              {campaigns.map((campaign) => (
                <article
                  key={campaign.id}
                  className="rounded-lg border border-slate-200 px-4 py-3 hover:border-indigo-300 transition-colors"
                >
                  <div className="flex flex-wrap gap-3 items-center justify-between">
                    <div>
                      <h3 className="font-semibold text-slate-900">{campaign.name}</h3>
                      <p className="text-sm text-slate-500">
                        Created {formatDate(campaign.created_at)}
                        {campaign.initiated_by_email ? ` by ${campaign.initiated_by_email}` : ''}
                      </p>
                    </div>
                    <span
                      className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-medium ${
                        statusBadgeClass[campaign.status] || 'bg-slate-100 text-slate-700'
                      }`}
                    >
                      {campaign.status}
                    </span>
                  </div>
                  {campaign.description && (
                    <p className="text-sm text-slate-600 mt-2 line-clamp-2">{campaign.description}</p>
                  )}
                  <div className="mt-3 flex items-center justify-between">
                    <div className="text-xs text-slate-500 inline-flex items-center gap-1">
                      <CalendarDays className="w-3.5 h-3.5" />
                      {campaign.starts_at ? formatDate(campaign.starts_at) : 'No start date'}
                    </div>
                    <Link
                      to={`/campaigns/${campaign.id}`}
                      className="text-sm text-indigo-600 hover:text-indigo-700 font-medium"
                    >
                      Open Workspace
                    </Link>
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
