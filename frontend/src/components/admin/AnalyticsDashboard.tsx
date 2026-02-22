// src/components/admin/AnalyticsDashboard.tsx
import { useState, useEffect, useCallback } from 'react';
import {
  LineChart, Line, BarChart, Bar, PieChart, Pie,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, Cell
} from 'recharts';
import { subDays, formatISO } from 'date-fns';

// Type Definitions
interface OverviewMetrics {
  total_interviews: number;
  completion_rate: number;
}

interface PerformanceMetrics {
  avg_deception_score: number;
  avg_duration_minutes: number;
  avg_questions_asked: number;
  avg_overall_score: number;
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

interface Deception {
  distribution: {
    low: number;
    medium: number;
    high: number;
  };
  common_red_flags: Record<string, number>;
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


export function AnalyticsDashboard() {
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [trends, setTrends] = useState<Trends | null>(null);
  const [flags, setFlags] = useState<Flag[]>([]);
  const [deception, setDeception] = useState<Deception | null>(null);
  const [timeRange, setTimeRange] = useState(30);
  const [loading, setLoading] = useState(true);

  const fetchAnalytics = useCallback(async () => {
    setLoading(true);
    try {
      const response = await fetch(`/api/analytics/dashboard?days=${timeRange}`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
      });
      const data = await response.json();
      
      setMetrics(data.metrics);
      setTrends(data.trends);
      setFlags(data.flags);
      setDeception(data.deception);
    } catch (error) {
      console.error('Failed to fetch analytics:', error);
    } finally {
      setLoading(false);
    }
  }, [timeRange]);

  useEffect(() => {
    fetchAnalytics();
  }, [fetchAnalytics]);


  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="animate-spin rounded-full h-16 w-16 border-t-2 border-b-2 border-blue-600"></div>
      </div>
    );
  }


  // Functions
const downloadCSVReport = async () => {
  const endDate = new Date();
  const startDate = subDays(endDate, timeRange);

  const response = await fetch(
    `/api/analytics/export/csv?start_date=${formatISO(startDate)}&end_date=${formatISO(endDate)}`,
    {
      headers: {
        'Authorization': `Bearer ${localStorage.getItem('token')}`
      }
    }
  );
  
  const blob = await response.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `interview_report_${new Date().toISOString().split('T')[0]}.csv`;
  a.click();
};

if (!metrics || !trends || !deception) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-red-500">
          Failed to load analytics data. Please try again later.
        </div>
      </div>
    );
  }


  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex justify-between items-center mb-8">
          <div>
            <h1 className="text-4xl font-bold text-gray-900">Interview Analytics</h1>
            <p className="text-gray-600 mt-2">AI Interrogation System Performance</p>
          </div>
          
          <select
            value={timeRange}
            onChange={(e) => setTimeRange(Number(e.target.value))}
            className="px-4 py-2 border border-gray-300 rounded-lg"
          >
            <option value={7}>Last 7 days</option>
            <option value={30}>Last 30 days</option>
            <option value={90}>Last 90 days</option>
          </select>
        </div>
        {/* // Add to AnalyticsDashboard.tsx */}
        <div className="flex gap-4 mb-8">
        <button
            onClick={downloadCSVReport}
            className="px-6 py-3 bg-blue-600 text-white rounded-lg font-semibold hover:bg-blue-700 flex items-center gap-2"
        >
            <span>📊</span>
            Export CSV Report
        </button>
        
        <button
            // TODO: Implement PDF report generation for a selected session or all sessions
            // onClick={() => downloadPDFReport('some-session-id')}
            className="px-6 py-3 bg-purple-600 text-white rounded-lg font-semibold hover:bg-purple-700 flex items-center gap-2"
        >
            <span>📄</span>
            Export PDF Reports
        </button>
        </div>


        {/* Overview Cards */}
        <div className="grid md:grid-cols-4 gap-6 mb-8">
          <MetricCard
            title="Total Interviews"
            value={metrics.overview.total_interviews}
            icon="📊"
            color="blue"
          />
          <MetricCard
            title="Completion Rate"
            value={`${metrics.overview.completion_rate}%`}
            icon="✅"
            color="green"
          />
          <MetricCard
            title="Avg Deception Score"
            value={`${metrics.performance.avg_deception_score}%`}
            icon="⚠️"
            color="red"
          />
          <MetricCard
            title="Total Cost"
            value={`${metrics.cost.estimated_cost}`}
            icon="💰"
            color="yellow"
          />
        </div>

        {/* Charts Grid */}
        <div className="grid md:grid-cols-2 gap-8 mb-8">
          {/* Interview Trend */}
          <div className="bg-white rounded-xl shadow-lg p-6">
            <h2 className="text-xl font-bold text-gray-900 mb-4">Interview Trend</h2>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={formatTrendData(trends)}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Line 
                  type="monotone" 
                  dataKey="interviews" 
                  stroke="#3B82F6" 
                  strokeWidth={2}
                  name="Total"
                />
                <Line 
                  type="monotone" 
                  dataKey="completed" 
                  stroke="#10B981" 
                  strokeWidth={2}
                  name="Completed"
                />
              </LineChart>
            </ResponsiveContainer>
          </div>

          {/* Average Scores Trend */}
          <div className="bg-white rounded-xl shadow-lg p-6">
            <h2 className="text-xl font-bold text-gray-900 mb-4">Average Scores</h2>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={formatTrendData(trends)}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" />
                <YAxis domain={[0, 100]} />
                <Tooltip />
                <Legend />
                <Line 
                  type="monotone" 
                  dataKey="avgScore" 
                  stroke="#8B5CF6" 
                  strokeWidth={2}
                  name="Overall Score"
                />
              </LineChart>
            </ResponsiveContainer>
          </div>

          {/* Flag Breakdown */}
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

          {/* Deception Distribution */}
          <div className="bg-white rounded-xl shadow-lg p-6">
            <h2 className="text-xl font-bold text-gray-900 mb-4">Deception Score Distribution</h2>
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={formatDeceptionData(deception.distribution)}
                  cx="50%"
                  cy="50%"
                  labelLine={false}
                  label={renderCustomLabel}
                  outerRadius={100}
                  fill="#8884d8"
                  dataKey="value"
                >
                  {formatDeceptionData(deception.distribution).map((_entry, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Detailed Metrics */}
        <div className="grid md:grid-cols-3 gap-6 mb-8">
          {/* Performance Metrics */}
          <div className="bg-white rounded-xl shadow-lg p-6">
            <h3 className="text-lg font-bold text-gray-900 mb-4 flex items-center gap-2">
              <span>⚡</span> Performance Metrics
            </h3>
            <div className="space-y-3">
              <MetricRow 
                label="Avg Duration" 
                value={`${metrics.performance.avg_duration_minutes} min`} 
              />
              <MetricRow 
                label="Avg Questions" 
                value={metrics.performance.avg_questions_asked} 
              />
              <MetricRow 
                label="Avg Overall Score" 
                value={`${metrics.performance.avg_overall_score}%`} 
              />
            </div>
          </div>

          {/* Flag Metrics */}
          <div className="bg-white rounded-xl shadow-lg p-6">
            <h3 className="text-lg font-bold text-gray-900 mb-4 flex items-center gap-2">
              <span>🚩</span> Flag Resolution
            </h3>
            <div className="space-y-3">
              <MetricRow 
                label="Total Flags" 
                value={metrics.flags.total_flags} 
              />
              <MetricRow 
                label="Resolved" 
                value={metrics.flags.resolved_flags} 
              />
              <MetricRow 
                label="Resolution Rate" 
                value={`${metrics.flags.resolution_rate}%`} 
              />
            </div>
          </div>

          {/* Cost Metrics */}
          <div className="bg-white rounded-xl shadow-lg p-6">
            <h3 className="text-lg font-bold text-gray-900 mb-4 flex items-center gap-2">
              <span>💵</span> Cost Analysis
            </h3>
            <div className="space-y-3">
              <MetricRow 
                label="Total Minutes" 
                value={metrics.cost.total_minutes} 
              />
              <MetricRow 
                label="Total Cost" 
                value={`${metrics.cost.estimated_cost}`} 
              />
              <MetricRow 
                label="Cost per Interview" 
                value={`${metrics.cost.cost_per_interview}`} 
              />
            </div>
          </div>
        </div>

        {/* Common Red Flags Table */}
        <div className="bg-white rounded-xl shadow-lg p-6">
          <h2 className="text-xl font-bold text-gray-900 mb-4">Most Common Behavioral Red Flags</h2>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Red Flag</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Occurrences</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Severity</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {Object.entries(deception.common_red_flags || {}).map(([flag, count]) => (
                  <tr key={flag}>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {flag.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {count}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className={`px-2 py-1 text-xs font-semibold rounded-full ${
                        count > 10 ? 'bg-red-100 text-red-800' :
                        count > 5 ? 'bg-yellow-100 text-yellow-800' :
                        'bg-green-100 text-green-800'
                      }`}>
                        {count > 10 ? 'High' : count > 5 ? 'Medium' : 'Low'}
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

// Helper Components
function MetricCard({ title, value, icon, color }: MetricCardProps) {
  const colorClasses = {
    blue: 'bg-blue-50 text-blue-600',
    green: 'bg-green-50 text-green-600',
    red: 'bg-red-50 text-red-600',
    yellow: 'bg-yellow-50 text-yellow-600'
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

// Helper Functions
function formatTrendData(trends: Trends) {
  if (!trends || !trends.dates) return [];
  
  return trends.dates.map((date, index) => ({
    date: new Date(date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
    interviews: trends.interviews[index],
    completed: trends.completed[index],
    avgScore: trends.avg_scores[index]
  }));
}

function formatDeceptionData(distribution: Deception['distribution']) {
  if (!distribution) return [];
  return [
    { name: 'Low Risk (0-30%)', value: distribution.low, color: '#10B981' },
    { name: 'Medium Risk (30-70%)', value: distribution.medium, color: '#F59E0B' },
    { name: 'High Risk (70-100%)', value: distribution.high, color: '#EF4444' }
  ];
}

function renderCustomLabel({ cx, cy, midAngle, innerRadius, outerRadius, percent }: CustomLabelProps) {
  const radius = innerRadius + (outerRadius - innerRadius) * 0.5;
  const x = cx + radius * Math.cos(-midAngle * Math.PI / 180);
  const y = cy + radius * Math.sin(-midAngle * Math.PI / 180);

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
}

const COLORS = ['#10B981', '#F59E0B', '#EF4444'];

export default AnalyticsDashboard;