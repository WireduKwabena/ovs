// src/components/admin/Analytics.tsx
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  TrendingUp,
  TrendingDown,
  Users,
  FileText,
  Clock,
  CheckCircle,
  XCircle,
  Activity,
  RotateCcw,
} from 'lucide-react';
import {
  LineChart,
  Line,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import { Loader } from '@/components/common/Loader';
import { adminService } from '@/services/admin.service';

interface AnalyticsData {
  overview: {
    totalApplications: number;
    approvalRate: number;
    avgProcessingTime: number;
    activeUsers: number;
  };
  trends: {
    date: string;
    applications: number;
    approved: number;
    rejected: number;
  }[];
  statusDistribution: {
    name: string;
    value: number;
    color: string;
  }[];
  performanceMetrics: {
    avgReviewTime: number;
    avgDocumentsPerApp: number;
    aiAccuracy: number;
    fraudDetectionRate: number;
  };
}

interface AdminAnalyticsResponse {
  status_distribution?: Array<{ status: string; count: number }>;
  monthly_trend?: Array<{ month: string; count: number }>;
  rubric_statistics?: {
    avg_score?: number | null;
    pass_count?: number;
    fail_count?: number;
  };
  total_applications?: number;
  total_users?: number;
}

const STATUS_COLORS: Record<string, string> = {
  pending: '#F59E0B',
  under_review: '#3B82F6',
  approved: '#10B981',
  rejected: '#EF4444',
};

const prettify = (value: string): string =>
  value
    .split('_')
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');

const mapApiResponseToAnalyticsData = (response: AdminAnalyticsResponse): AnalyticsData => {
  const totalApplications = Number(response.total_applications || 0);
  const totalUsers = Number(response.total_users || 0);
  const statuses = Array.isArray(response.status_distribution)
    ? response.status_distribution
    : [];

  const approvedCount = statuses.find((item) => item.status === 'approved')?.count || 0;
  const approvalRate = totalApplications > 0 ? (approvedCount / totalApplications) * 100 : 0;

  const statusDistribution = statuses.map((item) => ({
    name: prettify(item.status),
    value: Number(item.count || 0),
    color: STATUS_COLORS[item.status] || '#64748B',
  }));

  const trends = (response.monthly_trend || []).map((item) => ({
    date: item.month,
    applications: Number(item.count || 0),
    approved: 0,
    rejected: 0,
  }));

  const rubricStats = response.rubric_statistics || {};
  const passCount = Number(rubricStats.pass_count || 0);
  const failCount = Number(rubricStats.fail_count || 0);
  const reviewedCount = passCount + failCount;
  const avgScore = Number(rubricStats.avg_score || 0);

  return {
    overview: {
      totalApplications,
      approvalRate,
      avgProcessingTime: 0,
      activeUsers: totalUsers,
    },
    trends,
    statusDistribution,
    performanceMetrics: {
      avgReviewTime: 0,
      avgDocumentsPerApp: 0,
      aiAccuracy: avgScore,
      fraudDetectionRate: reviewedCount > 0 ? (failCount / reviewedCount) * 100 : 0,
    },
  };
};

export const Analytics: React.FC = () => {
  const [data, setData] = useState<AnalyticsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [timeRange, setTimeRange] = useState<'7d' | '30d' | '90d'>('30d');

  const monthsWindow = useMemo(() => {
    if (timeRange === '7d') return 1;
    if (timeRange === '30d') return 3;
    return 6;
  }, [timeRange]);

  const loadAnalytics = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      const response = (await adminService.getAnalytics({ months: monthsWindow })) as AdminAnalyticsResponse;
      const analyticsData = mapApiResponseToAnalyticsData(response);
      setData(analyticsData);
    } catch (loadError: any) {
      console.error('Failed to load analytics:', loadError);
      setData(null);
      setError(loadError?.message || 'Unable to load analytics data.');
    } finally {
      setLoading(false);
    }
  }, [monthsWindow]);

  useEffect(() => {
    void loadAnalytics();
  }, [loadAnalytics]);

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex justify-center items-center">
        <Loader size="xl" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 flex justify-center items-center p-6">
        <div className="max-w-xl rounded-xl border border-red-200 bg-white p-6 text-center shadow-sm">
          <Activity className="w-16 h-16 text-red-400 mx-auto mb-4" />
          <p className="text-red-700 font-semibold">Analytics unavailable</p>
          <p className="mt-2 text-sm text-slate-800">{error}</p>
          <button
            type="button"
            onClick={() => void loadAnalytics()}
            className="mt-5 inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700"
          >
            <RotateCcw className="w-4 h-4" />
            Retry
          </button>
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="min-h-screen bg-gray-50 flex justify-center items-center">
        <div className="text-center">
          <Activity className="w-16 h-16 text-slate-800 mx-auto mb-4" />
          <p className="text-slate-800">No analytics data available</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="mx-auto max-w-7xl space-y-6 px-4 py-6 sm:px-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Analytics Dashboard</h1>
            <p className="mt-1 text-slate-800">Comprehensive system insights and metrics</p>
          </div>

          <div className="grid w-full grid-cols-1 gap-2 sm:grid-cols-3 lg:w-auto">
            {(['7d', '30d', '90d'] as const).map((range) => (
              <button
                key={range}
                onClick={() => setTimeRange(range)}
                className={`rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
                  timeRange === range
                    ? 'bg-indigo-600 text-white'
                    : 'border border-slate-700 bg-white text-slate-900 hover:bg-slate-100'
                }`}
              >
                {range === '7d' ? 'Last 7 Days' : range === '30d' ? 'Last 30 Days' : 'Last 90 Days'}
              </button>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          <div className="bg-white rounded-lg shadow-sm p-6">
            <div className="flex items-center justify-between mb-2">
              <FileText className="w-8 h-8 text-blue-600" />
              <span className="flex items-center text-green-600 text-sm font-medium">
                <TrendingUp className="w-4 h-4 mr-1" />
                Live
              </span>
            </div>
            <p className="text-sm text-slate-800">Total Applications</p>
            <p className="text-3xl font-bold text-gray-900 mt-1">
              {data.overview.totalApplications.toLocaleString()}
            </p>
          </div>

          <div className="bg-white rounded-lg shadow-sm p-6">
            <div className="flex items-center justify-between mb-2">
              <CheckCircle className="w-8 h-8 text-green-600" />
              <span className="flex items-center text-green-600 text-sm font-medium">
                <TrendingUp className="w-4 h-4 mr-1" />
                Computed
              </span>
            </div>
            <p className="text-sm text-slate-800">Approval Rate</p>
            <p className="text-3xl font-bold text-gray-900 mt-1">
              {data.overview.approvalRate.toFixed(1)}%
            </p>
          </div>

          <div className="bg-white rounded-lg shadow-sm p-6">
            <div className="flex items-center justify-between mb-2">
              <Clock className="w-8 h-8 text-amber-700" />
              <span className="flex items-center text-sm font-medium text-slate-800">
                <TrendingDown className="w-4 h-4 mr-1" />
                N/A
              </span>
            </div>
            <p className="text-sm text-slate-800">Avg. Processing Time</p>
            <p className="text-3xl font-bold text-gray-900 mt-1">
              {data.overview.avgProcessingTime.toFixed(1)} days
            </p>
          </div>

          <div className="bg-white rounded-lg shadow-sm p-6">
            <div className="flex items-center justify-between mb-2">
              <Users className="w-8 h-8 text-purple-600" />
              <span className="flex items-center text-green-600 text-sm font-medium">
                <TrendingUp className="w-4 h-4 mr-1" />
                Live
              </span>
            </div>
            <p className="text-sm text-slate-800">Active Users</p>
            <p className="text-3xl font-bold text-gray-900 mt-1">
              {data.overview.activeUsers.toLocaleString()}
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="bg-white rounded-lg shadow-sm p-6">
            <h2 className="text-xl font-semibold mb-4">Application Trends</h2>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={data.trends}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Line type="monotone" dataKey="applications" stroke="#3B82F6" strokeWidth={2} name="Total" />
              </LineChart>
            </ResponsiveContainer>
          </div>

          <div className="bg-white rounded-lg shadow-sm p-6">
            <h2 className="text-xl font-semibold mb-4">Status Distribution</h2>
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={data.statusDistribution}
                  cx="50%"
                  cy="50%"
                  labelLine={false}
                  label={({ name, percent }) => `${name}: ${(percent * 100).toFixed(0)}%`}
                  outerRadius={80}
                  fill="#8884d8"
                  dataKey="value"
                >
                  {data.statusDistribution.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="bg-white rounded-lg shadow-sm p-6">
          <h2 className="text-xl font-semibold mb-6">Performance Metrics</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            <div className="text-center p-4 bg-blue-50 rounded-lg">
              <Clock className="w-8 h-8 text-blue-600 mx-auto mb-2" />
              <p className="text-2xl font-bold text-blue-600">{data.performanceMetrics.avgReviewTime.toFixed(1)} days</p>
              <p className="mt-1 text-sm text-slate-800">Avg. Review Time</p>
            </div>

            <div className="text-center p-4 bg-green-50 rounded-lg">
              <FileText className="w-8 h-8 text-green-600 mx-auto mb-2" />
              <p className="text-2xl font-bold text-green-600">{data.performanceMetrics.avgDocumentsPerApp.toFixed(1)}</p>
              <p className="mt-1 text-sm text-slate-800">Docs per Application</p>
            </div>

            <div className="rounded-lg border border-border bg-card p-4 text-center">
              <Activity className="mx-auto mb-2 h-8 w-8 text-primary" />
              <p className="text-2xl font-bold text-foreground">{data.performanceMetrics.aiAccuracy.toFixed(1)}%</p>
              <p className="mt-1 text-sm text-muted-foreground">Rubric Avg Score</p>
            </div>

            <div className="text-center p-4 bg-red-50 rounded-lg">
              <XCircle className="w-8 h-8 text-red-600 mx-auto mb-2" />
              <p className="text-2xl font-bold text-red-600">{data.performanceMetrics.fraudDetectionRate.toFixed(1)}%</p>
              <p className="mt-1 text-sm text-slate-800">Fail/Review Ratio</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Analytics;
