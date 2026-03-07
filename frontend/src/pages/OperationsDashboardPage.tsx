import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import {
  FolderKanban,
  Users2,
  UserCheck2,
  UserX2,
  FileClock,
  ArrowUpRight,
  RefreshCw,
  Activity,
  Download,
  Link2,
  Video,
} from 'lucide-react';
import { toast } from 'react-toastify';
import { campaignService } from '@/services/campaign.service';
import type { CampaignDashboard, VettingCampaign } from '@/types';
import { downloadCsvFile, isoDateStamp } from '@/utils/csv';
import { downloadJsonFile } from '@/utils/json';
import { formatDate } from '@/utils/helper';
import { useAuth } from '@/hooks/useAuth';
import { getUserDisplayName } from '@/utils/userDisplay';

interface CampaignWithMetrics {
  campaign: VettingCampaign;
  metrics: CampaignDashboard;
}

type DashboardStatusFilter = 'all' | VettingCampaign['status'];
type DashboardWindowFilter = 'all' | '30' | '90' | '365';
type DashboardChartMode = 'count' | 'percentage';
type FilterPresetId = 'all' | 'active_30' | 'active_90' | 'draft_only' | 'archived_365';
type CampaignPulseSort = 'recent' | 'oldest' | 'completion' | 'approval' | 'in_progress';
interface SavedDashboardView {
  id: string;
  name: string;
  status: DashboardStatusFilter;
  window: DashboardWindowFilter;
  mode: DashboardChartMode;
  sort: CampaignPulseSort;
  query: string;
  created_at: string;
}

interface PendingQuerySync {
  from: string;
  to: string;
}

const STATUS_FILTER_OPTIONS: DashboardStatusFilter[] = ['all', 'draft', 'active', 'closed', 'archived'];
const WINDOW_FILTER_OPTIONS: DashboardWindowFilter[] = ['all', '30', '90', '365'];
const CHART_MODE_OPTIONS: DashboardChartMode[] = ['count', 'percentage'];
const SAVED_VIEWS_STORAGE_KEY = 'ovs.operations_dashboard.saved_views.v1';
const MAX_SAVED_VIEWS = 8;
const CAMPAIGN_PULSE_SORT_OPTIONS: Array<{ value: CampaignPulseSort; label: string }> = [
  { value: 'recent', label: 'Most Recent' },
  { value: 'oldest', label: 'Oldest' },
  { value: 'completion', label: 'Completion Rate' },
  { value: 'approval', label: 'Approval Rate' },
  { value: 'in_progress', label: 'In Progress' },
];

const statusPillClass: Record<string, string> = {
  draft: 'bg-slate-200 text-slate-800',
  active: 'bg-teal-100 text-teal-700',
  closed: 'bg-amber-100 text-amber-700',
  archived: 'bg-zinc-100 text-zinc-700',
};

const emptyMetrics: CampaignDashboard = {
  total_candidates: 0,
  invited: 0,
  registered: 0,
  in_progress: 0,
  completed: 0,
  reviewed: 0,
  approved: 0,
  rejected: 0,
  escalated: 0,
};

const FILTER_PRESETS: Array<{
  id: FilterPresetId;
  label: string;
  status: DashboardStatusFilter;
  window: DashboardWindowFilter;
}> = [
  { id: 'all', label: 'All Campaigns', status: 'all', window: 'all' },
  { id: 'active_30', label: 'Active 30d', status: 'active', window: '30' },
  { id: 'active_90', label: 'Active 90d', status: 'active', window: '90' },
  { id: 'draft_only', label: 'Drafts Only', status: 'draft', window: 'all' },
  { id: 'archived_365', label: 'Archived 1y', status: 'archived', window: '365' },
];

const isDashboardStatusFilter = (value: string): value is DashboardStatusFilter =>
  STATUS_FILTER_OPTIONS.includes(value as DashboardStatusFilter);

const isDashboardWindowFilter = (value: string): value is DashboardWindowFilter =>
  WINDOW_FILTER_OPTIONS.includes(value as DashboardWindowFilter);

const isDashboardChartMode = (value: string): value is DashboardChartMode =>
  CHART_MODE_OPTIONS.includes(value as DashboardChartMode);

const isCampaignPulseSort = (value: string): value is CampaignPulseSort =>
  CAMPAIGN_PULSE_SORT_OPTIONS.some((option) => option.value === value);

const loadSavedDashboardViews = (): SavedDashboardView[] => {
  if (typeof window === 'undefined') {
    return [];
  }

  try {
    const raw = window.localStorage.getItem(SAVED_VIEWS_STORAGE_KEY);
    if (!raw) {
      return [];
    }

    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) {
      return [];
    }

    const normalizedViews: SavedDashboardView[] = [];

    for (const item of parsed) {
      if (!item || typeof item !== 'object') {
        continue;
      }
      if (typeof item.id !== 'string' || typeof item.name !== 'string') {
        continue;
      }
      if (!isDashboardStatusFilter(String(item.status))) {
        continue;
      }
      if (!isDashboardWindowFilter(String(item.window))) {
        continue;
      }
      if (!isDashboardChartMode(String(item.mode))) {
        continue;
      }
      if (typeof item.query !== 'string') {
        continue;
      }
      if (typeof item.created_at !== 'string') {
        continue;
      }

      normalizedViews.push({
        id: item.id,
        name: item.name,
        status: item.status,
        window: item.window,
        mode: item.mode,
        sort: isCampaignPulseSort(String(item.sort)) ? item.sort : 'recent',
        query: item.query,
        created_at: item.created_at,
      });

      if (normalizedViews.length >= MAX_SAVED_VIEWS) {
        break;
      }
    }

    return normalizedViews;
  } catch {
    return [];
  }
};

const persistSavedDashboardViews = (views: SavedDashboardView[]) => {
  if (typeof window === 'undefined') {
    return;
  }

  try {
    window.localStorage.setItem(SAVED_VIEWS_STORAGE_KEY, JSON.stringify(views));
  } catch {
    // Ignore storage write failures and keep runtime state only.
  }
};

const createSavedViewId = () => {
  if (typeof window !== 'undefined' && window.crypto?.randomUUID) {
    return window.crypto.randomUUID();
  }

  return `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
};

const OperationsDashboardChartsSection = React.lazy(
  () => import('@/components/admin/OperationsDashboardChartsSection')
);

const OperationsDashboardPage: React.FC = () => {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const { user } = useAuth();
  const chartsSectionTriggerRef = useRef<HTMLDivElement | null>(null);
  const pendingQuerySyncRef = useRef<PendingQuerySync | null>(null);

  const statusFromQuery = (searchParams.get('status') || 'all') as DashboardStatusFilter;
  const windowFromQuery = (searchParams.get('window') || 'all') as DashboardWindowFilter;
  const modeFromQuery = (searchParams.get('mode') || 'count') as DashboardChartMode;
  const pulseFromQuery = (searchParams.get('pulse') || 'recent') as CampaignPulseSort;
  const queryFromQuery = searchParams.get('q') || '';
  const currentQueryString = searchParams.toString();

  const [campaignStats, setCampaignStats] = useState<CampaignWithMetrics[]>([]);
  const [statusFilter, setStatusFilter] = useState<DashboardStatusFilter>(
    isDashboardStatusFilter(statusFromQuery) ? statusFromQuery : 'all'
  );
  const [windowFilter, setWindowFilter] = useState<DashboardWindowFilter>(
    isDashboardWindowFilter(windowFromQuery) ? windowFromQuery : 'all'
  );
  const [searchQuery, setSearchQuery] = useState(queryFromQuery);
  const [chartMode, setChartMode] = useState<DashboardChartMode>(
    isDashboardChartMode(modeFromQuery) ? modeFromQuery : 'count'
  );
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [linkCopied, setLinkCopied] = useState(false);
  const [isCopyingLink, setIsCopyingLink] = useState(false);
  const [applyingPresetId, setApplyingPresetId] = useState<FilterPresetId | null>(null);
  const [isClearingFilters, setIsClearingFilters] = useState(false);
  const [savedViews, setSavedViews] = useState<SavedDashboardView[]>([]);
  const [savedViewName, setSavedViewName] = useState('');
  const [isSavingView, setIsSavingView] = useState(false);
  const [applyingViewId, setApplyingViewId] = useState<string | null>(null);
  const [removingViewId, setRemovingViewId] = useState<string | null>(null);
  const [sharingViewId, setSharingViewId] = useState<string | null>(null);
  const [campaignPulseSort, setCampaignPulseSort] = useState<CampaignPulseSort>(
    isCampaignPulseSort(pulseFromQuery) ? pulseFromQuery : 'recent'
  );
  const [shouldLoadCharts, setShouldLoadCharts] = useState(false);

  const loadDashboard = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const campaignsData = await campaignService.list();

      const dashboards = await Promise.all(
        campaignsData.map(async (campaign) => {
          try {
            const metrics = await campaignService.getDashboard(campaign.id);
            return { campaign, metrics };
          } catch {
            return { campaign, metrics: emptyMetrics };
          }
        })
      );

      setCampaignStats(dashboards);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || 'Failed to load operations dashboard.');
      setCampaignStats([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadDashboard();
  }, [loadDashboard]);

  useEffect(() => {
    setSavedViews(loadSavedDashboardViews());
  }, []);

  useEffect(() => {
    if (shouldLoadCharts) {
      return;
    }
    if (typeof window === 'undefined') {
      return;
    }
    if (!('IntersectionObserver' in window)) {
      setShouldLoadCharts(true);
      return;
    }

    const target = chartsSectionTriggerRef.current;
    if (!target) {
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          setShouldLoadCharts(true);
          observer.disconnect();
        }
      },
      { rootMargin: '280px 0px' }
    );

    observer.observe(target);
    return () => observer.disconnect();
  }, [shouldLoadCharts]);

  useEffect(() => {
    const nextParams = new URLSearchParams(currentQueryString);

    if (searchQuery.trim()) {
      nextParams.set('q', searchQuery.trim());
    } else {
      nextParams.delete('q');
    }

    if (statusFilter !== 'all') {
      nextParams.set('status', statusFilter);
    } else {
      nextParams.delete('status');
    }

    if (windowFilter !== 'all') {
      nextParams.set('window', windowFilter);
    } else {
      nextParams.delete('window');
    }

    if (chartMode !== 'count') {
      nextParams.set('mode', chartMode);
    } else {
      nextParams.delete('mode');
    }

    if (campaignPulseSort !== 'recent') {
      nextParams.set('pulse', campaignPulseSort);
    } else {
      nextParams.delete('pulse');
    }

    const nextQueryString = nextParams.toString();
    if (nextQueryString !== currentQueryString) {
      const pendingSync = pendingQuerySyncRef.current;
      if (
        pendingSync &&
        pendingSync.from === currentQueryString &&
        pendingSync.to === nextQueryString
      ) {
        return;
      }
      pendingQuerySyncRef.current = { from: currentQueryString, to: nextQueryString };
      setSearchParams(nextParams, { replace: true });
    }
  }, [
    campaignPulseSort,
    chartMode,
    currentQueryString,
    searchQuery,
    setSearchParams,
    statusFilter,
    windowFilter,
  ]);

  useEffect(() => {
    const queryString = searchParams.toString();
    const pendingSync = pendingQuerySyncRef.current;
    if (pendingSync) {
      if (queryString === pendingSync.from) {
        return;
      }
      if (queryString === pendingSync.to) {
        pendingQuerySyncRef.current = null;
        return;
      }
      pendingQuerySyncRef.current = null;
    }

    const nextStatus = (searchParams.get('status') || 'all') as DashboardStatusFilter;
    const nextWindow = (searchParams.get('window') || 'all') as DashboardWindowFilter;
    const nextMode = (searchParams.get('mode') || 'count') as DashboardChartMode;
    const nextPulse = (searchParams.get('pulse') || 'recent') as CampaignPulseSort;
    const nextQuery = searchParams.get('q') || '';

    const validatedStatus: DashboardStatusFilter = isDashboardStatusFilter(nextStatus) ? nextStatus : 'all';
    const validatedWindow: DashboardWindowFilter = isDashboardWindowFilter(nextWindow) ? nextWindow : 'all';
    const validatedMode: DashboardChartMode = isDashboardChartMode(nextMode) ? nextMode : 'count';
    const validatedPulse: CampaignPulseSort = isCampaignPulseSort(nextPulse) ? nextPulse : 'recent';

    if (validatedStatus !== statusFilter) {
      setStatusFilter(validatedStatus);
    }
    if (validatedWindow !== windowFilter) {
      setWindowFilter(validatedWindow);
    }
    if (validatedMode !== chartMode) {
      setChartMode(validatedMode);
    }
    if (validatedPulse !== campaignPulseSort) {
      setCampaignPulseSort(validatedPulse);
    }
    if (nextQuery !== searchQuery) {
      setSearchQuery(nextQuery);
    }
  }, [campaignPulseSort, chartMode, searchParams, searchQuery, statusFilter, windowFilter]);

  const persistViews = useCallback((views: SavedDashboardView[]) => {
    setSavedViews(views);
    persistSavedDashboardViews(views);
  }, []);

  const activeSavedViewId = useMemo(() => {
    return (
      savedViews.find(
        (view) =>
          view.status === statusFilter &&
          view.window === windowFilter &&
          view.mode === chartMode &&
          view.sort === campaignPulseSort &&
          view.query.trim() === searchQuery.trim()
      )?.id ?? null
    );
  }, [campaignPulseSort, chartMode, savedViews, searchQuery, statusFilter, windowFilter]);

  const isSavedViewActionBusy = Boolean(applyingViewId || removingViewId || sharingViewId);

  const applySavedView = useCallback(
    (view: SavedDashboardView) => {
      if (isSavedViewActionBusy) {
        return;
      }

      setApplyingViewId(view.id);
      try {
        setStatusFilter(view.status);
        setWindowFilter(view.window);
        setChartMode(view.mode);
        setCampaignPulseSort(view.sort);
        setSearchQuery(view.query);
      } finally {
        window.setTimeout(() => setApplyingViewId(null), 180);
      }
    },
    [isSavedViewActionBusy]
  );

  const removeSavedView = useCallback(
    (viewId: string) => {
      if (isSavedViewActionBusy) {
        return;
      }

      setRemovingViewId(viewId);
      try {
        const nextViews = savedViews.filter((view) => view.id !== viewId);
        persistViews(nextViews);
        if (nextViews.length < savedViews.length) {
          toast.info('Saved view removed.');
        }
      } finally {
        window.setTimeout(() => setRemovingViewId(null), 180);
      }
    },
    [isSavedViewActionBusy, persistViews, savedViews]
  );

  const saveCurrentView = useCallback(() => {
    if (isSavingView || isSavedViewActionBusy) {
      return;
    }

    const normalizedName = savedViewName.trim();
    if (!normalizedName) {
      toast.error('Enter a view name first.');
      return;
    }

    setIsSavingView(true);

    try {
      const duplicateIndex = savedViews.findIndex(
        (view) => view.name.toLowerCase() === normalizedName.toLowerCase()
      );

      const view: SavedDashboardView = {
        id: duplicateIndex >= 0 ? savedViews[duplicateIndex].id : createSavedViewId(),
        name: normalizedName,
        status: statusFilter,
        window: windowFilter,
        mode: chartMode,
        sort: campaignPulseSort,
        query: searchQuery.trim(),
        created_at: new Date().toISOString(),
      };

      const nonDuplicateViews =
        duplicateIndex >= 0
          ? savedViews.filter((item) => item.id !== savedViews[duplicateIndex].id)
          : savedViews;

      const nextViews = [view, ...nonDuplicateViews].slice(0, MAX_SAVED_VIEWS);
      persistViews(nextViews);
      setSavedViewName('');
      toast.success(duplicateIndex >= 0 ? `Updated "${normalizedName}".` : `Saved "${normalizedName}".`);
    } finally {
      setIsSavingView(false);
    }
  }, [
    campaignPulseSort,
    chartMode,
    isSavingView,
    isSavedViewActionBusy,
    persistViews,
    savedViewName,
    savedViews,
    searchQuery,
    statusFilter,
    windowFilter,
  ]);

  const filteredCampaignStats = useMemo(() => {
    const normalizedQuery = searchQuery.trim().toLowerCase();
    const maxAgeDays = windowFilter === 'all' ? null : Number(windowFilter);
    const nowMs = Date.now();

    return campaignStats.filter(({ campaign }) => {
      if (statusFilter !== 'all' && campaign.status !== statusFilter) {
        return false;
      }

      if (maxAgeDays !== null) {
        const createdMs = new Date(campaign.created_at).getTime();
        const ageMs = nowMs - createdMs;
        if (Number.isNaN(createdMs) || ageMs > maxAgeDays * 24 * 60 * 60 * 1000) {
          return false;
        }
      }

      if (normalizedQuery) {
        const haystack = `${campaign.name} ${campaign.description || ''} ${campaign.initiated_by_email || ''}`.toLowerCase();
        if (!haystack.includes(normalizedQuery)) {
          return false;
        }
      }

      return true;
    });
  }, [campaignStats, searchQuery, statusFilter, windowFilter]);

  const activePresetId = useMemo(() => {
    if (searchQuery.trim()) {
      return null;
    }
    const match = FILTER_PRESETS.find(
      (preset) => preset.status === statusFilter && preset.window === windowFilter
    );
    return match ? match.id : null;
  }, [searchQuery, statusFilter, windowFilter]);

  const isFilterActionBusy = Boolean(applyingPresetId || isClearingFilters);

  const applyPreset = useCallback(
    (presetId: FilterPresetId) => {
      if (isFilterActionBusy) {
        return;
      }

      const preset = FILTER_PRESETS.find((item) => item.id === presetId);
      if (!preset) {
        return;
      }

      setApplyingPresetId(preset.id);
      try {
        setStatusFilter(preset.status);
        setWindowFilter(preset.window);
        setSearchQuery('');
      } finally {
        window.setTimeout(() => setApplyingPresetId(null), 180);
      }
    },
    [isFilterActionBusy]
  );

  const clearFilters = useCallback(() => {
    if (isFilterActionBusy) {
      return;
    }

    setIsClearingFilters(true);
    try {
      setSearchQuery('');
      setStatusFilter('all');
      setWindowFilter('all');
    } finally {
      window.setTimeout(() => setIsClearingFilters(false), 180);
    }
  }, [isFilterActionBusy]);

  const aggregate = useMemo(() => {
    return filteredCampaignStats.reduce(
      (acc, item) => {
        const metrics = item.metrics;
        acc.totalCandidates += metrics.total_candidates;
        acc.invited += metrics.invited;
        acc.registered += metrics.registered;
        acc.inProgress += metrics.in_progress;
        acc.completed += metrics.completed;
        acc.reviewed += metrics.reviewed;
        acc.approved += metrics.approved;
        acc.rejected += metrics.rejected;
        acc.escalated += metrics.escalated;
        return acc;
      },
      {
        totalCandidates: 0,
        invited: 0,
        registered: 0,
        inProgress: 0,
        completed: 0,
        reviewed: 0,
        approved: 0,
        rejected: 0,
        escalated: 0,
      }
    );
  }, [filteredCampaignStats]);

  const pipelineRate = useMemo(() => {
    if (aggregate.totalCandidates === 0) {
      return { completion: '0.0', approval: '0.0' };
    }
    const completion = (aggregate.completed / aggregate.totalCandidates) * 100;
    const approval = (aggregate.approved / aggregate.totalCandidates) * 100;
    return {
      completion: completion.toFixed(1),
      approval: approval.toFixed(1),
    };
  }, [aggregate]);

  const activeCampaigns = useMemo(() => {
    return filteredCampaignStats.filter((row) => row.campaign.status === 'active').length;
  }, [filteredCampaignStats]);

  const campaignPulseRows = useMemo(() => {
    const createdAtMs = (value: string) => {
      const ms = new Date(value).getTime();
      return Number.isNaN(ms) ? 0 : ms;
    };

    const completionRate = (row: CampaignWithMetrics) => {
      const total = row.metrics.total_candidates;
      if (total <= 0) {
        return 0;
      }
      return row.metrics.completed / total;
    };

    const approvalRate = (row: CampaignWithMetrics) => {
      const total = row.metrics.total_candidates;
      if (total <= 0) {
        return 0;
      }
      return row.metrics.approved / total;
    };

    return [...filteredCampaignStats]
      .sort((left, right) => {
        if (campaignPulseSort === 'oldest') {
          return createdAtMs(left.campaign.created_at) - createdAtMs(right.campaign.created_at);
        }
        if (campaignPulseSort === 'completion') {
          const diff = completionRate(right) - completionRate(left);
          if (diff !== 0) {
            return diff;
          }
          return createdAtMs(right.campaign.created_at) - createdAtMs(left.campaign.created_at);
        }
        if (campaignPulseSort === 'approval') {
          const diff = approvalRate(right) - approvalRate(left);
          if (diff !== 0) {
            return diff;
          }
          return createdAtMs(right.campaign.created_at) - createdAtMs(left.campaign.created_at);
        }
        if (campaignPulseSort === 'in_progress') {
          const diff = right.metrics.in_progress - left.metrics.in_progress;
          if (diff !== 0) {
            return diff;
          }
          return createdAtMs(right.campaign.created_at) - createdAtMs(left.campaign.created_at);
        }

        return createdAtMs(right.campaign.created_at) - createdAtMs(left.campaign.created_at);
      })
      .slice(0, 8);
  }, [campaignPulseSort, filteredCampaignStats]);

  const throughputChartData = useMemo(() => {
    return filteredCampaignStats.slice(0, 8).map((row) => ({
      name:
        row.campaign.name.length > 16 ? `${row.campaign.name.slice(0, 16)}...` : row.campaign.name,
      total_candidates: row.metrics.total_candidates,
      invited: row.metrics.invited,
      in_progress: row.metrics.in_progress,
      completed: row.metrics.completed,
      approved: row.metrics.approved,
    }));
  }, [filteredCampaignStats]);

  const throughputDisplayData = useMemo(() => {
    if (chartMode === 'count') {
      return throughputChartData;
    }
    return throughputChartData.map((row) => {
      const denominator = row.total_candidates > 0 ? row.total_candidates : 1;
      return {
        ...row,
        invited: Number(((row.invited / denominator) * 100).toFixed(2)),
        in_progress: Number(((row.in_progress / denominator) * 100).toFixed(2)),
        completed: Number(((row.completed / denominator) * 100).toFixed(2)),
        approved: Number(((row.approved / denominator) * 100).toFixed(2)),
      };
    });
  }, [chartMode, throughputChartData]);

  const pipelineMixData = useMemo(() => {
    return [
      { name: 'Invited', value: aggregate.invited, fill: '#38bdf8' },
      { name: 'Registered', value: aggregate.registered, fill: '#6366f1' },
      { name: 'In Progress', value: aggregate.inProgress, fill: '#f59e0b' },
      { name: 'Completed', value: aggregate.completed, fill: '#14b8a6' },
      { name: 'Reviewed', value: aggregate.reviewed, fill: '#0ea5a4' },
    ].filter((row) => row.value > 0);
  }, [aggregate]);

  const decisionMixData = useMemo(() => {
    return [
      { name: 'Approved', value: aggregate.approved, fill: '#10b981' },
      { name: 'Rejected', value: aggregate.rejected, fill: '#f43f5e' },
      { name: 'Escalated', value: aggregate.escalated, fill: '#f59e0b' },
    ].filter((row) => row.value > 0);
  }, [aggregate]);

  const pipelineMixDisplayData = useMemo(() => {
    if (chartMode === 'count') {
      return pipelineMixData.map((row) => ({ ...row, raw: row.value }));
    }
    const total = pipelineMixData.reduce((sum, row) => sum + row.value, 0);
    return pipelineMixData.map((row) => ({
      ...row,
      raw: row.value,
      value: total > 0 ? Number(((row.value / total) * 100).toFixed(2)) : 0,
    }));
  }, [chartMode, pipelineMixData]);

  const decisionMixDisplayData = useMemo(() => {
    if (chartMode === 'count') {
      return decisionMixData.map((row) => ({ ...row, raw: row.value }));
    }
    const total = decisionMixData.reduce((sum, row) => sum + row.value, 0);
    return decisionMixData.map((row) => ({
      ...row,
      raw: row.value,
      value: total > 0 ? Number(((row.value / total) * 100).toFixed(2)) : 0,
    }));
  }, [chartMode, decisionMixData]);

  const exportCampaignCsv = useCallback(() => {
    if (filteredCampaignStats.length === 0) {
      return;
    }

    const headers = [
      'campaign_id',
      'campaign_name',
      'status',
      'created_at',
      'initiated_by_email',
      'total_candidates',
      'invited',
      'registered',
      'in_progress',
      'completed',
      'reviewed',
      'approved',
      'rejected',
      'escalated',
    ];

    const rows = filteredCampaignStats.map((row) => [
      row.campaign.id,
      row.campaign.name,
      row.campaign.status,
      row.campaign.created_at,
      row.campaign.initiated_by_email || '',
      row.metrics.total_candidates,
      row.metrics.invited,
      row.metrics.registered,
      row.metrics.in_progress,
      row.metrics.completed,
      row.metrics.reviewed,
      row.metrics.approved,
      row.metrics.rejected,
      row.metrics.escalated,
    ]);

    downloadCsvFile(headers, rows, `campaign-dashboard-${isoDateStamp()}.csv`);
  }, [filteredCampaignStats]);

  const exportCampaignJson = useCallback(() => {
    if (filteredCampaignStats.length === 0) {
      return;
    }

    downloadJsonFile(
      {
        exported_at: new Date().toISOString(),
        filters: {
          status: statusFilter,
          window: windowFilter,
          mode: chartMode,
          pulse: campaignPulseSort,
          query: searchQuery,
        },
        aggregate,
        pipeline_mix: pipelineMixDisplayData,
        decision_mix: decisionMixDisplayData,
        total_rows: filteredCampaignStats.length,
        campaigns: filteredCampaignStats,
      },
      `campaign-dashboard-${isoDateStamp()}.json`,
    );
  }, [
    aggregate,
    campaignPulseSort,
    chartMode,
    decisionMixDisplayData,
    filteredCampaignStats,
    pipelineMixDisplayData,
    searchQuery,
    statusFilter,
    windowFilter,
  ]);

  const copyTextToClipboard = useCallback(async (text: string) => {
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(text);
      } else {
        const input = document.createElement('textarea');
        input.value = text;
        input.setAttribute('readonly', '');
        input.style.position = 'absolute';
        input.style.left = '-9999px';
        document.body.appendChild(input);
        input.select();
        document.execCommand('copy');
        document.body.removeChild(input);
      }
      return true;
    } catch {
      return false;
    }
  }, []);

  const buildDashboardShareUrl = useCallback(
    (params: {
      status: DashboardStatusFilter;
      window: DashboardWindowFilter;
      mode: DashboardChartMode;
      pulse: CampaignPulseSort;
      query: string;
    }) => {
      const url = new URL(window.location.href);
      const nextParams = new URLSearchParams();

      if (params.query.trim()) {
        nextParams.set('q', params.query.trim());
      }
      if (params.status !== 'all') {
        nextParams.set('status', params.status);
      }
      if (params.window !== 'all') {
        nextParams.set('window', params.window);
      }
      if (params.mode !== 'count') {
        nextParams.set('mode', params.mode);
      }
      if (params.pulse !== 'recent') {
        nextParams.set('pulse', params.pulse);
      }

      url.search = nextParams.toString();
      return url.toString();
    },
    []
  );

  const copyShareLink = useCallback(async () => {
    if (isCopyingLink) {
      return;
    }

    setIsCopyingLink(true);
    const url = buildDashboardShareUrl({
      status: statusFilter,
      window: windowFilter,
      mode: chartMode,
      pulse: campaignPulseSort,
      query: searchQuery,
    });
    try {
      const copied = await copyTextToClipboard(url);
      if (copied) {
        setLinkCopied(true);
        window.setTimeout(() => setLinkCopied(false), 1800);
      } else {
        setLinkCopied(false);
      }
    } finally {
      setIsCopyingLink(false);
    }
  }, [
    buildDashboardShareUrl,
    campaignPulseSort,
    chartMode,
    copyTextToClipboard,
    isCopyingLink,
    searchQuery,
    statusFilter,
    windowFilter,
  ]);

  const copySavedViewLink = useCallback(
    async (view: SavedDashboardView) => {
      if (isSavedViewActionBusy) {
        return;
      }

      setSharingViewId(view.id);
      const url = buildDashboardShareUrl({
        status: view.status,
        window: view.window,
        mode: view.mode,
        pulse: view.sort,
        query: view.query,
      });
      try {
        const copied = await copyTextToClipboard(url);
        if (copied) {
          toast.success(`Link copied for "${view.name}".`);
        } else {
          toast.error('Failed to copy link.');
        }
      } finally {
        setSharingViewId(null);
      }
    },
    [buildDashboardShareUrl, copyTextToClipboard, isSavedViewActionBusy]
  );

  const displayName = getUserDisplayName(user, 'Team');

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-10">
        <div className="rounded-2xl border border-slate-200 bg-white p-10 text-center text-slate-700">
          Loading operations dashboard...
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 py-8 space-y-6">
      <section className="rounded-2xl bg-linear-to-br from-slate-900 via-slate-800 to-teal-900 text-white p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold">Operations Dashboard</h1>
            <p className="text-slate-200 mt-1">
              Welcome, {displayName}. Campaign performance and candidate pipeline are summarized here.
            </p>
          </div>
          <div className="flex w-full flex-wrap items-center gap-2 lg:w-auto lg:flex-nowrap">
            <button
              type="button"
              onClick={() => void loadDashboard()}
              className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-slate-800/80 px-4 py-2 text-sm hover:bg-slate-700/80 sm:w-auto"
            >
              <RefreshCw className="w-4 h-4" />
              Refresh
            </button>
            <button
              type="button"
              onClick={exportCampaignCsv}
              disabled={filteredCampaignStats.length === 0}
              className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-slate-800/80 px-4 py-2 text-sm hover:bg-slate-700/80 disabled:opacity-50 disabled:cursor-not-allowed sm:w-auto"
            >
              <Download className="w-4 h-4" />
              Export CSV
            </button>
            <button
              type="button"
              onClick={exportCampaignJson}
              disabled={filteredCampaignStats.length === 0}
              className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-slate-800/80 px-4 py-2 text-sm hover:bg-slate-700/80 disabled:opacity-50 disabled:cursor-not-allowed sm:w-auto"
            >
              <Download className="w-4 h-4" />
              Export JSON
            </button>
            <button
              type="button"
              onClick={() => void copyShareLink()}
              disabled={isCopyingLink}
              className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-slate-800/80 px-4 py-2 text-sm hover:bg-slate-700/80 disabled:cursor-not-allowed disabled:opacity-60 sm:w-auto"
            >
              <Link2 className="w-4 h-4" />
              {isCopyingLink ? 'Copying...' : linkCopied ? 'Link Copied' : 'Copy Link'}
            </button>
            <Link
              to="/campaigns"
              className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-teal-500 px-4 py-2 text-sm font-medium text-slate-900 hover:bg-teal-400 sm:w-auto"
            >
              Manage Campaigns
              <ArrowUpRight className="w-4 h-4" />
            </Link>
            <Link
              to="/video-calls"
              className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-indigo-500 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-400 sm:w-auto"
            >
              Video Calls
              <Video className="w-4 h-4" />
            </Link>
          </div>
        </div>
      </section>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-red-700">{error}</div>
      )}

      <section className="rounded-xl border border-slate-200 bg-white p-5">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
          <h2 className="text-lg font-semibold">Analytics Filters</h2>
          <button
            type="button"
            onClick={clearFilters}
            disabled={isFilterActionBusy}
            className="text-sm text-indigo-600 hover:text-indigo-700 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isClearingFilters ? 'Clearing...' : 'Clear filters'}
          </button>
        </div>
        <div className="mb-3 flex flex-wrap gap-2">
          {FILTER_PRESETS.map((preset) => {
            const isActive = activePresetId === preset.id;
            const isApplyingThisPreset = applyingPresetId === preset.id;
            return (
              <button
                key={preset.id}
                type="button"
                onClick={() => applyPreset(preset.id)}
                disabled={isFilterActionBusy}
                className={`px-3 py-1.5 rounded-full text-xs border transition-colors disabled:cursor-not-allowed disabled:opacity-60 ${
                  isActive
                    ? 'border-teal-300 bg-teal-50 text-teal-700'
                    : 'border-slate-700 bg-white text-slate-700 hover:bg-slate-100'
                }`}
              >
                {isApplyingThisPreset ? 'Applying...' : preset.label}
              </button>
            );
          })}
        </div>
        <div className="mb-4 rounded-lg border border-slate-200 bg-slate-50 p-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h3 className="text-sm font-semibold text-slate-700">Saved Views</h3>
            <p className="text-xs text-slate-700">
              {savedViews.length}/{MAX_SAVED_VIEWS} saved
            </p>
          </div>
          <div className="mt-2 flex flex-wrap gap-2">
            {savedViews.length === 0 ? (
              <p className="text-xs text-slate-700">No saved views yet. Save current filters to reuse later.</p>
            ) : (
              savedViews.map((view) => {
                const isActive = activeSavedViewId === view.id;
                const isApplyingThisView = applyingViewId === view.id;
                const isRemovingThisView = removingViewId === view.id;
                const isSharingThisView = sharingViewId === view.id;
                return (
                  <div key={view.id} className="inline-flex items-center overflow-hidden rounded-full border border-slate-700 bg-white">
                    <button
                      type="button"
                      onClick={() => applySavedView(view)}
                      disabled={isSavedViewActionBusy}
                      className={`px-3 py-1.5 text-xs disabled:cursor-not-allowed disabled:opacity-60 ${isActive ? 'bg-teal-100 text-teal-800' : 'text-slate-700 hover:bg-slate-100'}`}
                    >
                      {isApplyingThisView ? 'Applying...' : view.name}
                    </button>
                    <button
                      type="button"
                      onClick={() => removeSavedView(view.id)}
                      disabled={isSavedViewActionBusy}
                      className="border-l border-slate-200 px-2 py-1.5 text-[11px] text-slate-700 hover:bg-slate-100 hover:text-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
                      aria-label={`Remove saved view ${view.name}`}
                    >
                      {isRemovingThisView ? 'Removing...' : 'Remove'}
                    </button>
                    <button
                      type="button"
                      onClick={() => void copySavedViewLink(view)}
                      disabled={isSavedViewActionBusy}
                      className="border-l border-slate-200 px-2 py-1.5 text-[11px] text-slate-700 hover:bg-slate-100 hover:text-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
                      aria-label={`Share saved view ${view.name}`}
                    >
                      {isSharingThisView ? 'Sharing...' : 'Share'}
                    </button>
                  </div>
                );
              })
            )}
          </div>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <input
              value={savedViewName}
              disabled={isSavedViewActionBusy}
              onChange={(event) => setSavedViewName(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter') {
                  event.preventDefault();
                  saveCurrentView();
                }
              }}
              placeholder="e.g. Active campaigns this quarter"
              maxLength={40}
              className="w-full rounded-lg border border-slate-700 px-3 py-2 text-sm focus:ring-2 focus:ring-teal-400 outline-none disabled:cursor-not-allowed disabled:opacity-60 sm:min-w-[220px] sm:flex-1"
            />
            <button
              type="button"
              onClick={saveCurrentView}
              disabled={isSavingView || isSavedViewActionBusy || !savedViewName.trim()}
              className="w-full rounded-lg bg-teal-600 px-3 py-2 text-sm font-medium text-white hover:bg-teal-500 disabled:cursor-not-allowed disabled:border disabled:border-slate-500 disabled:bg-slate-100 disabled:text-slate-700 sm:w-auto"
            >
              {isSavingView ? 'Saving...' : 'Save current view'}
            </button>
          </div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <div>
            <label htmlFor="operations-search-campaign" className="block text-sm font-medium text-slate-700 mb-1">
              Search
            </label>
            <input
              id="operations-search-campaign"
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
              placeholder="Campaign name, description, manager email"
              className="w-full rounded-lg border border-slate-700 px-3 py-2 text-sm focus:ring-2 focus:ring-teal-400 outline-none"
            />
          </div>
          <div>
            <label htmlFor="operations-status-filter" className="block text-sm font-medium text-slate-700 mb-1">
              Status
            </label>
            <select
              id="operations-status-filter"
              value={statusFilter}
              onChange={(event) => setStatusFilter(event.target.value as DashboardStatusFilter)}
              className="w-full rounded-lg border border-slate-700 px-3 py-2 text-sm focus:ring-2 focus:ring-teal-400 outline-none"
            >
              <option value="all">All statuses</option>
              <option value="draft">Draft</option>
              <option value="active">Active</option>
              <option value="closed">Closed</option>
              <option value="archived">Archived</option>
            </select>
          </div>
          <div>
            <label htmlFor="operations-window-filter" className="block text-sm font-medium text-slate-700 mb-1">
              Created within
            </label>
            <select
              id="operations-window-filter"
              value={windowFilter}
              onChange={(event) => setWindowFilter(event.target.value as DashboardWindowFilter)}
              className="w-full rounded-lg border border-slate-700 px-3 py-2 text-sm focus:ring-2 focus:ring-teal-400 outline-none"
            >
              <option value="all">All time</option>
              <option value="30">Last 30 days</option>
              <option value="90">Last 90 days</option>
              <option value="365">Last 365 days</option>
            </select>
          </div>
        </div>
        <p className="text-xs text-slate-700 mt-3">
          Showing {filteredCampaignStats.length} campaign(s) out of {campaignStats.length} loaded.
        </p>
      </section>

      <section className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-5 gap-4">
        <div className="rounded-xl border border-slate-200 bg-white p-5">
          <div className="flex items-center justify-between">
            <p className="text-sm text-slate-700">Total Campaigns</p>
            <FolderKanban className="w-5 h-5 text-slate-700" />
          </div>
          <p className="mt-2 text-3xl font-semibold text-slate-900">{filteredCampaignStats.length}</p>
          <p className="text-xs text-slate-700 mt-1">{activeCampaigns} active</p>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-5">
          <div className="flex items-center justify-between">
            <p className="text-sm text-slate-700">Total Candidates</p>
            <Users2 className="w-5 h-5 text-slate-700" />
          </div>
          <p className="mt-2 text-3xl font-semibold text-slate-900">{aggregate.totalCandidates}</p>
          <p className="text-xs text-slate-700 mt-1">Across filtered campaigns</p>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-5">
          <div className="flex items-center justify-between">
            <p className="text-sm text-slate-700">In Progress</p>
            <FileClock className="w-5 h-5 text-amber-500" />
          </div>
          <p className="mt-2 text-3xl font-semibold text-amber-600">{aggregate.inProgress}</p>
          <p className="text-xs text-slate-700 mt-1">Candidates currently vetting</p>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-5">
          <div className="flex items-center justify-between">
            <p className="text-sm text-slate-700">Approved</p>
            <UserCheck2 className="w-5 h-5 text-emerald-500" />
          </div>
          <p className="mt-2 text-3xl font-semibold text-emerald-600">{aggregate.approved}</p>
          <p className="text-xs text-slate-700 mt-1">{pipelineRate.approval}% approval</p>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-5">
          <div className="flex items-center justify-between">
            <p className="text-sm text-slate-700">Rejected</p>
            <UserX2 className="w-5 h-5 text-rose-500" />
          </div>
          <p className="mt-2 text-3xl font-semibold text-rose-600">{aggregate.rejected}</p>
          <p className="text-xs text-slate-700 mt-1">{pipelineRate.completion}% completion</p>
        </div>
      </section>

      <div ref={chartsSectionTriggerRef} className="h-px" aria-hidden />
      {shouldLoadCharts ? (
        <React.Suspense
          fallback={
            <section className="grid grid-cols-1 xl:grid-cols-3 gap-6">
              <div className="xl:col-span-2 rounded-xl border border-slate-200 bg-white p-5">
                <div className="h-6 w-56 bg-slate-200 rounded animate-pulse" />
                <div className="h-80 mt-4 bg-slate-100 rounded animate-pulse" />
              </div>
              <div className="rounded-xl border border-slate-200 bg-white p-5">
                <div className="h-6 w-36 bg-slate-200 rounded animate-pulse" />
                <div className="h-60 mt-3 bg-slate-100 rounded animate-pulse" />
                <div className="h-4 w-28 mt-4 bg-slate-200 rounded animate-pulse" />
                <div className="h-44 mt-2 bg-slate-100 rounded animate-pulse" />
              </div>
            </section>
          }
        >
          <OperationsDashboardChartsSection
            chartMode={chartMode}
            onChartModeChange={setChartMode}
            throughputDisplayData={throughputDisplayData}
            pipelineMixDisplayData={pipelineMixDisplayData}
            decisionMixDisplayData={decisionMixDisplayData}
          />
        </React.Suspense>
      ) : (
        <section className="grid grid-cols-1 xl:grid-cols-3 gap-6">
          <div className="xl:col-span-2 rounded-xl border border-slate-200 bg-white p-5 text-sm text-slate-700">
            Charts will load as this section enters view.
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-5 text-sm text-slate-700">
            Deferred chart loading improves initial dashboard responsiveness.
          </div>
        </section>
      )}

      <section className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        <div className="xl:col-span-2 rounded-xl border border-slate-200 bg-white p-5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-lg font-semibold">Campaign Pulse</h2>
            <div className="flex flex-wrap items-center gap-2">
              <label htmlFor="campaign-pulse-sort" className="text-xs text-slate-700">
                Sort by
              </label>
              <select
                id="campaign-pulse-sort"
                value={campaignPulseSort}
                onChange={(event) => setCampaignPulseSort(event.target.value as CampaignPulseSort)}
                className="rounded-md border border-slate-700 bg-white px-2 py-1 text-xs text-slate-700"
              >
                {CAMPAIGN_PULSE_SORT_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
              <Link to="/campaigns" className="text-sm text-indigo-600 hover:text-indigo-700">
                View all
              </Link>
            </div>
          </div>
          {campaignPulseRows.length === 0 ? (
            <div className="py-10 text-center text-slate-700">No campaigns match current filters.</div>
          ) : (
            <div className="mt-4 space-y-3">
              {campaignPulseRows.map((row) => (
                <article
                  key={row.campaign.id}
                  className="rounded-lg border border-slate-200 p-4 hover:border-teal-300 transition-colors"
                >
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <p className="font-medium text-slate-900">{row.campaign.name}</p>
                      <p className="text-xs text-slate-700">Created {formatDate(row.campaign.created_at)}</p>
                    </div>
                    <span
                      className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium ${
                        statusPillClass[row.campaign.status] || 'bg-slate-200 text-slate-800'
                      }`}
                    >
                      {row.campaign.status}
                    </span>
                  </div>

                  <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mt-3 text-xs">
                    <div className="rounded bg-slate-50 px-2 py-1.5">
                      <p className="text-slate-700">Total</p>
                      <p className="font-semibold">{row.metrics.total_candidates}</p>
                    </div>
                    <div className="rounded bg-slate-50 px-2 py-1.5">
                      <p className="text-slate-700">In Progress</p>
                      <p className="font-semibold">{row.metrics.in_progress}</p>
                    </div>
                    <div className="rounded bg-slate-50 px-2 py-1.5">
                      <p className="text-slate-700">Completed</p>
                      <p className="font-semibold">{row.metrics.completed}</p>
                    </div>
                    <div className="rounded bg-slate-50 px-2 py-1.5">
                      <p className="text-slate-700">Approved</p>
                      <p className="font-semibold">{row.metrics.approved}</p>
                    </div>
                  </div>
                  <div className="mt-2 flex flex-wrap gap-2 text-[11px]">
                    <span className="rounded-full bg-teal-50 px-2 py-1 text-teal-700">
                      Completion:{' '}
                      {row.metrics.total_candidates > 0
                        ? `${((row.metrics.completed / row.metrics.total_candidates) * 100).toFixed(1)}%`
                        : '0.0%'}
                    </span>
                    <span className="rounded-full bg-emerald-50 px-2 py-1 text-emerald-700">
                      Approval:{' '}
                      {row.metrics.total_candidates > 0
                        ? `${((row.metrics.approved / row.metrics.total_candidates) * 100).toFixed(1)}%`
                        : '0.0%'}
                    </span>
                  </div>

                  <div className="mt-3 flex justify-end">
                    <button
                      type="button"
                      onClick={() => navigate(`/campaigns/${row.campaign.id}`)}
                      className="text-sm text-indigo-600 hover:text-indigo-700 font-medium"
                    >
                      Open Workspace
                    </button>
                  </div>
                </article>
              ))}
            </div>
          )}
        </div>

        <div className="space-y-4">
          <div className="rounded-xl border border-slate-200 bg-white p-5">
            <h2 className="text-lg font-semibold inline-flex items-center gap-2">
              <Activity className="w-5 h-5 text-teal-600" />
              Quick Actions
            </h2>
            <div className="mt-4 space-y-3">
              <button
                type="button"
                onClick={() => navigate('/campaigns')}
                className="w-full rounded-lg border border-slate-700 px-4 py-3 text-left hover:bg-slate-100"
              >
                <p className="font-medium text-slate-900">Create / Edit Campaign</p>
                <p className="text-xs text-slate-700">Configure campaign window and rules.</p>
              </button>

              <button
                type="button"
                onClick={() => navigate('/campaigns')}
                className="w-full rounded-lg border border-slate-700 px-4 py-3 text-left hover:bg-slate-100"
              >
                <p className="font-medium text-slate-900">Import Candidate Batch</p>
                <p className="text-xs text-slate-700">Upload candidate list and trigger invitations.</p>
              </button>

              <button
                type="button"
                onClick={() => navigate('/notifications')}
                className="w-full rounded-lg border border-slate-700 px-4 py-3 text-left hover:bg-slate-100"
              >
                <p className="font-medium text-slate-900">Review Alerts</p>
                <p className="text-xs text-slate-700">Monitor delivery and vetting notifications.</p>
              </button>

              <button
                type="button"
                onClick={() => navigate('/video-calls')}
                className="w-full rounded-lg border border-slate-700 px-4 py-3 text-left hover:bg-slate-100"
              >
                <p className="font-medium text-slate-900">Schedule Video Meeting</p>
                <p className="text-xs text-slate-700">Create 1v1 or 1vMany live interview sessions.</p>
              </button>

              <button
                type="button"
                onClick={() => navigate('/government/appointments')}
                className="w-full rounded-lg border border-slate-700 px-4 py-3 text-left hover:bg-slate-100"
              >
                <p className="font-medium text-slate-900">Government Appointments</p>
                <p className="text-xs text-slate-700">Track nomination, vetting stage, and final decisions.</p>
              </button>

              <button
                type="button"
                onClick={() => navigate('/government/positions')}
                className="w-full rounded-lg border border-slate-700 px-4 py-3 text-left hover:bg-slate-100"
              >
                <p className="font-medium text-slate-900">Government Position Registry</p>
                <p className="text-xs text-slate-700">Manage public offices, vacancies, and appointment authority.</p>
              </button>

              <button
                type="button"
                onClick={() => navigate('/government/personnel')}
                className="w-full rounded-lg border border-slate-700 px-4 py-3 text-left hover:bg-slate-100"
              >
                <p className="font-medium text-slate-900">Government Personnel Registry</p>
                <p className="text-xs text-slate-700">Maintain nominee and officeholder profiles.</p>
              </button>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
};

export default OperationsDashboardPage;





