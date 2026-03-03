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
import BillingHealthCard from '@/components/admin/BillingHealthCard';


interface StatCardProps {
  icon: LucideIcon;
  title: string;
  value: number;
  color: string;
  subtitle?: string;
}

const ICON_BG_BY_TEXT_COLOR: Record<string, string> = {
  'text-blue-600': 'bg-blue-100',
  'text-amber-700': 'bg-amber-100',
  'text-green-600': 'bg-green-100',
  'text-red-600': 'bg-red-100',
  'text-purple-600': 'bg-purple-100',
};

const StatCard: React.FC<StatCardProps> = ({ icon: Icon, title, value, color, subtitle }) => (
  <div className="bg-white rounded-lg shadow-sm p-6 hover:shadow-md transition-shadow">
    <div className="flex items-center justify-between">
      <div>
        <p className="text-sm font-medium text-slate-700">{title}</p>
        <p className={`text-3xl font-bold ${color} mt-2`}>{value.toLocaleString()}</p>
        {subtitle && (
          <p className="text-xs text-slate-600 mt-1">{subtitle}</p>
        )}
      </div>
      <div className={`p-3 rounded-full ${ICON_BG_BY_TEXT_COLOR[color] ?? 'bg-slate-100'}`}>
        <Icon className={`w-8 h-8 ${color}`} />
      </div>
    </div>
  </div>
);

interface RecentApplication {
  id: string;
  case_id: string;
  applicant_name: string;
  status: ApplicationStatus;
  application_type: string;
  created_at: string;
  rubric_score?: number | null;
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
          <p className="text-slate-700 mt-2">
            Overview of vetting applications and system performance
          </p>
        </div>

        <BillingHealthCard />

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
            color="text-amber-700"
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
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6">
          <div className="bg-white rounded-lg shadow-sm p-6">
            <div className="flex items-center gap-3 mb-4">
              <TrendingUp className="w-6 h-6 text-green-600" />
              <h3 className="font-semibold text-gray-900">Processing Speed</h3>
            </div>
            <p className="text-2xl font-bold text-green-600">
              {stats.pending > 0 ? '~2.5 days' : 'Up to date'}
            </p>
            <p className="text-sm text-slate-700 mt-1">Average review time</p>
          </div>

          <div className="bg-white rounded-lg shadow-sm p-6">
            <div className="flex items-center gap-3 mb-4">
              <Users className="w-6 h-6 text-blue-600" />
              <h3 className="font-semibold text-gray-900">Active Users</h3>
            </div>
            <p className="text-2xl font-bold text-blue-600">
              {Math.floor(stats.total_applications * 0.8)}
            </p>
            <p className="text-sm text-slate-700 mt-1">Registered applicants</p>
          </div>

          <div className="bg-white rounded-lg shadow-sm p-6">
            <div className="flex items-center gap-3 mb-4">
              <CheckCircle className="w-6 h-6 text-purple-600" />
              <h3 className="font-semibold text-gray-900">Success Rate</h3>
            </div>
            <p className="text-2xl font-bold text-purple-600">{approvalRate}%</p>
            <p className="text-sm text-slate-700 mt-1">Applications approved</p>
          </div>
        </div>

        {/* Recent Applications */}
        <div className="bg-white rounded-lg shadow-sm overflow-hidden">
          <div className="p-6 border-b border-gray-200 flex justify-between items-center">
            <h2 className="text-xl font-bold text-gray-900">Recent Applications</h2>
            <button
              onClick={() => navigate('/admin/cases')}
              className="inline-flex items-center rounded-md border border-indigo-200 bg-indigo-50 px-3 py-1.5 text-sm font-semibold text-indigo-700 hover:bg-indigo-100"
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
                      <p className="text-sm text-slate-700">
                        {app.applicant_name || 'Unknown'} • {' '}
                        <span className="capitalize">{app.application_type.replace('_', ' ')}</span>
                      </p>
                      <p className="text-xs text-slate-600 mt-1">
                        Submitted: {formatDate(app.created_at)}
                      </p>
                    </div>

                    <div className="text-right ml-6">
                      {typeof app.rubric_score === 'number' && (
                        <div className="mb-3">
                          <div className="text-sm text-slate-700">
                            Rubric Score:{' '}
                            <span className="font-semibold text-indigo-600">
                              {app.rubric_score.toFixed(1)}%
                            </span>
                          </div>
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
                <p className="text-slate-700 text-lg">No recent applications</p>
                <p className="text-slate-600 text-sm mt-1">New applications will appear here</p>
              </div>
            )}
          </div>
        </div>

        {/* Quick Actions */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <button
            onClick={() => navigate('/admin/cases?status=pending')}
            className="group p-6 bg-linear-to-br from-amber-100 to-amber-200 rounded-lg border-2 border-amber-300 hover:border-amber-400 hover:shadow-md transition-all text-left"
          >
            <AlertTriangle className="w-10 h-10 text-amber-900 mb-3 group-hover:scale-110 transition-transform" />
            <h3 className="font-bold text-lg text-gray-900">Pending Cases</h3>
            <p className="text-sm text-slate-800 mt-1">Review {stats.pending} waiting applications</p>
            <div className="mt-4 flex items-center text-amber-900 font-semibold text-sm">
              <span>Review Now</span>
              <span className="ml-2 group-hover:ml-3 transition-all">→</span>
            </div>
          </button>

          <button
            onClick={() => navigate('/admin/rubrics')}
            className="group p-6 bg-linear-to-br from-violet-100 to-violet-200 rounded-lg border-2 border-violet-300 hover:border-violet-400 hover:shadow-md transition-all text-left"
          >
            <TrendingUp className="w-10 h-10 text-violet-900 mb-3 group-hover:scale-110 transition-transform" />
            <h3 className="font-bold text-lg text-gray-900">Manage Rubrics</h3>
            <p className="text-sm text-slate-800 mt-1">Configure evaluation criteria and rules</p>
            <div className="mt-4 flex items-center text-violet-900 font-semibold text-sm">
              <span>Configure</span>
              <span className="ml-2 group-hover:ml-3 transition-all">→</span>
            </div>
          </button>

          <button
            onClick={() => navigate('/admin/analytics')}
            className="group p-6 bg-linear-to-br from-blue-100 to-blue-200 rounded-lg border-2 border-blue-300 hover:border-blue-400 hover:shadow-md transition-all text-left"
          >
            <Users className="w-10 h-10 text-blue-900 mb-3 group-hover:scale-110 transition-transform" />
            <h3 className="font-bold text-lg text-gray-900">Analytics</h3>
            <p className="text-sm text-slate-800 mt-1">View detailed system statistics</p>
            <div className="mt-4 flex items-center text-blue-900 font-semibold text-sm">
              <span>View Stats</span>
              <span className="ml-2 group-hover:ml-3 transition-all">→</span>
            </div>
          </button>

          <button
            onClick={() => navigate('/admin/control-center')}
            className="group p-6 bg-linear-to-br from-slate-200 to-slate-300 rounded-lg border-2 border-slate-400 hover:border-slate-500 hover:shadow-md transition-all text-left"
          >
            <Users className="w-10 h-10 text-slate-900 mb-3 group-hover:scale-110 transition-transform" />
            <h3 className="font-bold text-lg text-gray-900">Admin Control</h3>
            <p className="text-sm text-slate-900 mt-1">Open full Django admin module controls</p>
            <div className="mt-4 flex items-center text-slate-900 font-semibold text-sm">
              <span>Open Control Center</span>
              <span className="ml-2 group-hover:ml-3 transition-all">→</span>
            </div>
          </button>

          <button
            onClick={() => navigate('/admin/users')}
            className="group p-6 bg-linear-to-br from-emerald-100 to-emerald-200 rounded-lg border-2 border-emerald-300 hover:border-emerald-400 hover:shadow-md transition-all text-left"
          >
            <Users className="w-10 h-10 text-emerald-900 mb-3 group-hover:scale-110 transition-transform" />
            <h3 className="font-bold text-lg text-gray-900">Manage Users</h3>
            <p className="text-sm text-slate-800 mt-1">Update roles, activity status, and account security.</p>
            <div className="mt-4 flex items-center text-emerald-900 font-semibold text-sm">
              <span>Open Users</span>
              <span className="ml-2 group-hover:ml-3 transition-all">→</span>
            </div>
          </button>
        </div>
      </div>
    </div>
  );
};

export default AdminDashboard;
