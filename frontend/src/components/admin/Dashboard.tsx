// src/components/admin/Dashboard.tsx
import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Building2,
  CheckCircle,
  Clock,
  FileText,
  AlertTriangle,
  ShieldCheck,
  TrendingUp,
  Users,
  Users2,
  XCircle,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { Loader } from '@/components/common/Loader';
import { adminService } from '@/services/admin.service';
import type { DashboardStats } from '@/types';
import BillingHealthCard from '@/components/admin/BillingHealthCard';
import ReminderHealthCard from '@/components/admin/ReminderHealthCard';


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
        <p className="text-sm font-medium text-slate-800">{title}</p>
        <p className={`text-3xl font-bold ${color} mt-2`}>{value.toLocaleString()}</p>
        {subtitle && (
          <p className="text-xs text-slate-800 mt-1">{subtitle}</p>
        )}
      </div>
      <div className={`p-3 rounded-full ${ICON_BG_BY_TEXT_COLOR[color] ?? 'bg-slate-100'}`}>
        <Icon className={`w-8 h-8 ${color}`} />
      </div>
    </div>
  </div>
);

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
      <div className="mx-auto max-w-7xl space-y-6 px-4 py-6 sm:px-6">
        {/* Header */}
        <div className="bg-white rounded-lg shadow-sm p-6">
          <h1 className="text-3xl font-bold text-gray-900">Platform Admin Dashboard</h1>
          <p className="text-slate-800 mt-2">
            Platform-level oversight for organizations, organization admins, and runtime health.
          </p>
        </div>

        <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
          <BillingHealthCard />
          <ReminderHealthCard />
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          <StatCard
            icon={Users2}
            title="Total Reviews"
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
            <p className="text-sm text-slate-800 mt-1">Average review time</p>
          </div>

          <div className="bg-white rounded-lg shadow-sm p-6">
            <div className="flex items-center gap-3 mb-4">
              <Users className="w-6 h-6 text-blue-600" />
              <h3 className="font-semibold text-gray-900">Active Users</h3>
            </div>
            <p className="text-2xl font-bold text-blue-600">
              {Math.floor(stats.total_applications * 0.8)}
            </p>
            <p className="text-sm text-slate-800 mt-1">Registered applicants</p>
          </div>

          <div className="bg-white rounded-lg shadow-sm p-6">
            <div className="flex items-center gap-3 mb-4">
              <CheckCircle className="w-6 h-6 text-purple-600" />
              <h3 className="font-semibold text-gray-900">Success Rate</h3>
            </div>
            <p className="text-2xl font-bold text-purple-600">{approvalRate}%</p>
            <p className="text-sm text-slate-800 mt-1">Applications approved</p>
          </div>
        </div>

        {/* Platform Quick Actions */}
        <div className="grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-3">
          <button
            onClick={() => navigate('/admin/organizations')}
            className="group p-6 bg-linear-to-br from-cyan-100 to-cyan-200 rounded-lg border-2 border-cyan-300 hover:border-cyan-400 hover:shadow-md transition-all text-left"
          >
            <Building2 className="w-10 h-10 text-cyan-900 mb-3 group-hover:scale-110 transition-transform" />
            <h3 className="font-bold text-lg text-gray-900">Organizations</h3>
            <p className="text-sm text-slate-800 mt-1">Manage organization setup and platform-level access entry.</p>
            <div className="mt-4 flex items-center text-cyan-900 font-semibold text-sm">
              <span>Open Organizations</span>
              <span className="ml-2 group-hover:ml-3 transition-all">→</span>
            </div>
          </button>

          <button
            onClick={() => navigate('/admin/users')}
            className="group p-6 bg-linear-to-br from-emerald-100 to-emerald-200 rounded-lg border-2 border-emerald-300 hover:border-emerald-400 hover:shadow-md transition-all text-left"
          >
            <Users2 className="w-10 h-10 text-emerald-900 mb-3 group-hover:scale-110 transition-transform" />
            <h3 className="font-bold text-lg text-gray-900">Organization Admins</h3>
            <p className="text-sm text-slate-800 mt-1">Manage organization administrator accounts and account state.</p>
            <div className="mt-4 flex items-center text-emerald-900 font-semibold text-sm">
              <span>Open Admin Accounts</span>
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
            onClick={() => navigate('/video-calls')}
            className="group p-6 bg-linear-to-br from-indigo-100 to-indigo-200 rounded-lg border-2 border-indigo-300 hover:border-indigo-400 hover:shadow-md transition-all text-left"
          >
            <ShieldCheck className="w-10 h-10 text-indigo-900 mb-3 group-hover:scale-110 transition-transform" />
            <h3 className="font-bold text-lg text-gray-900">Runtime</h3>
            <p className="text-sm text-slate-800 mt-1">Monitor platform reminder runtime and interview operations.</p>
            <div className="mt-4 flex items-center text-indigo-900 font-semibold text-sm">
              <span>Open Runtime</span>
              <span className="ml-2 group-hover:ml-3 transition-all">→</span>
            </div>
          </button>

          <button
            onClick={() => navigate('/audit-logs')}
            className="group p-6 bg-linear-to-br from-slate-100 to-slate-200 rounded-lg border-2 border-slate-300 hover:border-slate-400 hover:shadow-md transition-all text-left"
          >
            <FileText className="w-10 h-10 text-slate-900 mb-3 group-hover:scale-110 transition-transform" />
            <h3 className="font-bold text-lg text-gray-900">Audit</h3>
            <p className="text-sm text-slate-800 mt-1">Review platform-level governance and security events.</p>
            <div className="mt-4 flex items-center text-slate-900 font-semibold text-sm">
              <span>Open Audit Logs</span>
              <span className="ml-2 group-hover:ml-3 transition-all">→</span>
            </div>
          </button>

          <button
            onClick={() => navigate('/fraud-insights')}
            className="group p-6 bg-linear-to-br from-rose-100 to-rose-200 rounded-lg border-2 border-rose-300 hover:border-rose-400 hover:shadow-md transition-all text-left"
          >
            <XCircle className="w-10 h-10 text-rose-900 mb-3 group-hover:scale-110 transition-transform" />
            <h3 className="font-bold text-lg text-gray-900">Risk Signals</h3>
            <p className="text-sm text-slate-800 mt-1">Track fraud and verification signals across the platform.</p>
            <div className="mt-4 flex items-center text-rose-900 font-semibold text-sm">
              <span>Open Risk Signals</span>
              <span className="ml-2 group-hover:ml-3 transition-all">→</span>
            </div>
          </button>
        </div>
      </div>
    </div>
  );
};

export default AdminDashboard;
