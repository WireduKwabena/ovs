// src/pages/DashboardPage.tsx
import React, { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  FileText, 
  Clock, 
  CheckCircle, 
  XCircle, 
  Plus,
  TrendingUp,
  AlertCircle
} from 'lucide-react';
import { StatusBadge } from '@/components/common/StatusBadge';
import { Loader } from '@/components/common/Loader';
import { useApplications } from '@/hooks/useApplications';
import { useAuth } from '@/hooks/useAuth';
import type { ApplicationStatus } from '@/types';
import { formatDate } from '@/utils/helper';
import { Navbar } from '@/components/common/Navbar';

interface StatCardProps {
  icon: React.ElementType;
  title: string;
  value: number;
  color: string;
  trend?: string;
}

const StatCard: React.FC<StatCardProps> = ({ icon: Icon, title, value, color, trend }) => (
  <div className="bg-white rounded-lg shadow-sm p-6 hover:shadow-md transition-shadow">
    <div className="flex items-center justify-between mb-4">
      <Icon className={`w-8 h-8 ${color}`} />
      {trend && (
        <span className="flex items-center text-green-600 text-sm font-medium">
          <TrendingUp className="w-4 h-4 mr-1" />
          {trend}
        </span>
      )}
    </div>
    <p className="text-sm text-gray-600 mb-1">{title}</p>
    <p className={`text-3xl font-bold ${color}`}>{value}</p>
  </div>
);

export const DashboardPage: React.FC = () => {
  const navigate = useNavigate();
  const { user } = useAuth();
  const { applications, loading, refetch } = useApplications();

   

  useEffect(() => {
    refetch();
  }, [refetch]);

   // ✅ Always ensure we have an array
  const applicationsArray = React.useMemo(() => {
    return Array.isArray(applications) ? applications : [];
  }, [applications]);

  const getStatusCount = (status: ApplicationStatus): number => {
    return applicationsArray.filter(app => app.status === status).length;
  };

  const recentApplications = React.useMemo(() => {
    return applicationsArray.slice(0, 5);
  }, [applicationsArray]);

  const stats = React.useMemo(() => ({
    total: applicationsArray.length,
    pending: getStatusCount('pending'),
    under_review: getStatusCount('under_review'),
    approved: getStatusCount('approved'),
    rejected: getStatusCount('rejected'),
  }), [applicationsArray]);


  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />
      
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Welcome Section */}
        <div className="bg-linear-to-r from-indigo-600 to-purple-600 rounded-lg shadow-lg p-8 mb-8 text-white">
          <div className="flex justify-between items-start">
            <div>
              <h1 className="text-3xl font-bold mb-2">
                Welcome back, {user && ('full_name' in user ? user.full_name : user.username) || 'User'}!
              </h1>
              <p className="text-indigo-100">
                Track and manage your vetting applications from your dashboard
              </p>
            </div>
            <button
            type='button'
              onClick={() => navigate('/applications/new')}
              className="inline-flex items-center gap-2 px-6 py-3 bg-white text-indigo-600 rounded-lg hover:bg-indigo-50 font-semibold transition-colors"
            >
              <Plus className="w-5 h-5" />
              New Application
            </button>
          </div>
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          <StatCard
            icon={FileText}
            title="Total Applications"
            value={stats.total}
            color="text-blue-600"
          />
          <StatCard
            icon={Clock}
            title="Pending Review"
            value={stats.pending + stats.under_review}
            color="text-yellow-600"
          />
          <StatCard
            icon={CheckCircle}
            title="Approved"
            value={stats.approved}
            color="text-green-600"
            trend="+12%"
          />
          <StatCard
            icon={XCircle}
            title="Rejected"
            value={stats.rejected}
            color="text-red-600"
          />
        </div>

        {/* Recent Applications */}
        <div className="bg-white rounded-lg shadow-sm">
          <div className="p-6 border-b border-gray-200 flex justify-between items-center">
            <h2 className="text-xl font-bold text-gray-900">Recent Applications</h2>
            <button
              type='button'
              onClick={() => navigate('/applications')}
              className="text-indigo-600 hover:text-indigo-700 font-medium text-sm"
            >
              View All →
            </button>
          </div>

          {loading ? (
            <div className="flex justify-center items-center py-12">
              <Loader size="lg" />
            </div>
          ) : recentApplications.length > 0 ? (
            <div className="divide-y divide-gray-200">
              {recentApplications.map((application) => (
                <div
                  key={application.id}
                  className="p-6 hover:bg-gray-50 cursor-pointer transition-colors"
                  onClick={() => navigate(`/applications/${application.case_id}`)}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-3 mb-2">
                        <h3 className="font-semibold text-lg text-gray-900">
                          {application.case_id}
                        </h3>
                        <StatusBadge status={application.status} />
                      </div>
                      <p className="text-sm text-gray-600 capitalize">
                        {application.application_type.replace('_', ' ')} • {' '}
                        Priority: {application.priority}
                      </p>
                      <p className="text-xs text-gray-500 mt-1">
                        Submitted: {formatDate(application.created_at)}
                      </p>
                    </div>
                    <button type='button' className="px-4 py-2 text-indigo-600 hover:bg-indigo-50 rounded-lg font-medium transition-colors">
                      View Details
                    </button>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="p-12 text-center">
              <FileText className="w-16 h-16 text-gray-300 mx-auto mb-4" />
              <h3 className="text-lg font-semibold text-gray-900 mb-2">No applications yet</h3>
              <p className="text-gray-600 mb-6">
                Get started by creating your first vetting application
              </p>
              <button
              type='button'
                onClick={() => navigate('/applications/new')}
                className="inline-flex items-center gap-2 px-6 py-3 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 font-medium"
              >
                <Plus className="w-5 h-5" />
                Create Application
              </button>
            </div>
          )}
        </div>

        {/* Quick Actions */}
        <div className="grid md:grid-cols-3 gap-6 mt-8">
          <button
          type='button'
            onClick={() => navigate('/applications/new')}
            className="p-6 bg-linear-to-br from-blue-50 to-blue-100 rounded-lg border-2 border-blue-200 hover:border-blue-300 hover:shadow-md transition-all text-left group h-auto"
          >
            <Plus className="w-8 h-8 text-blue-600 mb-3 group-hover:scale-110 transition-transform" />
            <h3 className="font-bold text-lg text-gray-900">New Application</h3>
            <p className="text-sm text-gray-600 mt-1">Start a new vetting process</p>
          </button>

          <button
          type='button'
            onClick={() => navigate('/applications')}
            className="p-6 bg-linear-to-br from-purple-50 to-purple-100 rounded-lg border-2 border-purple-200 hover:border-purple-300 hover:shadow-md transition-all text-left group h-auto"
          >
            <FileText className="w-8 h-8 text-purple-600 mb-3 group-hover:scale-110 transition-transform" />
            <h3 className="font-bold text-lg text-gray-900">View Applications</h3>
            <p className="text-sm text-gray-600 mt-1">Browse all your applications</p>
          </button>

          <button
          type='button'
            onClick={() => navigate('/notifications')}
            className="p-6 bg-linear-to-br from-green-50 to-green-100 rounded-lg border-2 border-green-200 hover:border-green-300 hover:shadow-md transition-all text-left group h-auto"
          >
            <AlertCircle className="w-8 h-8 text-green-600 mb-3 group-hover:scale-110 transition-transform" />
            <h3 className="font-bold text-lg text-gray-900">Notifications</h3>
            <p className="text-sm text-gray-600 mt-1">Check your updates</p>
          </button>
        </div>
      </div>
    </div>
  );
};

export default DashboardPage;