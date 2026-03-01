// src/components/admin/AnalyticsDashboard.tsx
import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  PieChart,
  Pie,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  Cell,
} from 'recharts';
import { Download, FileText, RefreshCw } from 'lucide-react';

import { adminService } from '@/services/admin.service';

interface OverviewMetrics {
  total_interviews: number;
  completion_rate: number;
}

interface PerformanceMetrics {
  avg_duration_minutes: number;
  avg_questions_asked: number;
  avg_overall_score: number;
  avg_response_quality?: number;
  avg_eye_contact_percentage?: number;
  avg_stress_level?: number;
}

interface CostMetrics {
  estimated_cost: number;
  total_minutes: number;
  cost_per_interview: number;
}

interface FlagMetrics {
  total_flags: number;
  resolved_flags: number;
  resolution_rate: number;
}

interface Metrics {
  overview: OverviewMetrics;
  performance: PerformanceMetrics;
  cost: CostMetrics;
  flags: FlagMetrics;
}

interface Trends {
  dates: string[];
  interviews: number[];
  completed: number[];
  avg_scores: number[];
}

interface Flag {
  flag_type: string;
  count: number;
  resolved: number;
  critical: number;
}

interface Behavioral {
  stress_distribution: {
    low: number;
    medium: number;
    high: number;
  };
  fidgeting_rate: number;
  average_confidence_level: number;
}

interface DashboardResponse {
  metrics: Metrics;
  trends: Trends;
  flags: Flag[];
  behavioral: Behavioral;
}

interface MetricCardProps {
  title: string;
  value: string | number;
  icon: string;
  color: 'blue' | 'green' | 'red' | 'yellow';
}

interface MetricRowProps {
  label: string;
  value: string | number;
}

interface CustomLabelProps {
  cx: number;
  cy: number;
  midAngle: number;
  innerRadius: number;
  outerRadius: number;
  percent: number;
}

const COLORS = ['#10B981', '#F59E0B', '#EF4444'];

const formatTrendData = (trends: Trends) => {
  if (!trends?.dates) return [];

  return trends.dates.map((date, index) => ({
    date: new Date(date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
    interviews: trends.interviews[index] ?? 0,
    completed: trends.completed[index] ?? 0,
    avgScore: trends.avg_scores[index] ?? 0,
  }));
};

const formatStressData = (behavioral: Behavioral['stress_distribution']) => [
  { name: 'Low Stress', value: behavioral.low, color: '#10B981' },
  { name: 'Medium Stress', value: behavioral.medium, color: '#F59E0B' },
  { name: 'High Stress', value: behavioral.high, color: '#EF4444' },
];

const renderCustomLabel = ({
  cx,
  cy,
  midAngle,
  innerRadius,
  outerRadius,
  percent,
}: CustomLabelProps) => {
  const radius = innerRadius + (outerRadius - innerRadius) * 0.5;
  const x = cx + radius * Math.cos((-midAngle * Math.PI) / 180);
  const y = cy + radius * Math.sin((-midAngle * Math.PI) / 180);

  return (
    <text
      x={x}
      y={y}
      fill="white"
      textAnchor={x > cx ? 'start' : 'end'}
      dominantBaseline="central"
      className="font-bold"
    >
      {`${(percent * 100).toFixed(0)}%`}
    </text>
  );
};

function MetricCard({ title, value, icon, color }: MetricCardProps) {
  const colorClasses = {
    blue: 'bg-blue-50 text-blue-600',
    green: 'bg-green-50 text-green-600',
    red: 'bg-red-50 text-red-600',
    yellow: 'bg-yellow-50 text-yellow-600',
  };

  return (
    <div className="bg-white rounded-xl shadow-lg p-6">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-gray-600 mb-1">{title}</p>
          <p className="text-3xl font-bold text-gray-900">{value}</p>
        </div>
        <div className={`w-12 h-12 rounded-full flex items-center justify-center text-2xl ${colorClasses[color]}`}>
          {icon}
        </div>
      </div>
    </div>
  );
}

function MetricRow({ label, value }: MetricRowProps) {
  return (
    <div className="flex justify-between items-center py-2 border-b border-gray-100 last:border-0">
      <span className="text-sm text-gray-600">{label}</span>
      <span className="text-sm font-semibold text-gray-900">{value}</span>
    </div>
  );
}

export function AnalyticsDashboard() {
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [trends, setTrends] = useState<Trends | null>(null);
  const [flags, setFlags] = useState<Flag[]>([]);
  const [behavioral, setBehavioral] = useState<Behavioral | null>(null);
  const [timeRange, setTimeRange] = useState(30);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchAnalytics = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = (await adminService.getInterviewAnalytics({ days: timeRange })) as DashboardResponse;
      setMetrics(data.metrics);
      setTrends(data.trends);
      setFlags(Array.isArray(data.flags) ? data.flags : []);
      setBehavioral(data.behavioral);
    } catch (fetchError: any) {
      console.error('Failed to fetch analytics:', fetchError);
      setError(fetchError?.message || 'Failed to load analytics data.');
      setMetrics(null);
      setTrends(null);
      setFlags([]);
      setBehavioral(null);
    } finally {
      setLoading(false);
    }
  }, [timeRange]);

  useEffect(() => {
    void fetchAnalytics();
  }, [fetchAnalytics]);

  const trendData = useMemo(() => (trends ? formatTrendData(trends) : []), [trends]);

  const downloadCSVReport = () => {
    if (!metrics || !trends || !behavioral) {
      return;
    }

    const rows: string[] = [];
    rows.push('section,key,value');
    rows.push(`overview,total_interviews,${metrics.overview.total_interviews}`);
    rows.push(`overview,completion_rate,${metrics.overview.completion_rate}`);
    rows.push(`performance,avg_duration_minutes,${metrics.performance.avg_duration_minutes}`);
    rows.push(`performance,avg_questions_asked,${metrics.performance.avg_questions_asked}`);
    rows.push(`performance,avg_overall_score,${metrics.performance.avg_overall_score}`);
    rows.push(`cost,estimated_cost,${metrics.cost.estimated_cost}`);
    rows.push(`flags,total_flags,${metrics.flags.total_flags}`);
    rows.push(`flags,resolved_flags,${metrics.flags.resolved_flags}`);
    rows.push(`behavioral,fidgeting_rate,${behavioral.fidgeting_rate}`);
    rows.push(`behavioral,average_confidence_level,${behavioral.average_confidence_level}`);

    trendData.forEach((item) => {
      rows.push(`trend,${item.date},interviews:${item.interviews}|completed:${item.completed}|avgScore:${item.avgScore}`);
    });

    flags.forEach((flag) => {
      rows.push(`flag,${flag.flag_type},count:${flag.count}|resolved:${flag.resolved}|critical:${flag.critical}`);
    });

    const csv = rows.join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `interview_analytics_${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
    window.URL.revokeObjectURL(url);
  };

  const downloadPDFReport = () => {
    window.print();
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="animate-spin rounded-full h-16 w-16 border-t-2 border-b-2 border-blue-600" />
      </div>
    );
  }

  if (error || !metrics || !trends || !behavioral) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-center">
          <p className="text-red-500 mb-3">{error || 'Failed to load analytics data.'}</p>
          <button
            type="button"
            onClick={() => void fetchAnalytics()}
            className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-white hover:bg-blue-700"
          >
            <RefreshCw className="h-4 w-4" />
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-7xl mx-auto">
        <div className="flex justify-between items-center mb-8">
          <div>
            <h1 className="text-4xl font-bold text-gray-900">Interview Analytics</h1>
            <p className="text-gray-600 mt-2">AI Interrogation System Performance</p>
          </div>

          <select
            title="Select Time Range"
            value={timeRange}
            onChange={(event) => setTimeRange(Number(event.target.value))}
            className="px-4 py-2 border border-gray-300 rounded-lg"
          >
            <option value={7}>Last 7 days</option>
            <option value={30}>Last 30 days</option>
            <option value={90}>Last 90 days</option>
          </select>
        </div>

        <div className="flex gap-4 mb-8">
          <button
            type="button"
            onClick={downloadCSVReport}
            className="px-6 py-3 bg-blue-600 text-white rounded-lg font-semibold hover:bg-blue-700 flex items-center gap-2"
          >
            <Download className="h-4 w-4" />
            Export CSV Report
          </button>

          <button
            type="button"
            onClick={downloadPDFReport}
            className="px-6 py-3 bg-purple-600 text-white rounded-lg font-semibold hover:bg-purple-700 flex items-center gap-2"
          >
            <FileText className="h-4 w-4" />
            Print / Save PDF
          </button>
        </div>

        <div className="grid md:grid-cols-4 gap-6 mb-8">
          <MetricCard title="Total Interviews" value={metrics.overview.total_interviews} icon="📊" color="blue" />
          <MetricCard title="Completion Rate" value={`${metrics.overview.completion_rate}%`} icon="✅" color="green" />
          <MetricCard
            title="Avg Stress Level"
            value={`${metrics.performance.avg_stress_level || 0}%`}
            icon="⚠️"
            color="red"
          />
          <MetricCard title="Total Cost" value={`${metrics.cost.estimated_cost}`} icon="💰" color="yellow" />
        </div>

        <div className="grid md:grid-cols-2 gap-8 mb-8">
          <div className="bg-white rounded-xl shadow-lg p-6">
            <h2 className="text-xl font-bold text-gray-900 mb-4">Interview Trend</h2>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={trendData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Line type="monotone" dataKey="interviews" stroke="#3B82F6" strokeWidth={2} name="Total" />
                <Line type="monotone" dataKey="completed" stroke="#10B981" strokeWidth={2} name="Completed" />
              </LineChart>
            </ResponsiveContainer>
          </div>

          <div className="bg-white rounded-xl shadow-lg p-6">
            <h2 className="text-xl font-bold text-gray-900 mb-4">Average Scores</h2>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={trendData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" />
                <YAxis domain={[0, 100]} />
                <Tooltip />
                <Legend />
                <Line type="monotone" dataKey="avgScore" stroke="#8B5CF6" strokeWidth={2} name="Overall Score" />
              </LineChart>
            </ResponsiveContainer>
          </div>

          <div className="bg-white rounded-xl shadow-lg p-6">
            <h2 className="text-xl font-bold text-gray-900 mb-4">Interrogation Flags</h2>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={flags}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="flag_type" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Bar dataKey="count" fill="#3B82F6" name="Total" />
                <Bar dataKey="resolved" fill="#10B981" name="Resolved" />
                <Bar dataKey="critical" fill="#EF4444" name="Critical" />
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div className="bg-white rounded-xl shadow-lg p-6">
            <h2 className="text-xl font-bold text-gray-900 mb-4">Stress Distribution</h2>
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={formatStressData(behavioral.stress_distribution)}
                  cx="50%"
                  cy="50%"
                  labelLine={false}
                  label={renderCustomLabel}
                  outerRadius={100}
                  fill="#8884d8"
                  dataKey="value"
                >
                  {formatStressData(behavioral.stress_distribution).map((_entry, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="grid md:grid-cols-3 gap-6 mb-8">
          <div className="bg-white rounded-xl shadow-lg p-6">
            <h3 className="text-lg font-bold text-gray-900 mb-4 flex items-center gap-2">
              <span>⚡</span> Performance Metrics
            </h3>
            <div className="space-y-3">
              <MetricRow label="Avg Duration" value={`${metrics.performance.avg_duration_minutes} min`} />
              <MetricRow label="Avg Questions" value={metrics.performance.avg_questions_asked} />
              <MetricRow label="Avg Overall Score" value={`${metrics.performance.avg_overall_score}%`} />
            </div>
          </div>

          <div className="bg-white rounded-xl shadow-lg p-6">
            <h3 className="text-lg font-bold text-gray-900 mb-4 flex items-center gap-2">
              <span>🚩</span> Flag Resolution
            </h3>
            <div className="space-y-3">
              <MetricRow label="Total Flags" value={metrics.flags.total_flags} />
              <MetricRow label="Resolved" value={metrics.flags.resolved_flags} />
              <MetricRow label="Resolution Rate" value={`${metrics.flags.resolution_rate}%`} />
            </div>
          </div>

          <div className="bg-white rounded-xl shadow-lg p-6">
            <h3 className="text-lg font-bold text-gray-900 mb-4 flex items-center gap-2">
              <span>💵</span> Cost Analysis
            </h3>
            <div className="space-y-3">
              <MetricRow label="Total Minutes" value={metrics.cost.total_minutes} />
              <MetricRow label="Total Cost" value={`${metrics.cost.estimated_cost}`} />
              <MetricRow label="Cost per Interview" value={`${metrics.cost.cost_per_interview}`} />
            </div>
          </div>
        </div>

        <div className="bg-white rounded-xl shadow-lg p-6">
          <h2 className="text-xl font-bold text-gray-900 mb-4">Most Common Flag Types</h2>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Flag Type</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Occurrences</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Severity</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {flags.map((flag) => (
                  <tr key={flag.flag_type}>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {flag.flag_type.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase())}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{flag.count}</td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span
                        className={`px-2 py-1 text-xs font-semibold rounded-full ${
                          flag.critical > 10
                            ? 'bg-red-100 text-red-800'
                            : flag.critical > 5
                            ? 'bg-yellow-100 text-yellow-800'
                            : 'bg-green-100 text-green-800'
                        }`}
                      >
                        {flag.critical > 10 ? 'High' : flag.critical > 5 ? 'Medium' : 'Low'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}

export default AnalyticsDashboard;
