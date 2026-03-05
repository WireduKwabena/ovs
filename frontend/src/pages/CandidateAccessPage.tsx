import React, { useCallback, useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { KeyRound, LogOut, RefreshCw, FileCheck2, ShieldAlert, Info } from 'lucide-react';
import { invitationService } from '@/services/invitation.service';
import type { CandidateAccessContext, CandidateAccessResults } from '@/types';
import { formatDateTime } from '@/utils/helper';
import { FieldLabel, HelpTooltip } from '@/components/common/FieldHelp';

const terminalStatuses = new Set(['approved', 'rejected', 'escalated']);

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

function resolveTimelinePosition(enrollmentStatus: string): number {
  switch (enrollmentStatus) {
    case 'invited':
      return 0;
    case 'registered':
      return 1;
    case 'in_progress':
      return 2;
    case 'completed':
      return 3;
    case 'reviewed':
      return 4;
    case 'approved':
    case 'rejected':
    case 'escalated':
      return 5;
    default:
      return 0;
  }
}

const CandidateAccessPage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const tokenFromQuery = searchParams.get('token') || '';

  const [tokenInput, setTokenInput] = useState(tokenFromQuery);
  const [context, setContext] = useState<CandidateAccessContext | null>(null);
  const [results, setResults] = useState<CandidateAccessResults | null>(null);
  const [loading, setLoading] = useState(false);
  const [resultsLoading, setResultsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const timelinePosition = context ? resolveTimelinePosition(context.enrollment_status) : 0;
  const timelinePercent = Math.round(((timelinePosition + 1) / 6) * 100);
  const outcomeLabel = context
    ? terminalStatuses.has(context.enrollment_status)
      ? context.enrollment_status.replace('_', ' ')
      : 'pending decision'
    : 'pending decision';
  const timelineSteps = [
    { key: 'invited', title: 'Invitation Sent', description: 'You were invited to start vetting.' },
    { key: 'registered', title: 'Access Registered', description: 'Your candidate session is confirmed.' },
    { key: 'in_progress', title: 'Vetting In Progress', description: 'Document/interview checks are running.' },
    { key: 'completed', title: 'Evaluation Completed', description: 'Initial scoring has finished.' },
    { key: 'reviewed', title: 'Reviewed By Initiator', description: 'HR or reviewer examined your results.' },
    { key: 'decision', title: `Outcome (${outcomeLabel})`, description: 'Final decision and notification step.' },
  ];

  const consumeToken = useCallback(async (rawToken: string, syncQuery = true) => {
    setLoading(true);
    setError(null);
    setMessage(null);
    try {
      const data = await invitationService.consumeAccessToken(rawToken, true);
      setContext(data);
      setTokenInput(rawToken);
      if (syncQuery) {
        setSearchParams({ token: rawToken }, { replace: true });
      }
      setMessage('Access granted. You can now proceed with vetting and review your results later.');
    } catch (err: unknown) {
      setError(getErrorMessage(err, 'Access failed.'));
      setContext(null);
      setResults(null);
    } finally {
      setLoading(false);
    }
  }, [setSearchParams]);

  const refreshContext = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await invitationService.getAccessContext();
      setContext(data);
    } catch (err: unknown) {
      setError(getErrorMessage(err, 'Session not found.'));
      setContext(null);
    } finally {
      setLoading(false);
    }
  }, []);

  const loadResults = async () => {
    setResultsLoading(true);
    setError(null);
    try {
      const payload = await invitationService.getAccessResults();
      setResults(payload);
      if (!payload.available) {
        setMessage('Results are not available yet. Please check back later.');
      } else {
        setMessage('Results loaded.');
      }
    } catch (err: unknown) {
      setError(getErrorMessage(err, 'Failed to load results.'));
    } finally {
      setResultsLoading(false);
    }
  };

  const handleLogout = async () => {
    setLoading(true);
    try {
      await invitationService.logoutAccess();
      setContext(null);
      setResults(null);
      setTokenInput('');
      setSearchParams({}, { replace: true });
      setMessage('Session closed.');
    } catch (err: unknown) {
      setError(getErrorMessage(err, 'Could not close session.'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (tokenFromQuery) {
      void consumeToken(tokenFromQuery, false);
      return;
    }
    void refreshContext();
  }, [consumeToken, refreshContext, tokenFromQuery]);

  return (
    <main className="max-w-4xl mx-auto px-4 py-10 space-y-5">
      <section className="rounded-2xl bg-slate-900 text-white p-6">
        <h1 className="text-2xl font-semibold">Candidate Access Portal</h1>
        <p className="mt-1 text-slate-200">
          Use your tokenized URL to start vetting and return to view your results.
        </p>
      </section>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-red-700">{error}</div>
      )}
      {message && (
        <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-emerald-700">{message}</div>
      )}

      {!context && (
        <section className="rounded-xl border border-slate-200 bg-white p-5">
          <h2 className="font-semibold text-lg inline-flex items-center gap-2">
            <KeyRound className="w-5 h-5 text-indigo-600" />
            Enter Access Token
          </h2>
          <div className="mt-3 rounded-lg border border-indigo-200 bg-indigo-50 px-4 py-3 text-sm text-indigo-900">
            Hover or focus the <Info className="mx-1 inline h-4 w-4 align-text-bottom" /> icons beside labels for guidance.
          </div>
          <form
            className="mt-4 space-y-3"
            onSubmit={(event) => {
              event.preventDefault();
              if (!tokenInput.trim()) {
                setError('Token is required.');
                return;
              }
              void consumeToken(tokenInput.trim());
            }}
          >
            <FieldLabel
              htmlFor="candidate-access-token"
              label="Candidate Access Token"
              required
              help="Paste the token from your email/SMS access link to open your candidate session."
              className="mb-1 flex items-center gap-1.5"
              textClassName="block text-sm text-slate-700"
            />
            <input
              id="candidate-access-token"
              value={tokenInput}
              onChange={(event) => setTokenInput(event.target.value)}
              placeholder="Paste access token from email/SMS URL"
              className="w-full rounded-lg border border-slate-700 px-3 py-2 focus:ring-2 focus:ring-indigo-400 outline-none"
            />
            <button
              type="submit"
              disabled={loading}
              className="rounded-lg bg-indigo-600 text-white px-4 py-2 hover:bg-indigo-700 disabled:opacity-60"
            >
              {loading ? 'Verifying...' : 'Access Portal'}
            </button>
          </form>
        </section>
      )}

      {context && (
        <>
          <section className="rounded-xl border border-slate-200 bg-white p-5 space-y-2">
            <div className="flex flex-wrap gap-3 items-center justify-between">
              <h2 className="font-semibold text-lg inline-flex items-center gap-1.5">
                Session Context
                <HelpTooltip text="Shows your active candidate identity, campaign, and enrollment state for this access token." />
              </h2>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => void refreshContext()}
                  className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg border border-slate-300 hover:bg-slate-100 text-sm"
                >
                  <RefreshCw className="w-4 h-4" />
                  Refresh
                </button>
                <button
                  type="button"
                  onClick={() => void handleLogout()}
                  className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg border border-red-200 text-red-700 hover:bg-red-50 text-sm"
                >
                  <LogOut className="w-4 h-4" />
                  Logout
                </button>
              </div>
            </div>
            <p className="text-sm text-slate-700">
              Candidate: <strong>{context.candidate.first_name} {context.candidate.last_name}</strong> ({context.candidate.email})
            </p>
            <p className="text-sm text-slate-700">
              Campaign: <strong>{context.campaign.name}</strong> ({context.campaign.status})
            </p>
            <p className="text-sm text-slate-700">
              Enrollment Status: <strong>{context.enrollment_status}</strong>
            </p>
            <p className="text-sm text-slate-700">Session expires: {formatDateTime(context.session_expires_at)}</p>
          </section>

          <section className="rounded-xl border border-slate-200 bg-white p-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 className="font-semibold text-lg inline-flex items-center gap-1.5">
                Vetting Progress
                <HelpTooltip text="Tracks your current step from invitation through final decision." />
              </h2>
              <span className="text-xs rounded-full bg-indigo-50 text-indigo-700 px-2.5 py-1">
                {timelinePercent}% complete
              </span>
            </div>
            <div className="w-full h-2 bg-slate-100 rounded-full mt-3 overflow-hidden">
              <div
                className="h-2 bg-indigo-600 rounded-full transition-all duration-500"
                style={{ width: `${timelinePercent}%` }}
              />
            </div>
            <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-3">
              {timelineSteps.map((step, index) => {
                const isDone = index < timelinePosition;
                const isCurrent = index === timelinePosition;
                const cardClass = isCurrent
                  ? 'border-indigo-300 bg-indigo-50'
                  : isDone
                    ? 'border-emerald-200 bg-emerald-50'
                    : 'border-slate-200 bg-white';
                const bulletClass = isCurrent
                  ? 'bg-indigo-600'
                  : isDone
                    ? 'bg-emerald-600'
                    : 'bg-slate-300';
                return (
                  <article key={step.key} className={`rounded-lg border p-3 ${cardClass}`}>
                    <div className="flex items-start gap-3">
                      <span className={`mt-1 inline-flex h-2.5 w-2.5 rounded-full ${bulletClass}`} />
                      <div>
                        <p className="text-sm font-medium text-slate-900">{step.title}</p>
                        <p className="text-xs text-slate-700 mt-1">{step.description}</p>
                      </div>
                    </div>
                  </article>
                );
              })}
            </div>
          </section>

          <section className="rounded-xl border border-slate-200 bg-white p-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 className="font-semibold text-lg inline-flex items-center gap-2">
                <FileCheck2 className="w-5 h-5 text-indigo-600" />
                Results
                <HelpTooltip text="Check whether your vetting results are released and view the final outcome details." />
              </h2>
              <button
                type="button"
                onClick={() => void loadResults()}
                disabled={resultsLoading}
                className="rounded-lg bg-indigo-600 text-white px-4 py-2 hover:bg-indigo-700 disabled:opacity-60"
              >
                {resultsLoading ? 'Loading...' : 'Check Results'}
              </button>
            </div>

            {results && (
              <div className="mt-4 space-y-3">
                <p className="text-sm">
                  Availability:{' '}
                  <strong>{results.available ? 'Available' : 'Pending review / processing'}</strong>
                </p>
                {results.available ? (
                  <>
                    <p className="text-sm">
                      Decision: <strong>{results.decision || 'N/A'}</strong>
                    </p>
                    {results.review_notes && (
                      <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm">
                        <p className="font-medium mb-1">Reviewer Notes</p>
                        <p>{results.review_notes}</p>
                      </div>
                    )}
                    <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm">
                      <p className="font-medium mb-1">Result Payload</p>
                      <pre className="overflow-auto text-xs">{JSON.stringify(results.results, null, 2)}</pre>
                    </div>
                  </>
                ) : (
                  <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800 inline-flex items-center gap-2">
                    <ShieldAlert className="w-4 h-4" />
                    Results are not yet released.
                  </div>
                )}
              </div>
            )}
          </section>
        </>
      )}

      <section className="text-sm text-slate-700">
        Received a legacy invitation link? Open{' '}
        <code className="rounded bg-slate-100 px-1 py-0.5 text-xs">/invite/&lt;token&gt;</code>.
      </section>
    </main>
  );
};

export default CandidateAccessPage;

