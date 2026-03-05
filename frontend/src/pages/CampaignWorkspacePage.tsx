import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ArrowLeft, Upload, Users, Mail, Activity, RefreshCw, Copy, Send, CheckCircle2, Info } from 'lucide-react';
import { HelpTooltip, FieldLabel } from '@/components/common/FieldHelp';
import type {
  CandidateEnrollment,
  CandidateImportResult,
  CandidateImportRow,
  CampaignDashboard,
  Invitation,
  VettingRubric,
  VettingCampaign,
} from '@/types';
import { campaignService, type CampaignRubricVersion } from '@/services/campaign.service';
import { invitationService } from '@/services/invitation.service';
import { candidateService } from '@/services/candidate.service';
import { billingService, type BillingQuotaCandidate } from '@/services/billing.service';
import { rubricService } from '@/services/rubric.service';
import { formatDate, formatDateTime } from '@/utils/helper';
import {
  extractCandidateQuotaError,
  getProjectedUsage,
  isProjectedQuotaExceeded,
  projectCandidateImport,
} from './campaignWorkspaceQuota';
import { toast } from 'react-toastify';
import { useAuth } from '@/hooks/useAuth';

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

const getSourceRubricId = (payload?: Record<string, unknown>): string | null => {
  if (!payload) {
    return null;
  }
  const sourceRubricId = payload['source_rubric_id'];
  return typeof sourceRubricId === 'string' && sourceRubricId.length > 0 ? sourceRubricId : null;
};

const CampaignWorkspacePage: React.FC = () => {
  const { userType } = useAuth();
  const { campaignId } = useParams<{ campaignId: string }>();
  const [campaign, setCampaign] = useState<VettingCampaign | null>(null);
  const [dashboard, setDashboard] = useState<CampaignDashboard | null>(null);
  const [enrollments, setEnrollments] = useState<CandidateEnrollment[]>([]);
  const [invitations, setInvitations] = useState<Invitation[]>([]);
  const [availableRubrics, setAvailableRubrics] = useState<VettingRubric[]>([]);
  const [campaignRubricVersions, setCampaignRubricVersions] = useState<CampaignRubricVersion[]>([]);
  const [selectedRubricId, setSelectedRubricId] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [applyingRubric, setApplyingRubric] = useState(false);
  const [activatingRubricVersionId, setActivatingRubricVersionId] = useState<string | null>(null);

  const [importPayload, setImportPayload] = useState(defaultImportPayload);
  const [sendInvites, setSendInvites] = useState(true);
  const [importing, setImporting] = useState(false);
  const [importSummary, setImportSummary] = useState<CandidateImportResult | null>(null);
  const [quota, setQuota] = useState<BillingQuotaCandidate | null>(null);
  const [quotaLoading, setQuotaLoading] = useState(false);
  const [quotaError, setQuotaError] = useState<string | null>(null);
  const [resendingInvitationId, setResendingInvitationId] = useState<string | null>(null);
  const [completingEnrollmentId, setCompletingEnrollmentId] = useState<string | null>(null);

  const shouldShowQuota = userType === 'hr_manager';

  const loadWorkspace = useCallback(async () => {
    if (!campaignId) {
      setError('Campaign id is missing.');
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const [
        campaignData,
        dashboardData,
        enrollmentData,
        invitationData,
        rubricsData,
        rubricVersionsData,
      ] = await Promise.all([
        campaignService.getById(campaignId),
        campaignService.getDashboard(campaignId),
        campaignService.getEnrollments(campaignId),
        campaignService.getInvitations(campaignId),
        rubricService.getAll(),
        campaignService.listRubricVersions(campaignId),
      ]);

      setCampaign(campaignData);
      setDashboard(dashboardData);
      setEnrollments(enrollmentData);
      setInvitations(invitationData);
      setAvailableRubrics(rubricsData);
      setCampaignRubricVersions(rubricVersionsData);

      const activeVersion = rubricVersionsData.find((version) => version.is_active);
      const sourceRubricId = getSourceRubricId(activeVersion?.rubric_payload) ?? '';
      if (sourceRubricId) {
        setSelectedRubricId(sourceRubricId);
      } else if (rubricsData.length > 0) {
        setSelectedRubricId((previous) => previous || String(rubricsData[0].id));
      } else {
        setSelectedRubricId('');
      }
    } catch (err: unknown) {
      setError(getErrorMessage(err, 'Failed to load campaign workspace.'));
    } finally {
      setLoading(false);
    }
  }, [campaignId]);

  useEffect(() => {
    void loadWorkspace();
  }, [loadWorkspace]);

  const fetchQuota = useCallback(async () => {
    if (!shouldShowQuota) {
      setQuota(null);
      setQuotaError(null);
      return;
    }

    setQuotaLoading(true);
    setQuotaError(null);
    try {
      const data = await billingService.getQuota();
      setQuota(data.candidate);
    } catch (err: unknown) {
      setQuotaError(getErrorMessage(err, 'Failed to load quota status.'));
    } finally {
      setQuotaLoading(false);
    }
  }, [shouldShowQuota]);

  useEffect(() => {
    void fetchQuota();
  }, [fetchQuota]);

  const latestInvitations = useMemo(() => {
    return invitations.slice(0, 8);
  }, [invitations]);

  const selectedRubric = useMemo(
    () => availableRubrics.find((rubric) => String(rubric.id) === selectedRubricId) ?? null,
    [availableRubrics, selectedRubricId],
  );

  const importProjection = useMemo(() => {
    return projectCandidateImport(importPayload);
  }, [importPayload]);

  const projectedUsage = useMemo(() => {
    return getProjectedUsage(quota, importProjection.count);
  }, [quota, importProjection.count]);

  const projectedQuotaExceeded = useMemo(() => {
    return isProjectedQuotaExceeded({
      shouldShowQuota,
      quotaLoading,
      quota,
      projectedUsage,
    });
  }, [shouldShowQuota, quotaLoading, quota, projectedUsage]);

  const handleImportCandidates = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!campaignId) {
      setError('Campaign id is missing.');
      return;
    }

    if (importProjection.parseError) {
      setError(importProjection.parseError);
      return;
    }

    if (projectedQuotaExceeded && quota && quota.limit !== null) {
      setError(
        `Import exceeds monthly quota. Current usage ${quota.used}/${quota.limit}, projected ${projectedUsage}/${quota.limit}.`
      );
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
      await fetchQuota();
    } catch (err: unknown) {
      const quotaImportError = extractCandidateQuotaError(err);
      if (quotaImportError) {
        setError(quotaImportError.detail);
        if (quotaImportError.quotaPatch) {
          setQuota((current) => (current ? { ...current, ...quotaImportError.quotaPatch } : current));
        }
      } else {
        setError(getErrorMessage(err, 'Failed to import candidates.'));
      }
    } finally {
      setImporting(false);
    }
  };

  const handleResendInvitation = async (invitationId: string) => {
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

  const handleMarkEnrollmentComplete = async (enrollmentId: string) => {
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

  const handleApplyRubricVersion = async () => {
    if (!campaignId) {
      setError('Campaign id is missing.');
      return;
    }
    if (!selectedRubric) {
      setError('Select a rubric to apply.');
      return;
    }

    setApplyingRubric(true);
    setError(null);
    try {
      const weightDocument =
        selectedRubric.document_authenticity_weight +
        selectedRubric.consistency_weight +
        selectedRubric.fraud_detection_weight;
      const weightInterview = selectedRubric.interview_weight + selectedRubric.manual_review_weight;

      await campaignService.addRubricVersion(campaignId, {
        name: `${selectedRubric.name} Snapshot`,
        description: selectedRubric.description,
        weight_document: weightDocument,
        weight_interview: weightInterview,
        passing_score: selectedRubric.passing_score,
        auto_approve_threshold: selectedRubric.auto_approve_threshold,
        auto_reject_threshold: selectedRubric.auto_reject_threshold,
        rubric_payload: {
          source_rubric_id: selectedRubric.id,
          source_rubric_name: selectedRubric.name,
          source_rubric_type: selectedRubric.rubric_type,
          source_total_weight: selectedRubric.total_weight,
          source_weights: {
            document_authenticity_weight: selectedRubric.document_authenticity_weight,
            consistency_weight: selectedRubric.consistency_weight,
            fraud_detection_weight: selectedRubric.fraud_detection_weight,
            interview_weight: selectedRubric.interview_weight,
            manual_review_weight: selectedRubric.manual_review_weight,
          },
          source_criteria_count: selectedRubric.criteria?.length ?? 0,
        },
        is_active: true,
      });

      toast.success('Rubric version applied to campaign.');
      await loadWorkspace();
    } catch (err: unknown) {
      setError(getErrorMessage(err, 'Failed to apply rubric version.'));
    } finally {
      setApplyingRubric(false);
    }
  };

  const handleActivateRubricVersion = async (versionId: string) => {
    if (!campaignId) {
      setError('Campaign id is missing.');
      return;
    }

    setActivatingRubricVersionId(versionId);
    setError(null);
    try {
      await campaignService.activateRubricVersion(campaignId, versionId);
      toast.success('Campaign rubric version set active.');
      await loadWorkspace();
    } catch (err: unknown) {
      setError(getErrorMessage(err, 'Failed to activate rubric version.'));
    } finally {
      setActivatingRubricVersionId(null);
    }
  };

  if (loading) {
    return (
      <main className="max-w-7xl mx-auto px-4 py-10">
        <div className="rounded-xl border border-slate-200 bg-white p-10 text-center text-slate-700">
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
            <p className="text-slate-700 mt-1">{campaign.description || 'No description provided.'}</p>
          </div>
          <button
            type="button"
            onClick={() => {
              void loadWorkspace();
              void fetchQuota();
            }}
            className="inline-flex w-full items-center justify-center gap-2 rounded-lg border border-slate-700 px-4 py-2 text-slate-900 hover:bg-slate-100 sm:w-auto"
          >
            <RefreshCw className="w-4 h-4" />
            Refresh
          </button>
        </div>
        <div className="mt-4 text-sm text-slate-700">
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
            <p className="text-sm text-slate-700">Total</p>
            <p className="text-2xl font-semibold">{dashboard.total_candidates}</p>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <p className="text-sm text-slate-700">Invited</p>
            <p className="text-2xl font-semibold">{dashboard.invited}</p>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <p className="text-sm text-slate-700">In Progress</p>
            <p className="text-2xl font-semibold">{dashboard.in_progress}</p>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <p className="text-sm text-slate-700">Completed</p>
            <p className="text-2xl font-semibold">{dashboard.completed}</p>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <p className="text-sm text-slate-700">Approved</p>
            <p className="text-2xl font-semibold">{dashboard.approved}</p>
          </div>
        </section>
      )}

      <section className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="rounded-xl border border-slate-200 bg-white p-5">
          <h2 className="text-lg font-semibold mb-4 inline-flex items-center gap-1.5">
            Campaign Rubric Assignment
            <HelpTooltip text="Assign a source rubric to this campaign by creating a snapshot version. This protects historical scoring consistency." />
          </h2>
          <p className="text-sm text-slate-700 mb-4">
            Select an existing rubric and snapshot it into this campaign as a new rubric version.
          </p>
          <div className="mb-4 rounded-lg border border-indigo-200 bg-indigo-50 px-3 py-2 text-xs text-indigo-900">
            Hover or focus the <Info className="mx-1 inline h-3.5 w-3.5 align-text-bottom" /> icons beside labels for guidance.
          </div>

          <FieldLabel
            htmlFor="campaign-rubric-select"
            label="Source Rubric"
            help="Pick the baseline rubric to copy into this campaign as a versioned snapshot."
            className="mb-1 flex items-center gap-1.5"
            textClassName="block text-sm font-medium text-slate-700"
          />
          <select
            title='Source Rubric - Choose a rubric from the list. This will create a snapshot version in the campaign to preserve historical scoring consistency. Only the rubric settings are copied, not the criteria or their scores.'
            id="campaign-rubric-select"
            value={selectedRubricId}
            onChange={(event) => setSelectedRubricId(event.target.value)}
            className="w-full rounded-lg border border-slate-700 px-3 py-2 focus:ring-2 focus:ring-indigo-400 outline-none"
          >
            {availableRubrics.length === 0 ? (
              <option value="">No rubrics found</option>
            ) : (
              availableRubrics.map((rubric) => (
                <option key={rubric.id} value={String(rubric.id)}>
                  {rubric.name} ({rubric.rubric_type}, {rubric.status ?? (rubric.is_active ? 'active' : 'archived')})
                </option>
              ))
            )}
          </select>

          {selectedRubric ? (
            <div className="mt-4 rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm text-slate-800">
              <p className="font-semibold text-slate-900">{selectedRubric.name}</p>
              <p className="text-xs text-slate-700 mt-1">
                Pass: {selectedRubric.passing_score}% | Auto-approve: {selectedRubric.auto_approve_threshold}% |
                Auto-reject: {selectedRubric.auto_reject_threshold}%
              </p>
              <p className="text-xs text-slate-700 mt-1">
                Criteria: {selectedRubric.criteria?.length ?? 0} | Type: {selectedRubric.rubric_type}
              </p>
            </div>
          ) : null}

          <div className="mt-4 flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={() => void handleApplyRubricVersion()}
              disabled={applyingRubric || !selectedRubric}
              title="Snapshot the selected rubric into this campaign and set it active"
              className="inline-flex items-center justify-center rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-60"
            >
              {applyingRubric ? 'Applying...' : 'Apply Rubric Version'}
            </button>
            <Link
              to="/rubrics/new"
              title="Create a new rubric in a separate page, then return to assign it here"
              className="text-sm font-medium text-indigo-600 hover:text-indigo-700"
            >
              Create new rubric
            </Link>
          </div>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-5">
          <h2 className="text-lg font-semibold mb-4 inline-flex items-center gap-1.5">
            Rubric Version History
            <HelpTooltip text="Each version stores scoring settings used at that time. Activate one version at a time for consistent evaluations." />
          </h2>
          {campaignRubricVersions.length === 0 ? (
            <p className="text-sm text-slate-700">No campaign rubric versions yet.</p>
          ) : (
            <div className="space-y-3 max-h-80 overflow-auto pr-1">
              {campaignRubricVersions.map((version) => (
                <article key={version.id} className="rounded-lg border border-slate-200 p-3">
                  {(() => {
                    const sourceRubricId = getSourceRubricId(version.rubric_payload);
                    return (
                      <>
                  <div className="flex items-center justify-between gap-2">
                    <p className="font-medium text-slate-900">
                      v{version.version}: {version.name}
                    </p>
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                        version.is_active ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-700'
                      }`}
                    >
                      {version.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </div>
                  <p className="mt-1 text-xs text-slate-700">
                    {version.description || 'No description'}
                  </p>
                  <p className="mt-1 text-xs text-slate-700">
                    Doc Weight: {version.weight_document}% | Interview Weight: {version.weight_interview}% | Pass:{' '}
                    {version.passing_score}%
                  </p>
                  <p className="mt-1 text-xs text-slate-700">Created {formatDateTime(version.created_at)}</p>
                  <div className="mt-2 flex flex-wrap items-center gap-2">
                    {!version.is_active && (
                      <button
                        type="button"
                        onClick={() => void handleActivateRubricVersion(version.id)}
                        disabled={activatingRubricVersionId === version.id}
                        className="inline-flex items-center justify-center rounded border border-slate-700 px-2 py-1 text-xs font-medium text-slate-900 hover:bg-slate-100 disabled:opacity-60"
                      >
                        {activatingRubricVersionId === version.id ? 'Activating...' : 'Set Active'}
                      </button>
                    )}
                    {sourceRubricId ? (
                      <Link
                        to={`/rubrics/${sourceRubricId}/edit`}
                        className="inline-flex items-center justify-center rounded border border-indigo-200 bg-indigo-50 px-2 py-1 text-xs font-medium text-indigo-700 hover:bg-indigo-100"
                      >
                        View Source Rubric
                      </Link>
                    ) : null}
                  </div>
                      </>
                    );
                  })()}
                </article>
              ))}
            </div>
          )}
        </div>
      </section>

      <section className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="rounded-xl border border-slate-200 bg-white p-5">
          <h2 className="text-lg font-semibold inline-flex items-center gap-2 mb-4">
            <Upload className="w-5 h-5 text-indigo-600" />
            Import Candidates
            <HelpTooltip text="Bulk import candidates with JSON. You can optionally trigger invitation delivery immediately after import." />
          </h2>
          {shouldShowQuota && (
            <div className="mb-4 rounded-lg border border-cyan-200 bg-cyan-50 p-3 text-sm text-cyan-900">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="font-semibold text-cyan-900">Monthly Candidate Quota</p>
                {quotaLoading ? (
                  <span className="text-xs text-cyan-800">Loading...</span>
                ) : quota ? (
                  <span className="rounded-full bg-cyan-100 px-2 py-0.5 text-xs font-semibold text-cyan-900">
                    {quota.limit === null ? 'Unlimited' : `${quota.used}/${quota.limit}`} used
                  </span>
                ) : (
                  <span className="text-xs text-cyan-800">Unavailable</span>
                )}
              </div>

              {quotaError && <p className="mt-1 text-xs text-red-700">{quotaError}</p>}

              {!quotaLoading && quota && (
                <div className="mt-2 space-y-1 text-xs text-cyan-900">
                  <p>
                    Plan: <span className="font-semibold">{quota.plan_name || quota.plan_id || 'Unassigned'}</span> |
                    Remaining:{' '}
                    <span className="font-semibold">
                      {quota.remaining === null ? 'Unlimited' : quota.remaining}
                    </span>
                  </p>
                  <p>
                    Window: {formatDate(quota.period_start)} - {formatDate(quota.period_end)}
                  </p>
                  <p>
                    Payload estimate: <span className="font-semibold">{importProjection.count}</span> unique candidates
                    {quota.limit !== null && (
                      <>
                        {' '}| Projected usage:{' '}
                        <span className="font-semibold">
                          {quota.used + importProjection.count}/{quota.limit}
                        </span>
                      </>
                    )}
                  </p>
                  {importProjection.parseError && (
                    <p className="text-amber-700">{importProjection.parseError}</p>
                  )}
                  {projectedQuotaExceeded && quota && quota.limit !== null && (
                    <p className="font-medium text-red-700">
                      Projected import exceeds quota ({projectedUsage}/{quota.limit}).
                      Reduce payload size or upgrade plan before importing.
                    </p>
                  )}
                  <p className="text-slate-700">
                    Estimate may be lower after import if payload rows are duplicates or already enrolled.
                  </p>
                </div>
              )}
            </div>
          )}
          <form className="space-y-3" onSubmit={handleImportCandidates}>
            <div>
              <FieldLabel
                htmlFor="campaign-import-payload"
                label="Payload (JSON array)"
                help="Provide an array of candidate objects (first_name, last_name, email, phone_number, preferred_channel)."
                className="mb-1 flex items-center gap-1.5"
                textClassName="block text-sm font-medium text-slate-700"
              />
              <textarea
                title='Candidate Import Payload - Enter a JSON array of candidate objects. Each object should include first_name, last_name, email, phone_number, and preferred_channel fields.'
                id="campaign-import-payload"
                rows={12}
                value={importPayload}
                onChange={(event) => setImportPayload(event.target.value)}
                className="w-full rounded-lg border border-slate-700 px-3 py-2 font-mono text-sm focus:ring-2 focus:ring-indigo-400 outline-none"
              />
            </div>
            <div className="inline-flex items-center gap-2 text-sm text-slate-700">
              <input
                id="campaign-send-invites"
                type="checkbox"
                checked={sendInvites}
                onChange={(event) => setSendInvites(event.target.checked)}
              />
              <label htmlFor="campaign-send-invites">Send invitations immediately after import</label>
              <HelpTooltip text="When enabled, invite messages are queued right after successful import." />
            </div>
            <button
              type="submit"
              disabled={importing || Boolean(importProjection.parseError) || projectedQuotaExceeded}
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
            <p className="text-slate-700 text-sm">No enrollments yet.</p>
          ) : (
            <div className="max-h-[430px] overflow-auto space-y-2 pr-1">
              {enrollments.map((enrollment) => (
                <article
                  key={enrollment.id}
                  className="flex flex-col items-start gap-3 rounded-lg border border-slate-200 px-3 py-2 sm:flex-row sm:items-center sm:justify-between"
                >
                  <div>
                    <p className="font-medium text-slate-800">{enrollment.candidate_email || `Candidate #${enrollment.candidate}`}</p>
                    <p className="text-xs text-slate-700">
                      Invited: {enrollment.invited_at ? formatDateTime(enrollment.invited_at) : 'N/A'}
                    </p>
                  </div>
                  <span className="text-xs rounded-full px-2.5 py-1 bg-slate-200 text-slate-800">
                    {enrollment.status}
                  </span>
                  {!['completed', 'reviewed', 'approved', 'rejected', 'escalated'].includes(enrollment.status) && (
                    <button
                      type="button"
                      onClick={() => void handleMarkEnrollmentComplete(enrollment.id)}
                      disabled={completingEnrollmentId === enrollment.id}
                      className="inline-flex w-full items-center justify-center gap-1 rounded border border-slate-700 px-2 py-1 text-xs text-slate-900 hover:bg-slate-100 disabled:opacity-60 sm:w-auto"
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
          <p className="text-slate-700 text-sm">No invitations found for this campaign.</p>
        ) : (
          <>
            <div className="space-y-3 md:hidden">
              {latestInvitations.map((invitation) => (
                <article key={invitation.id} className="rounded-lg border border-slate-200 p-3">
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium text-slate-900">{invitation.send_to}</p>
                      <p className="text-xs text-slate-700">
                        {invitation.channel.toUpperCase()} • Attempts: {invitation.attempts}
                      </p>
                    </div>
                    <span className="rounded-full bg-slate-200 px-2 py-0.5 text-xs font-medium text-slate-800">
                      {invitation.status}
                    </span>
                  </div>
                  <p className="mt-2 text-xs text-slate-700">Expires: {formatDateTime(invitation.expires_at)}</p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {invitation.status !== 'accepted' && invitation.status !== 'expired' && (
                      <button
                        type="button"
                        onClick={() => void handleResendInvitation(invitation.id)}
                        disabled={resendingInvitationId === invitation.id}
                        className="inline-flex flex-1 items-center justify-center gap-1 rounded border border-slate-700 px-2 py-1.5 text-xs text-slate-900 hover:bg-slate-100 disabled:opacity-60"
                      >
                        <Send className="h-3.5 w-3.5" />
                        {resendingInvitationId === invitation.id ? 'Sending...' : 'Resend'}
                      </button>
                    )}
                    {invitation.accept_url && (
                      <button
                        type="button"
                        onClick={() => void handleCopyAcceptUrl(invitation)}
                        className="inline-flex flex-1 items-center justify-center gap-1 rounded border border-slate-700 px-2 py-1.5 text-xs text-slate-900 hover:bg-slate-100"
                      >
                        <Copy className="h-3.5 w-3.5" />
                        Copy URL
                      </button>
                    )}
                  </div>
                </article>
              ))}
            </div>
            <div className="hidden overflow-auto md:block">
              <table className="w-full min-w-[720px] text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-left text-slate-700">
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
                            className="inline-flex items-center gap-1 rounded border border-slate-700 px-2 py-1 text-xs text-slate-900 hover:bg-slate-100 disabled:opacity-60"
                          >
                            <Send className="w-3.5 h-3.5" />
                            {resendingInvitationId === invitation.id ? 'Sending...' : 'Resend'}
                          </button>
                        )}
                        {invitation.accept_url && (
                          <button
                            type="button"
                            onClick={() => void handleCopyAcceptUrl(invitation)}
                            className="inline-flex items-center gap-1 rounded border border-slate-700 px-2 py-1 text-xs text-slate-900 hover:bg-slate-100"
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
          </>
        )}
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-5">
        <h2 className="text-lg font-semibold inline-flex items-center gap-2 mb-3">
          <Activity className="w-5 h-5 text-indigo-600" />
          Candidate Entry Point
        </h2>
        <p className="text-sm text-slate-700">
          Candidates should use the access URL received through email/SMS. Legacy invitation links are still accepted
          at <code className="bg-slate-200 px-1 py-0.5 rounded text-xs text-slate-900">/invite/&lt;token&gt;</code>.
        </p>
      </section>
    </main>
  );
};

export default CampaignWorkspacePage;
