import React, { Suspense, useEffect, useMemo } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { FileText, Clock, CheckCircle, XCircle, Plus, AlertCircle, TrendingUp } from 'lucide-react';
import { StatusBadge } from '@/components/common/StatusBadge';
import { Loader } from '@/components/common/Loader';
import { useApplications } from '@/hooks/useApplications';
import { useAuth } from '@/hooks/useAuth';
import { formatDate } from '@/utils/helper';

const HrDashboardPage = React.lazy(() => import('@/pages/HrDashboardPage'));

interface StatCardProps {
  icon: React.ElementType;
  title: string;
  value: number;
  color: string;
  hint?: string;
}

const StatCard: React.FC<StatCardProps> = ({ icon: Icon, title, value, color, hint }) => (
  <div className="rounded-xl border border-slate-200 bg-white p-5">
    <div className="flex items-center justify-between">
      <Icon className={`w-6 h-6 ${color}`} />
      {hint ? <span className="text-xs text-slate-500">{hint}</span> : null}
    </div>
    <p className="mt-2 text-sm text-slate-500">{title}</p>
    <p className={`text-3xl font-semibold ${color}`}>{value}</p>
  </div>
);

const ApplicantDashboardPage: React.FC = () => {
  const navigate = useNavigate();
  const { user } = useAuth();
  const { applications, loading, refetch } = useApplications();

  useEffect(() => {
    refetch();
  }, [refetch]);

  const applicationsArray = useMemo(() => (Array.isArray(applications) ? applications : []), [applications]);

  const stats = useMemo(() => {
    return applicationsArray.reduce(
      (acc, app) => {
        acc.total += 1;
        if (app.status === 'pending' || app.status === 'under_review') {
          acc.pendingReview += 1;
        }
        if (app.status === 'approved') {
          acc.approved += 1;
        }
        if (app.status === 'rejected') {
          acc.rejected += 1;
        }
        return acc;
      },
      { total: 0, pendingReview: 0, approved: 0, rejected: 0 }
    );
  }, [applicationsArray]);

  const recentApplications = useMemo(() => applicationsArray.slice(0, 5), [applicationsArray]);

  const displayName = user ? ('full_name' in user ? user.full_name : user.username) : 'User';

  return (
    <main className="max-w-7xl mx-auto px-4 py-8 space-y-6">
      <section className="rounded-2xl bg-gradient-to-br from-indigo-700 via-indigo-600 to-cyan-600 text-white p-6">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-2xl font-semibold">Welcome back, {displayName}</h1>
            <p className="text-indigo-100 mt-1">Track your vetting cases and next required actions.</p>
          </div>
          <button
            type="button"
            onClick={() => navigate('/applications/new')}
            className="inline-flex items-center gap-2 rounded-lg bg-white px-4 py-2 font-medium text-indigo-700 hover:bg-indigo-50"
          >
            <Plus className="w-4 h-4" />
            New Application
          </button>
        </div>
      </section>

      <section className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
        <StatCard icon={FileText} title="Total Applications" value={stats.total} color="text-slate-900" />
        <StatCard icon={Clock} title="Pending Review" value={stats.pendingReview} color="text-amber-600" />
        <StatCard
          icon={CheckCircle}
          title="Approved"
          value={stats.approved}
          color="text-emerald-600"
          hint="+ trend"
        />
        <StatCard icon={XCircle} title="Rejected" value={stats.rejected} color="text-rose-600" />
      </section>

      <section className="rounded-xl border border-slate-200 bg-white">
        <div className="flex items-center justify-between border-b border-slate-200 px-5 py-4">
          <h2 className="text-lg font-semibold">Recent Applications</h2>
          <Link to="/applications" className="text-sm font-medium text-indigo-600 hover:text-indigo-700">
            View all
          </Link>
        </div>

        {loading ? (
          <div className="px-5 py-10 flex items-center justify-center">
            <Loader size="lg" />
          </div>
        ) : recentApplications.length === 0 ? (
          <div className="px-5 py-10 text-center text-slate-500">No applications yet.</div>
        ) : (
          <ul className="divide-y divide-slate-100">
            {recentApplications.map((application) => (
              <li key={application.id} className="px-5 py-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <p className="font-medium text-slate-900">{application.case_id}</p>
                      <StatusBadge status={application.status} />
                    </div>
                    <p className="text-sm text-slate-600 mt-1">
                      {application.application_type.replace('_', ' ')} | Priority: {application.priority}
                    </p>
                    <p className="text-xs text-slate-500 mt-1">Submitted: {formatDate(application.created_at)}</p>
                  </div>
                  <Link
                    to={`/applications/${application.case_id}`}
                    className="inline-flex items-center gap-1 text-sm font-medium text-indigo-600 hover:text-indigo-700"
                  >
                    Open case
                    <TrendingUp className="w-4 h-4" />
                  </Link>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <button
          type="button"
          onClick={() => navigate('/applications/new')}
          className="rounded-xl border border-blue-200 bg-blue-50 p-5 text-left hover:bg-blue-100"
        >
          <Plus className="w-7 h-7 text-blue-600" />
          <p className="font-semibold mt-2">Create Application</p>
          <p className="text-sm text-slate-600">Start a new vetting request.</p>
        </button>

        <button
          type="button"
          onClick={() => navigate('/applications')}
          className="rounded-xl border border-indigo-200 bg-indigo-50 p-5 text-left hover:bg-indigo-100"
        >
          <FileText className="w-7 h-7 text-indigo-600" />
          <p className="font-semibold mt-2">My Applications</p>
          <p className="text-sm text-slate-600">Review all submitted cases.</p>
        </button>

        <button
          type="button"
          onClick={() => navigate('/notifications')}
          className="rounded-xl border border-emerald-200 bg-emerald-50 p-5 text-left hover:bg-emerald-100"
        >
          <AlertCircle className="w-7 h-7 text-emerald-600" />
          <p className="font-semibold mt-2">Notifications</p>
          <p className="text-sm text-slate-600">Check updates from reviewers.</p>
        </button>
      </section>
    </main>
  );
};

export const DashboardPage: React.FC = () => {
  const { userType } = useAuth();

  if (userType === 'hr_manager' || userType === 'admin') {
    return (
      <Suspense
        fallback={
          <main className="max-w-7xl mx-auto px-4 py-10">
            <div className="rounded-xl border border-slate-200 bg-white p-10 flex items-center justify-center">
              <Loader size="lg" />
            </div>
          </main>
        }
      >
        <HrDashboardPage />
      </Suspense>
    );
  }

  return <ApplicantDashboardPage />;
};

export default DashboardPage;
