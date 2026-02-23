import React, { useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { CheckCircle2, AlertTriangle } from 'lucide-react';
import { invitationService } from '@/services/invitation.service';

const InvitationAcceptPage: React.FC = () => {
  const { token } = useParams<{ token: string }>();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [payload, setPayload] = useState<{
    message: string;
    campaign: string;
    candidate_email: string;
    enrollment_status: string;
  } | null>(null);

  useEffect(() => {
    const accept = async () => {
      if (!token) {
        setError('Invitation token is missing.');
        setLoading(false);
        return;
      }
      try {
        const data = await invitationService.acceptInvitation(token);
        setPayload(data);
      } catch (err: any) {
        const detail = err?.response?.data?.error || err?.response?.data?.detail || err?.message || 'Acceptance failed.';
        setError(detail);
      } finally {
        setLoading(false);
      }
    };

    void accept();
  }, [token]);

  const accessPath = useMemo(
    () => (token ? `/candidate/access?token=${encodeURIComponent(token)}` : '/candidate/access'),
    [token]
  );

  return (
    <main className="max-w-2xl mx-auto px-4 py-12">
      <section className="rounded-2xl border border-slate-200 bg-white p-6 space-y-4">
        {loading && <p className="text-slate-600">Validating invitation...</p>}

        {!loading && payload && (
          <>
            <div className="inline-flex items-center gap-2 rounded-lg bg-emerald-50 text-emerald-700 px-3 py-1.5 text-sm">
              <CheckCircle2 className="w-4 h-4" />
              Invitation accepted
            </div>
            <h1 className="text-2xl font-semibold">You are registered for vetting</h1>
            <p className="text-slate-700">
              Campaign: <strong>{payload.campaign}</strong>
            </p>
            <p className="text-slate-700">
              Candidate: <strong>{payload.candidate_email}</strong>
            </p>
            <p className="text-slate-700">
              Enrollment status: <strong>{payload.enrollment_status}</strong>
            </p>
          </>
        )}

        {!loading && error && (
          <>
            <div className="inline-flex items-center gap-2 rounded-lg bg-amber-50 text-amber-800 px-3 py-1.5 text-sm">
              <AlertTriangle className="w-4 h-4" />
              Could not auto-accept this token
            </div>
            <p className="text-slate-700">{error}</p>
          </>
        )}

        <div className="pt-2">
          <Link to={accessPath} className="inline-flex items-center rounded-lg bg-indigo-600 px-4 py-2 text-white hover:bg-indigo-700">
            Continue to Candidate Access
          </Link>
          <p className="text-xs text-slate-500 mt-2">
            Use the access URL from your invitation email/SMS inside the portal if prompted.
          </p>
        </div>
      </section>
    </main>
  );
};

export default InvitationAcceptPage;
