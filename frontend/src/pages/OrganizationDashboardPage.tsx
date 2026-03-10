import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Building2, Loader2, RefreshCw, ShieldCheck, Users, Workflow } from "lucide-react";
import { toast } from "react-toastify";

import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/useAuth";
import { billingService, type BillingSubscriptionManageResponse } from "@/services/billing.service";
import { governanceService } from "@/services/governance.service";
import type {
  GovernanceOrganizationSummaryResponse,
  OrganizationOnboardingTokenStateResponse,
} from "@/types";

const OrganizationDashboardPage: React.FC = () => {
  const navigate = useNavigate();
  const {
    userType,
    activeOrganization,
    activeOrganizationId,
    canManageActiveOrganizationGovernance,
  } = useAuth();

  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [summary, setSummary] = useState<GovernanceOrganizationSummaryResponse | null>(null);
  const [billingSummary, setBillingSummary] = useState<BillingSubscriptionManageResponse | null>(null);
  const [onboardingState, setOnboardingState] = useState<OrganizationOnboardingTokenStateResponse | null>(null);

  const canManage = userType !== "applicant" && canManageActiveOrganizationGovernance;

  const loadDashboard = useCallback(async () => {
    if (!canManage || !activeOrganizationId) {
      setSummary(null);
      setBillingSummary(null);
      setOnboardingState(null);
      return;
    }

    const [summaryResponse, billingResponse, onboardingResponse] = await Promise.all([
      governanceService.getOrganizationSummary(),
      billingService.getSubscriptionManagement(),
      billingService.getOnboardingTokenState(),
    ]);

    setSummary(summaryResponse);
    setBillingSummary(billingResponse);
    setOnboardingState(onboardingResponse);
  }, [activeOrganizationId, canManage]);

  useEffect(() => {
    const run = async () => {
      setLoading(true);
      try {
        await loadDashboard();
      } catch (error) {
        toast.error(error instanceof Error ? error.message : "Failed to load organization workspace.");
      } finally {
        setLoading(false);
      }
    };
    void run();
  }, [loadDashboard]);

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      await loadDashboard();
      toast.success("Organization workspace refreshed.");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Unable to refresh workspace.");
    } finally {
      setRefreshing(false);
    }
  };

  const nextStep = useMemo(() => {
    if (!billingSummary?.subscription) {
      return {
        label: "Activate organization subscription",
        path: "/subscribe?returnTo=%2Forganization%2Fonboarding",
      };
    }
    if (!onboardingState?.subscription_active) {
      return {
        label: "Resolve subscription status",
        path: "/subscribe?returnTo=%2Forganization%2Fonboarding",
      };
    }
    if (!onboardingState?.has_active_token) {
      return {
        label: "Generate onboarding invite link",
        path: "/organization/onboarding",
      };
    }
    return {
      label: "Manage committees and assignments",
      path: "/organization/committees",
    };
  }, [billingSummary?.subscription, onboardingState?.has_active_token, onboardingState?.subscription_active]);

  if (!canManage) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-slate-100 px-4 py-10">
        <section className="w-full max-w-xl rounded-2xl border border-amber-200 bg-white p-8 shadow-sm text-center">
          <h1 className="text-2xl font-black text-slate-900">Organization Admin Access Required</h1>
          <p className="mt-3 text-sm text-slate-700">
            Organization governance workspace is available to organization admins and platform admins.
          </p>
          <div className="mt-6">
            <Button type="button" onClick={() => navigate("/dashboard")}>
              Back to Dashboard
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
            Create or select an active organization before using the organization workspace.
          </p>
          <div className="mt-6 flex items-center justify-center gap-3">
            <Button type="button" onClick={() => navigate("/organization/setup")}>
              Organization Setup
            </Button>
            <Button type="button" variant="outline" onClick={() => navigate("/dashboard")}>
              Back
            </Button>
          </div>
        </section>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-7xl space-y-6 px-4 py-8">
      <header className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border border-cyan-200 bg-cyan-50 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-cyan-800">
              <ShieldCheck className="h-3.5 w-3.5" />
              Org Admin Workspace
            </div>
            <h1 className="mt-3 text-3xl font-black tracking-tight text-slate-900">Organization Dashboard</h1>
            <p className="mt-1 text-sm text-slate-700">
              Active organization: <span className="font-semibold">{activeOrganization?.name || "N/A"}</span>
            </p>
          </div>
          <Button type="button" variant="outline" onClick={() => void handleRefresh()} disabled={refreshing || loading}>
            <RefreshCw className={`mr-2 h-4 w-4 ${refreshing ? "animate-spin" : ""}`} />
            Refresh
          </Button>
        </div>
      </header>

      {loading ? (
        <section className="rounded-2xl border border-slate-200 bg-white p-10 text-center text-sm text-slate-700">
          <span className="inline-flex items-center gap-2">
            <Loader2 className="h-4 w-4 animate-spin" />
            Loading organization workspace...
          </span>
        </section>
      ) : (
        <>
          <section className="grid gap-4 md:grid-cols-3">
            <article className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-700">Members</p>
              <p className="mt-2 text-3xl font-black text-slate-900">{summary?.stats.members_active ?? 0}</p>
              <p className="mt-1 text-xs text-slate-700">Active of {summary?.stats.members_total ?? 0} total</p>
            </article>
            <article className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-700">Committees</p>
              <p className="mt-2 text-3xl font-black text-indigo-700">{summary?.stats.committees_active ?? 0}</p>
              <p className="mt-1 text-xs text-slate-700">Active of {summary?.stats.committees_total ?? 0} total</p>
            </article>
            <article className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-700">Active Chairs</p>
              <p className="mt-2 text-3xl font-black text-cyan-700">{summary?.stats.active_chairs ?? 0}</p>
              <p className="mt-1 text-xs text-slate-700">
                {summary?.stats.committee_memberships_active ?? 0} active committee assignments
              </p>
            </article>
          </section>

          <section className="grid gap-4 lg:grid-cols-2">
            <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
              <h2 className="text-lg font-bold text-slate-900">Onboarding & Subscription</h2>
              <p className="mt-2 text-sm text-slate-700">
                Subscription:{" "}
                <span className="font-semibold">
                  {billingSummary?.subscription ? "Active subscription detected" : "No active subscription"}
                </span>
              </p>
              <p className="mt-1 text-sm text-slate-700">
                Onboarding link:{" "}
                <span className="font-semibold">
                  {onboardingState?.has_active_token ? "Active" : "Not generated"}
                </span>
              </p>
              {onboardingState?.token ? (
                <p className="mt-1 text-xs text-slate-700">
                  Token preview: <span className="font-mono">{onboardingState.token.token_preview}</span>
                </p>
              ) : null}
              <p className="mt-1 text-xs text-slate-700">
                Remaining seats:{" "}
                {onboardingState?.organization_seat_remaining == null
                  ? "N/A"
                  : onboardingState.organization_seat_remaining}
              </p>
              <div className="mt-4 flex flex-wrap gap-2">
                <Button type="button" variant="outline" onClick={() => navigate("/organization/onboarding")}>
                  Manage Onboarding
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => navigate("/subscribe?returnTo=%2Forganization%2Fonboarding")}
                >
                  Subscription Plans
                </Button>
              </div>
            </article>

            <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
              <h2 className="text-lg font-bold text-slate-900">Next Step</h2>
              <p className="mt-2 text-sm text-slate-700">
                Keep the governance flow moving by completing the recommended next action.
              </p>
              <div className="mt-4 rounded-xl border border-cyan-200 bg-cyan-50 p-4">
                <p className="text-sm font-semibold text-cyan-900">{nextStep.label}</p>
              </div>
              <div className="mt-4 flex flex-wrap gap-2">
                <Button type="button" onClick={() => navigate(nextStep.path)}>
                  Continue
                </Button>
                <Button type="button" variant="outline" onClick={() => navigate("/organization/members")}>
                  Members
                </Button>
                <Button type="button" variant="outline" onClick={() => navigate("/organization/committees")}>
                  Committees
                </Button>
              </div>
            </article>
          </section>

          <section className="grid gap-4 md:grid-cols-3">
            <button
              type="button"
              onClick={() => navigate("/organization/members")}
              className="rounded-xl border border-slate-200 bg-white p-4 text-left shadow-sm transition hover:border-cyan-300"
            >
              <Users className="h-5 w-5 text-cyan-700" />
              <p className="mt-2 text-sm font-semibold text-slate-900">Manage Members</p>
              <p className="text-xs text-slate-700">Update membership roles and active state.</p>
            </button>
            <button
              type="button"
              onClick={() => navigate("/organization/committees")}
              className="rounded-xl border border-slate-200 bg-white p-4 text-left shadow-sm transition hover:border-cyan-300"
            >
              <Workflow className="h-5 w-5 text-cyan-700" />
              <p className="mt-2 text-sm font-semibold text-slate-900">Manage Committees</p>
              <p className="text-xs text-slate-700">Create committees and assign governance structure.</p>
            </button>
            <button
              type="button"
              onClick={() => navigate("/organization/onboarding")}
              className="rounded-xl border border-slate-200 bg-white p-4 text-left shadow-sm transition hover:border-cyan-300"
            >
              <Building2 className="h-5 w-5 text-cyan-700" />
              <p className="mt-2 text-sm font-semibold text-slate-900">Onboarding Links</p>
              <p className="text-xs text-slate-700">Generate, rotate, and revoke invite links safely.</p>
            </button>
          </section>
        </>
      )}
    </main>
  );
};

export default OrganizationDashboardPage;

