// src/components/admin/Analytics.tsx
import React, { useEffect, useState } from 'react';
import {
  TrendingUp,
  TrendingDown,
  Users,
  FileText,
  Clock,
  CheckCircle,
  XCircle,
  Activity,
} from 'lucide-react';
import { LineChart, Line, BarChart, Bar, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
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

export const Analytics: React.FC = () => {
  const [data, setData] = useState<AnalyticsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [timeRange, setTimeRange] = useState<'7d' | '30d' | '90d'>('30d');

  useEffect(() => {
    loadAnalytics();
  }, [timeRange]);

  const loadAnalytics = async () => {
    try {
      setLoading(true);
      const response = await adminService.getAnalytics();
      
      // Transform and prepare data
      const analyticsData: AnalyticsData = {
        overview: {
          totalApplications: response.total_applications || 0,
          approvalRate: response.approval_rate || 0,
          avgProcessingTime: response.avg_processing_time || 0,
          activeUsers: response.active_users || 0,
        },
        trends: response.trends || generateMockTrends(),
        statusDistribution: [
          { name: 'Pending', value: response.pending || 0, color: '#F59E0B' },
          { name: 'Under Review', value: response.under_review || 0, color: '#3B82F6' },
          { name: 'Approved', value: response.approved || 0, color: '#10B981' },
          { name: 'Rejected', value: response.rejected || 0, color: '#EF4444' },
        ],
        performanceMetrics: {
          avgReviewTime: response.avg_review_time || 2.5,
          avgDocumentsPerApp: response.avg_documents_per_app || 4.2,
          aiAccuracy: response.ai_accuracy || 92.5,
          fraudDetectionRate: response.fraud_detection_rate || 8.3,
        },
      };
      
      setData(analyticsData);
    } catch (error) {
      console.error('Failed to load analytics:', error);
      // Set mock data for demo
      setData(generateMockData());
    } finally {
      setLoading(false);
    }
  };

  const generateMockTrends = () => {
    const days = timeRange === '7d' ? 7 : timeRange === '30d' ? 30 : 90;
    return Array.from({ length: days }, (_, i) => ({
      date: new Date(Date.now() - (days - i) * 24 * 60 * 60 * 1000).toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
      }),
      applications: Math.floor(Math.random() * 50) + 20,
      approved: Math.floor(Math.random() * 30) + 10,
      rejected: Math.floor(Math.random() * 10) + 2,
    }));
  };

  const generateMockData = (): AnalyticsData => ({
    overview: {
      totalApplications: 1248,
      approvalRate: 78.5,
      avgProcessingTime: 2.8,
      activeUsers: 856,
    },
    trends: generateMockTrends(),
    statusDistribution: [
      { name: 'Pending', value: 145, color: '#F59E0B' },
      { name: 'Under Review', value: 89, color: '#3B82F6' },
      { name: 'Approved', value: 980, color: '#10B981' },
      { name: 'Rejected', value: 34, color: '#EF4444' },
    ],
    performanceMetrics: {
      avgReviewTime: 2.5,
      avgDocumentsPerApp: 4.2,
      aiAccuracy: 92.5,
      fraudDetectionRate: 8.3,
    },
  });

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex justify-center items-center">
        <Loader size="xl" />
      </div>
    );
  }

  if (!data) {
    return (
      <div className="min-h-screen bg-gray-50 flex justify-center items-center">
        <div className="text-center">
          <Activity className="w-16 h-16 text-gray-400 mx-auto mb-4" />
          <p className="text-gray-600">No analytics data available</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto p-6 space-y-6">
        {/* Header */}
        <div className="flex justify-between items-center">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Analytics Dashboard</h1>
            <p className="text-gray-600 mt-1">Comprehensive system insights and metrics</p>
          </div>
          
          <div className="flex gap-2">
            {(['7d', '30d', '90d'] as const).map((range) => (
              <button
                key={range}
                onClick={() => setTimeRange(range)}
                className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                  timeRange === range
                    ? 'bg-indigo-600 text-white'
                    : 'bg-white text-gray-700 hover:bg-gray-50'
                }`}
              >
                {range === '7d' ? 'Last 7 Days' : range === '30d' ? 'Last 30 Days' : 'Last 90 Days'}
              </button>
            ))}
          </div>
        </div>

        {/* Overview Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          <div className="bg-white rounded-lg shadow-sm p-6">
            <div className="flex items-center justify-between mb-2">
              <FileText className="w-8 h-8 text-blue-600" />
              <span className="flex items-center text-green-600 text-sm font-medium">
                <TrendingUp className="w-4 h-4 mr-1" />
                +12.5%
              </span>
            </div>
            <p className="text-sm text-gray-600">Total Applications</p>
            <p className="text-3xl font-bold text-gray-900 mt-1">
              {data.overview.totalApplications.toLocaleString()}
            </p>
          </div>

          <div className="bg-white rounded-lg shadow-sm p-6">
            <div className="flex items-center justify-between mb-2">
              <CheckCircle className="w-8 h-8 text-green-600" />
              <span className="flex items-center text-green-600 text-sm font-medium">
                <TrendingUp className="w-4 h-4 mr-1" />
                +3.2%
              </span>
            </div>
            <p className="text-sm text-gray-600">Approval Rate</p>
            <p className="text-3xl font-bold text-gray-900 mt-1">
              {data.overview.approvalRate.toFixed(1)}%
            </p>
          </div>

          <div className="bg-white rounded-lg shadow-sm p-6">
            <div className="flex items-center justify-between mb-2">
              <Clock className="w-8 h-8 text-yellow-600" />
              <span className="flex items-center text-red-600 text-sm font-medium">
                <TrendingDown className="w-4 h-4 mr-1" />
                -8.5%
              </span>
            </div>
            <p className="text-sm text-gray-600">Avg. Processing Time</p>
            <p className="text-3xl font-bold text-gray-900 mt-1">
              {data.overview.avgProcessingTime.toFixed(1)} days
            </p>
          </div>

          <div className="bg-white rounded-lg shadow-sm p-6">
            <div className="flex items-center justify-between mb-2">
              <Users className="w-8 h-8 text-purple-600" />
              <span className="flex items-center text-green-600 text-sm font-medium">
                <TrendingUp className="w-4 h-4 mr-1" />
                +18.7%
              </span>
            </div>
            <p className="text-sm text-gray-600">Active Users</p>
            <p className="text-3xl font-bold text-gray-900 mt-1">
              {data.overview.activeUsers.toLocaleString()}
            </p>
          </div>
        </div>

        {/* Charts Row */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Application Trends */}
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
                <Line type="monotone" dataKey="approved" stroke="#10B981" strokeWidth={2} name="Approved" />
                <Line type="monotone" dataKey="rejected" stroke="#EF4444" strokeWidth={2} name="Rejected" />
              </LineChart>
            </ResponsiveContainer>
          </div>

          {/* Status Distribution */}
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

        {/* Performance Metrics */}
        <div className="bg-white rounded-lg shadow-sm p-6">
          <h2 className="text-xl font-semibold mb-6">Performance Metrics</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            <div className="text-center p-4 bg-blue-50 rounded-lg">
              <Clock className="w-8 h-8 text-blue-600 mx-auto mb-2" />
              <p className="text-2xl font-bold text-blue-600">
                {data.performanceMetrics.avgReviewTime} days
              </p>
              <p className="text-sm text-gray-600 mt-1">Avg. Review Time</p>
            </div>

            <div className="text-center p-4 bg-green-50 rounded-lg">
              <FileText className="w-8 h-8 text-green-600 mx-auto mb-2" />
              <p className="text-2xl font-bold text-green-600">
                {data.performanceMetrics.avgDocumentsPerApp.toFixed(1)}
              </p>
              <p className="text-sm text-gray-600 mt-1">Docs per Application</p>
            </div>

            <div className="text-center p-4 bg-purple-50 rounded-lg">
              <Activity className="w-8 h-8 text-purple-600 mx-auto mb-2" />
              <p className="text-2xl font-bold text-purple-600">
                {data.performanceMetrics.aiAccuracy.toFixed(1)}%
              </p>
              <p className="text-sm text-gray-600 mt-1">AI Accuracy</p>
            </div>

            <div className="text-center p-4 bg-red-50 rounded-lg">
              <XCircle className="w-8 h-8 text-red-600 mx-auto mb-2" />
              <p className="text-2xl font-bold text-red-600">
                {data.performanceMetrics.fraudDetectionRate.toFixed(1)}%
              </p>
              <p className="text-sm text-gray-600 mt-1">Fraud Detection Rate</p>
            </div>
          </div>
        </div>

        {/* Comparison Bar Chart */}
        <div className="bg-white rounded-lg shadow-sm p-6">
          <h2 className="text-xl font-semibold mb-4">Monthly Comparison</h2>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={data.trends.slice(-12)}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="date" />
              <YAxis />
              <Tooltip />
              <Legend />
              <Bar dataKey="approved" fill="#10B981" name="Approved" />
              <Bar dataKey="rejected" fill="#EF4444" name="Rejected" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
};

export default Analytics;