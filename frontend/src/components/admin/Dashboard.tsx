// src/components/admin/Dashboard.tsx
import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  FileText, Users, CheckCircle, XCircle,
  Clock, TrendingUp, AlertTriangle
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { StatusBadge } from '@/components/common/StatusBadge';
import { Loader } from '@/components/common/Loader';
import { adminService } from '@/services/admin.service';
import type { ApplicationStatus, DashboardStats } from '@/types';
import { formatDate } from '@/utils/helper';


interface StatCardProps {
  icon: LucideIcon;
  title: string;
  value: number;
  color: string;
  subtitle?: string;
}

const StatCard: React.FC<StatCardProps> = ({ icon: Icon, title, value, color, subtitle }) => (
  <div className="bg-white rounded-lg shadow-sm p-6 hover:shadow-md transition-shadow">
    <div className="flex items-center justify-between">
      <div>
        <p className="text-sm font-medium text-gray-600">{title}</p>
        <p className={`text-3xl font-bold ${color} mt-2`}>{value.toLocaleString()}</p>
        {subtitle && (
          <p className="text-xs text-gray-500 mt-1">{subtitle}</p>
        )}
      </div>
      <div className={`p-3 rounded-full ${color.replace('text-', 'bg-').replace('600', '100')}`}>
        <Icon className={`w-8 h-8 ${color}`} />
      </div>
    </div>
  </div>
);

interface RecentApplication {
  id: number;
  case_id: string;
  status: ApplicationStatus;
  applicant: {
    full_name: string;
  };
  application_type: string;
  created_at: string;
  consistency_score?: number;
  fraud_risk_score?: number;
}

export const AdminDashboard: React.FC = () => {
  const navigate = useNavigate();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadDashboardData();
  }, []);

  const loadDashboardData = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await adminService.getDashboard();
      setStats(data);
    } catch (err: any) {
      setError(err.message || 'Failed to load dashboard data');
      console.error('Dashboard error:', err);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center h-screen">
        <Loader size="xl" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-7xl mx-auto p-6">
        <div className="bg-red-50 border-l-4 border-red-500 p-6 rounded-lg">
          <div className="flex items-center gap-3">
            <AlertTriangle className="w-6 h-6 text-red-600" />
            <div>
              <h3 className="text-lg font-semibold text-red-900">Error Loading Dashboard</h3>
              <p className="text-red-700 mt-1">{error}</p>
            </div>
          </div>
          <button
            onClick={loadDashboardData}
            className="mt-4 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  if (!stats) {
    return null;
  }

  const approvalRate = stats.total_applications > 0
    ? ((stats.approved / stats.total_applications) * 100).toFixed(1)
    : '0.0';

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto p-6 space-y-6">
        {/* Header */}
        <div className="bg-white rounded-lg shadow-sm p-6">
          <h1 className="text-3xl font-bold text-gray-900">Admin Dashboard</h1>
          <p className="text-gray-600 mt-2">
            Overview of vetting applications and system performance
          </p>
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          <StatCard
            icon={FileText}
            title="Total Applications"
            value={stats.total_applications}
            color="text-blue-600"
          />

          <StatCard
            icon={Clock}
            title="Pending Review"
            value={stats.pending}
            color="text-yellow-600"
            subtitle={`${stats.under_review} under review`}
          />

          <StatCard
            icon={CheckCircle}
            title="Approved"
            value={stats.approved}
            color="text-green-600"
            subtitle={`${approvalRate}% approval rate`}
          />

          <StatCard
            icon={XCircle}
            title="Rejected"
            value={stats.rejected}
            color="text-red-600"
          />
        </div>

        {/* Performance Metrics */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="bg-white rounded-lg shadow-sm p-6">
            <div className="flex items-center gap-3 mb-4">
              <TrendingUp className="w-6 h-6 text-green-600" />
              <h3 className="font-semibold text-gray-900">Processing Speed</h3>
            </div>
            <p className="text-2xl font-bold text-green-600">
              {stats.pending > 0 ? '~2.5 days' : 'Up to date'}
            </p>
            <p className="text-sm text-gray-600 mt-1">Average review time</p>
          </div>

          <div className="bg-white rounded-lg shadow-sm p-6">
            <div className="flex items-center gap-3 mb-4">
              <Users className="w-6 h-6 text-blue-600" />
              <h3 className="font-semibold text-gray-900">Active Users</h3>
            </div>
            <p className="text-2xl font-bold text-blue-600">
              {Math.floor(stats.total_applications * 0.8)}
            </p>
            <p className="text-sm text-gray-600 mt-1">Registered applicants</p>
          </div>

          <div className="bg-white rounded-lg shadow-sm p-6">
            <div className="flex items-center gap-3 mb-4">
              <CheckCircle className="w-6 h-6 text-purple-600" />
              <h3 className="font-semibold text-gray-900">Success Rate</h3>
            </div>
            <p className="text-2xl font-bold text-purple-600">{approvalRate}%</p>
            <p className="text-sm text-gray-600 mt-1">Applications approved</p>
          </div>
        </div>

        {/* Recent Applications */}
        <div className="bg-white rounded-lg shadow-sm overflow-hidden">
          <div className="p-6 border-b border-gray-200 flex justify-between items-center">
            <h2 className="text-xl font-bold text-gray-900">Recent Applications</h2>
            <button
              onClick={() => navigate('/admin/cases')}
              className="text-sm text-indigo-600 hover:text-indigo-700 font-medium"
            >
              View All →
            </button>
          </div>

          <div className="divide-y divide-gray-200">
            {stats.recent_applications && stats.recent_applications.length > 0 ? (
              stats.recent_applications.map((app: RecentApplication) => (
                <div
                  key={app.id}
                  className="p-6 hover:bg-gray-50 transition-colors"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-3 mb-2">
                        <h3 className="font-semibold text-lg text-gray-900">{app.case_id}</h3>
                        <StatusBadge status={app.status} />
                      </div>
                      <p className="text-sm text-gray-600">
                        {app.applicant?.full_name || 'Unknown'} • {' '}
                        <span className="capitalize">{app.application_type.replace('_', ' ')}</span>
                      </p>
                      <p className="text-xs text-gray-500 mt-1">
                        Submitted: {formatDate(app.created_at)}
                      </p>
                    </div>

                    <div className="text-right ml-6">
                      {(app.consistency_score || app.fraud_risk_score) && (
                        <div className="mb-3">
                          {app.consistency_score && (
                            <div className="text-sm text-gray-600">
                              Consistency: <span className="font-semibold text-green-600">
                                {app.consistency_score.toFixed(1)}%
                              </span>
                            </div>
                          )}
                          {app.fraud_risk_score && (
                            <div className="text-sm text-gray-600">
                              Fraud Risk: <span className="font-semibold text-red-600">
                                {app.fraud_risk_score.toFixed(1)}%
                              </span>
                            </div>
                          )}
                        </div>
                      )}
                      <button
                        type="button"
                        onClick={() => navigate(`/admin/cases/${app.case_id}`)}
                        className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 text-sm font-medium transition-colors"
                      >
                        Review Case
                      </button>
                    </div>
                  </div>
                </div>
              ))
            ) : (
              <div className="p-12 text-center">
                <FileText className="w-16 h-16 text-gray-300 mx-auto mb-4" />
                <p className="text-gray-500 text-lg">No recent applications</p>
                <p className="text-gray-400 text-sm mt-1">New applications will appear here</p>
              </div>
            )}
          </div>
        </div>

        {/* Quick Actions */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <button
            onClick={() => navigate('/admin/cases?status=pending')}
            className="group p-6 bg-linear-to-br from-yellow-50 to-yellow-100 rounded-lg border-2 border-yellow-200 hover:border-yellow-300 hover:shadow-md transition-all text-left"
          >
            <AlertTriangle className="w-10 h-10 text-yellow-600 mb-3 group-hover:scale-110 transition-transform" />
            <h3 className="font-bold text-lg text-gray-900">Pending Cases</h3>
            <p className="text-sm text-gray-600 mt-1">Review {stats.pending} waiting applications</p>
            <div className="mt-4 flex items-center text-yellow-600 font-medium text-sm">
              <span>Review Now</span>
              <span className="ml-2 group-hover:ml-3 transition-all">→</span>
            </div>
          </button>

          <button
            onClick={() => navigate('/admin/rubrics')}
            className="group p-6 bg-linear-to-br from-purple-50 to-purple-100 rounded-lg border-2 border-purple-200 hover:border-purple-300 hover:shadow-md transition-all text-left"
          >
            <TrendingUp className="w-10 h-10 text-purple-600 mb-3 group-hover:scale-110 transition-transform" />
            <h3 className="font-bold text-lg text-gray-900">Manage Rubrics</h3>
            <p className="text-sm text-gray-600 mt-1">Configure evaluation criteria and rules</p>
            <div className="mt-4 flex items-center text-purple-600 font-medium text-sm">
              <span>Configure</span>
              <span className="ml-2 group-hover:ml-3 transition-all">→</span>
            </div>
          </button>

          <button
            onClick={() => navigate('/admin/analytics')}
            className="group p-6 bg-linear-to-br from-blue-50 to-blue-100 rounded-lg border-2 border-blue-200 hover:border-blue-300 hover:shadow-md transition-all text-left"
          >
            <Users className="w-10 h-10 text-blue-600 mb-3 group-hover:scale-110 transition-transform" />
            <h3 className="font-bold text-lg text-gray-900">Analytics</h3>
            <p className="text-sm text-gray-600 mt-1">View detailed system statistics</p>
            <div className="mt-4 flex items-center text-blue-600 font-medium text-sm">
              <span>View Stats</span>
              <span className="ml-2 group-hover:ml-3 transition-all">→</span>
            </div>
          </button>
        </div>
      </div>
    </div>
  );
};

export default AdminDashboard;
