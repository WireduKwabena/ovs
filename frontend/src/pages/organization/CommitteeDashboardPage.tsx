import React, { useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { ClipboardCheck, ShieldCheck, Users, Workflow } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/useAuth";

const CommitteeDashboardPage: React.FC = () => {
  const navigate = useNavigate();
  const {
    userType,
    activeOrganization,
    activeOrganizationId,
    committees,
    canAccessAppointments,
    canAccessApplications,
    canViewAuditLogs,
  } = useAuth();

  const scopedCommittees = useMemo(() => {
    if (!Array.isArray(committees) || !activeOrganizationId) {
      return [];
    }
    return committees.filter(
      (membership) =>
        String(membership.organization_id || "") === String(activeOrganizationId) &&
        ["committee_member", "committee_chair"].includes(String(membership.committee_role || "")),
    );
  }, [activeOrganizationId, committees]);

  if (userType === "applicant") {
    return (
      <main className="flex min-h-screen items-center justify-center bg-slate-100 px-4 py-10">
        <section className="w-full max-w-xl rounded-2xl border border-amber-200 bg-white p-8 shadow-sm text-center">
          <h1 className="text-2xl font-black text-slate-900">Committee Dashboard Unavailable</h1>
          <p className="mt-3 text-sm text-slate-700">
            Applicant accounts cannot access internal committee workflows.
          </p>
          <div className="mt-6">
            <Button type="button" onClick={() => navigate("/candidate/access")}>
              Back to Candidate Access
            </Button>
          </div>
        </section>
      </main>
    );
  }

  if (!activeOrganizationId) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-slate-100 px-4 py-10">
        <section className="w-full max-w-xl rounded-2xl border border-amber-200 bg-white p-8 shadow-sm text-center">
          <h1 className="text-2xl font-black text-slate-900">Active Organization Required</h1>
          <p className="mt-3 text-sm text-slate-700">
            Select an active organization before opening committee workflows.
          </p>
          <div className="mt-6">
            <Button type="button" onClick={() => navigate("/workspace")}>
              Back to Workspace
            </Button>
          </div>
        </section>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-7xl space-y-6 px-4 py-8">
      <header className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="inline-flex items-center gap-2 rounded-full border border-cyan-200 bg-cyan-50 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-cyan-800">
          <ShieldCheck className="h-3.5 w-3.5" />
          Committee Workspace
        </div>
        <h1 className="mt-3 text-3xl font-black tracking-tight text-slate-900">Committee Dashboard</h1>
        <p className="mt-1 text-sm text-slate-700">
          Active organization: <span className="font-semibold">{activeOrganization?.name || "N/A"}</span>
        </p>
      </header>

      <section className="grid gap-4 md:grid-cols-3">
        <article className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-700">My Committees</p>
          <p className="mt-2 text-3xl font-black text-slate-900">{scopedCommittees.length}</p>
          <p className="mt-1 text-xs text-slate-700">Active committee memberships in this organization</p>
        </article>
        <article className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-700">Review Queue</p>
          <p className="mt-2 text-3xl font-black text-indigo-700">{canAccessAppointments ? "Ready" : "Restricted"}</p>
          <p className="mt-1 text-xs text-slate-700">Appointment stage actions are role and committee scoped</p>
        </article>
        <article className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-700">Audit Visibility</p>
          <p className="mt-2 text-3xl font-black text-cyan-700">{canViewAuditLogs ? "Enabled" : "Limited"}</p>
          <p className="mt-1 text-xs text-slate-700">Audit access remains policy-scoped by role and organization</p>
        </article>
      </section>

      <section className="grid gap-4 lg:grid-cols-2">
        <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="text-lg font-bold text-slate-900">Committee Actions</h2>
          <p className="mt-2 text-sm text-slate-700">
            Open appointment workflows to review committee-bound stages and decisions.
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            <Button
              type="button"
              onClick={() => navigate("/government/appointments?view=committee")}
              disabled={!canAccessAppointments}
            >
              <ClipboardCheck className="mr-2 h-4 w-4" />
              Open Committee Review Queue
            </Button>
            {canAccessApplications ? (
              <Button type="button" variant="outline" onClick={() => navigate("/applications")}>
                <Workflow className="mr-2 h-4 w-4" />
                Open Cases
              </Button>
            ) : null}
            {canViewAuditLogs ? (
              <Button type="button" variant="outline" onClick={() => navigate("/audit-logs")}>
                <Users className="mr-2 h-4 w-4" />
                Audit Logs
              </Button>
            ) : null}
          </div>
        </article>

        <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="text-lg font-bold text-slate-900">Assignments</h2>
          {scopedCommittees.length === 0 ? (
            <p className="mt-2 text-sm text-slate-700">
              No active committee memberships are available in this organization.
            </p>
          ) : (
            <ul className="mt-3 space-y-2">
              {scopedCommittees.map((membership) => (
                <li
                  key={membership.id}
                  className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-800"
                >
                  <p className="font-semibold">{membership.committee_name}</p>
                  <p className="text-xs text-slate-700">
                    Role: {String(membership.committee_role || "").replace(/_/g, " ")}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </article>
      </section>
    </main>
  );
};

export default CommitteeDashboardPage;
