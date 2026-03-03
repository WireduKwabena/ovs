import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ArrowLeft, Upload, Users, Mail, Activity, RefreshCw, Copy, Send, CheckCircle2 } from 'lucide-react';
import type {
  CandidateEnrollment,
  CandidateImportResult,
  CandidateImportRow,
  CampaignDashboard,
  Invitation,
  VettingCampaign,
} from '@/types';
import { campaignService } from '@/services/campaign.service';
import { invitationService } from '@/services/invitation.service';
import { candidateService } from '@/services/candidate.service';
import { formatDate, formatDateTime } from '@/utils/helper';
import { toast } from 'react-toastify';

const getErrorMessage = (error: unknown, fallback: string): string => {
  if (!error) {
    return fallback;
  }

  if (typeof error === 'string') {
    return error;
  }

  if (error instanceof Error && error.message) {
    return error.message;
  }

  const normalizedError = error as {
    message?: string;
    response?: {
      data?: {
        detail?: string;
        error?: string;
        message?: string;
      };
    };
  };

  return (
    normalizedError.response?.data?.detail ||
    normalizedError.response?.data?.error ||
    normalizedError.response?.data?.message ||
    normalizedError.message ||
    fallback
  );
};

const defaultImportPayload = `[
  {
    "first_name": "Ama",
    "last_name": "Mensah",
    "email": "ama.mensah@example.com",
    "phone_number": "+233200000001",
    "preferred_channel": "email"
  }
]`;

const CampaignWorkspacePage: React.FC = () => {
  const { campaignId } = useParams<{ campaignId: string }>();
  const [campaign, setCampaign] = useState<VettingCampaign | null>(null);
  const [dashboard, setDashboard] = useState<CampaignDashboard | null>(null);
  const [enrollments, setEnrollments] = useState<CandidateEnrollment[]>([]);
  const [invitations, setInvitations] = useState<Invitation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [importPayload, setImportPayload] = useState(defaultImportPayload);
  const [sendInvites, setSendInvites] = useState(true);
  const [importing, setImporting] = useState(false);
  const [importSummary, setImportSummary] = useState<CandidateImportResult | null>(null);
  const [resendingInvitationId, setResendingInvitationId] = useState<number | null>(null);
  const [completingEnrollmentId, setCompletingEnrollmentId] = useState<number | null>(null);

  const loadWorkspace = useCallback(async () => {
    if (!campaignId) {
      setError('Campaign id is missing.');
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const [campaignData, dashboardData, enrollmentData, invitationData] = await Promise.all([
        campaignService.getById(campaignId),
        campaignService.getDashboard(campaignId),
        campaignService.getEnrollments(campaignId),
        campaignService.getInvitations(campaignId),
      ]);

      setCampaign(campaignData);
      setDashboard(dashboardData);
      setEnrollments(enrollmentData);
      setInvitations(invitationData);
    } catch (err: unknown) {
      setError(getErrorMessage(err, 'Failed to load campaign workspace.'));
    } finally {
      setLoading(false);
    }
  }, [campaignId]);

  useEffect(() => {
    void loadWorkspace();
  }, [loadWorkspace]);

  const latestInvitations = useMemo(() => {
    return invitations.slice(0, 8);
  }, [invitations]);

  const handleImportCandidates = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!campaignId) {
      setError('Campaign id is missing.');
      return;
    }

    setImporting(true);
    setError(null);

    try {
      const parsed = JSON.parse(importPayload) as CandidateImportRow[];
      if (!Array.isArray(parsed) || parsed.length === 0) {
        throw new Error('Candidate payload must be a non-empty JSON array.');
      }

      const summary = await campaignService.importCandidates(campaignId, {
        candidates: parsed,
        send_invites: sendInvites,
      });
      setImportSummary(summary);
      await loadWorkspace();
    } catch (err: unknown) {
      setError(getErrorMessage(err, 'Failed to import candidates.'));
    } finally {
      setImporting(false);
    }
  };

  const handleResendInvitation = async (invitationId: number) => {
    setResendingInvitationId(invitationId);
    setError(null);
    try {
      await invitationService.sendNow(invitationId);
      toast.success('Invitation queued for resend.');
      await loadWorkspace();
    } catch (err: unknown) {
      setError(getErrorMessage(err, 'Failed to resend invitation.'));
    } finally {
      setResendingInvitationId(null);
    }
  };

  const handleCopyAcceptUrl = async (invitation: Invitation) => {
    if (!invitation.accept_url) {
      setError('No accept URL available for this invitation.');
      return;
    }

    try {
      await navigator.clipboard.writeText(invitation.accept_url);
      toast.success('Invitation link copied.');
    } catch {
      setError('Unable to copy invitation link from this browser.');
    }
  };

  const handleMarkEnrollmentComplete = async (enrollmentId: number) => {
    setCompletingEnrollmentId(enrollmentId);
    setError(null);
    try {
      await candidateService.markEnrollmentComplete(enrollmentId);
      toast.success('Enrollment marked as completed.');
      await loadWorkspace();
    } catch (err: unknown) {
      setError(getErrorMessage(err, 'Failed to mark enrollment as completed.'));
    } finally {
      setCompletingEnrollmentId(null);
    }
  };

  if (loading) {
    return (
      <main className="max-w-7xl mx-auto px-4 py-10">
        <div className="rounded-xl border border-slate-200 bg-white p-10 text-center text-slate-500">
          Loading campaign workspace...
        </div>
      </main>
    );
  }

  if (!campaign) {
    return (
      <main className="max-w-4xl mx-auto px-4 py-10">
        <div className="rounded-xl border border-red-200 bg-red-50 p-6 text-red-700">
          {error || 'Campaign not found.'}
        </div>
      </main>
    );
  }

  return (
    <main className="max-w-7xl mx-auto px-4 py-8 space-y-6">
      <section className="rounded-2xl bg-white border border-slate-200 p-6">
        <div className="flex flex-wrap gap-3 items-center justify-between">
          <div>
            <Link to="/campaigns" className="inline-flex items-center gap-1 text-sm text-indigo-600 hover:text-indigo-700">
              <ArrowLeft className="w-4 h-4" />
              Back to campaigns
            </Link>
            <h1 className="text-2xl font-semibold mt-2">{campaign.name}</h1>
            <p className="text-slate-600 mt-1">{campaign.description || 'No description provided.'}</p>
          </div>
          <button
            type="button"
            onClick={() => void loadWorkspace()}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg border border-slate-200 hover:bg-slate-50"
          >
            <RefreshCw className="w-4 h-4" />
            Refresh
          </button>
        </div>
        <div className="mt-4 text-sm text-slate-500">
          Status: <span className="font-medium text-slate-700">{campaign.status}</span> | Created on{' '}
          {formatDate(campaign.created_at)}
        </div>
      </section>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-red-700">
          {error}
        </div>
      )}

      {dashboard && (
        <section className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <p className="text-sm text-slate-500">Total</p>
            <p className="text-2xl font-semibold">{dashboard.total_candidates}</p>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <p className="text-sm text-slate-500">Invited</p>
            <p className="text-2xl font-semibold">{dashboard.invited}</p>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <p className="text-sm text-slate-500">In Progress</p>
            <p className="text-2xl font-semibold">{dashboard.in_progress}</p>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <p className="text-sm text-slate-500">Completed</p>
            <p className="text-2xl font-semibold">{dashboard.completed}</p>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <p className="text-sm text-slate-500">Approved</p>
            <p className="text-2xl font-semibold">{dashboard.approved}</p>
          </div>
        </section>
      )}

      <section className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="rounded-xl border border-slate-200 bg-white p-5">
          <h2 className="text-lg font-semibold inline-flex items-center gap-2 mb-4">
            <Upload className="w-5 h-5 text-indigo-600" />
            Import Candidates
          </h2>
          <form className="space-y-3" onSubmit={handleImportCandidates}>
            <div>
              <label htmlFor="campaign-import-payload" className="block text-sm font-medium text-slate-700 mb-1">
                Payload (JSON array)
              </label>
              <textarea
                id="campaign-import-payload"
                rows={12}
                value={importPayload}
                onChange={(event) => setImportPayload(event.target.value)}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 font-mono text-sm focus:ring-2 focus:ring-indigo-400 outline-none"
              />
            </div>
            <label className="inline-flex items-center gap-2 text-sm text-slate-700">
              <input
                type="checkbox"
                checked={sendInvites}
                onChange={(event) => setSendInvites(event.target.checked)}
              />
              Send invitations immediately after import
            </label>
            <button
              type="submit"
              disabled={importing}
              className="w-full rounded-lg bg-indigo-600 text-white py-2 px-4 font-medium hover:bg-indigo-700 disabled:opacity-60"
            >
              {importing ? 'Importing...' : 'Import Candidates'}
            </button>
          </form>

          {importSummary && (
            <div className="mt-4 rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">
              <p>
                Imported: {importSummary.created_candidates} new candidates, {importSummary.created_enrollments}{' '}
                enrollments, {importSummary.created_invitations} invitations.
              </p>
              {importSummary.errors.length > 0 && (
                <ul className="mt-2 list-disc pl-5">
                  {importSummary.errors.map((row, index) => (
                    <li key={`${row.email || 'unknown'}-${index}`}>
                      {(row.email || 'unknown email')}: {row.error}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-5">
          <h2 className="text-lg font-semibold inline-flex items-center gap-2 mb-4">
            <Users className="w-5 h-5 text-indigo-600" />
            Enrollments ({enrollments.length})
          </h2>
          {enrollments.length === 0 ? (
            <p className="text-slate-500 text-sm">No enrollments yet.</p>
          ) : (
            <div className="max-h-[430px] overflow-auto space-y-2 pr-1">
              {enrollments.map((enrollment) => (
                <article
                  key={enrollment.id}
                  className="rounded-lg border border-slate-200 px-3 py-2 flex items-center justify-between gap-3"
                >
                  <div>
                    <p className="font-medium text-slate-800">{enrollment.candidate_email || `Candidate #${enrollment.candidate}`}</p>
                    <p className="text-xs text-slate-500">
                      Invited: {enrollment.invited_at ? formatDateTime(enrollment.invited_at) : 'N/A'}
                    </p>
                  </div>
                  <span className="text-xs rounded-full px-2.5 py-1 bg-slate-100 text-slate-700">
                    {enrollment.status}
                  </span>
                  {!['completed', 'reviewed', 'approved', 'rejected', 'escalated'].includes(enrollment.status) && (
                    <button
                      type="button"
                      onClick={() => void handleMarkEnrollmentComplete(enrollment.id)}
                      disabled={completingEnrollmentId === enrollment.id}
                      className="inline-flex items-center gap-1 rounded border border-slate-200 px-2 py-1 text-xs hover:bg-slate-50 disabled:opacity-60"
                    >
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      {completingEnrollmentId === enrollment.id ? 'Updating...' : 'Mark Complete'}
                    </button>
                  )}
                </article>
              ))}
            </div>
          )}
        </div>
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-5">
        <h2 className="text-lg font-semibold inline-flex items-center gap-2 mb-4">
          <Mail className="w-5 h-5 text-indigo-600" />
          Latest Invitations
        </h2>
        {latestInvitations.length === 0 ? (
          <p className="text-slate-500 text-sm">No invitations found for this campaign.</p>
        ) : (
          <div className="overflow-auto">
            <table className="w-full min-w-[720px] text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-left text-slate-500">
                  <th className="py-2 pr-3 font-medium">Send To</th>
                  <th className="py-2 pr-3 font-medium">Channel</th>
                  <th className="py-2 pr-3 font-medium">Status</th>
                  <th className="py-2 pr-3 font-medium">Expires</th>
                  <th className="py-2 pr-3 font-medium">Attempts</th>
                  <th className="py-2 pr-3 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {latestInvitations.map((invitation) => (
                  <tr key={invitation.id} className="border-b border-slate-100">
                    <td className="py-2 pr-3">{invitation.send_to}</td>
                    <td className="py-2 pr-3 uppercase">{invitation.channel}</td>
                    <td className="py-2 pr-3">{invitation.status}</td>
                    <td className="py-2 pr-3">{formatDateTime(invitation.expires_at)}</td>
                    <td className="py-2 pr-3">{invitation.attempts}</td>
                    <td className="py-2 pr-3">
                      <div className="flex items-center gap-2">
                        {invitation.status !== 'accepted' && invitation.status !== 'expired' && (
                          <button
                            type="button"
                            onClick={() => void handleResendInvitation(invitation.id)}
                            disabled={resendingInvitationId === invitation.id}
                            className="inline-flex items-center gap-1 rounded border border-slate-200 px-2 py-1 text-xs hover:bg-slate-50 disabled:opacity-60"
                          >
                            <Send className="w-3.5 h-3.5" />
                            {resendingInvitationId === invitation.id ? 'Sending...' : 'Resend'}
                          </button>
                        )}
                        {invitation.accept_url && (
                          <button
                            type="button"
                            onClick={() => void handleCopyAcceptUrl(invitation)}
                            className="inline-flex items-center gap-1 rounded border border-slate-200 px-2 py-1 text-xs hover:bg-slate-50"
                          >
                            <Copy className="w-3.5 h-3.5" />
                            Copy URL
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-5">
        <h2 className="text-lg font-semibold inline-flex items-center gap-2 mb-3">
          <Activity className="w-5 h-5 text-indigo-600" />
          Candidate Entry Point
        </h2>
        <p className="text-sm text-slate-600">
          Candidates should use the access URL received through email/SMS. Legacy invitation links are still accepted
          at <code className="bg-slate-100 px-1 py-0.5 rounded text-xs">/invite/&lt;token&gt;</code>.
        </p>
      </section>
    </main>
  );
};

export default CampaignWorkspacePage;
