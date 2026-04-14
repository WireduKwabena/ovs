import React, { useCallback, useEffect, useState } from "react";
import {
  Users,
  Workflow,
  FolderOpen,
  RefreshCw,
  ChevronRight,
  AlertCircle,
  Building2,
  UserPlus,
  ShieldCheck,
  Clock,
  AlertTriangle,
  ExternalLink,
  Sparkles,
} from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "react-toastify";

import { useAuth } from "@/hooks/useAuth";
import { adminService } from "@/services/admin.service";
import { governanceService } from "@/services/governance.service";
import { billingService } from "@/services/billing.service";
import type {
  BillingSubscriptionManageResponse,
  BillingManagedSubscription,
} from "@/services/billing.service";
import type {
  DashboardStats,
  GovernanceOrganizationSummaryResponse,
  OrganizationOnboardingTokenStateResponse,
} from "@/types";
import { formatRelativeTime } from "@/utils/helper";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  buildBillingPaymentFailureNotificationTraceHref,
  buildBillingProcessingErrorNotificationTraceHref,
} from "@/utils/notificationTrace";

const HEALTHY_PAYMENT_STATUSES = new Set(["paid", "no_payment_required"]);

const isBillingHealthy = (sub: BillingManagedSubscription | null): boolean => {
  if (!sub) return false;
  // Backend stores a healthy subscription as status="complete" (see is_subscription_active in services.py).
  // payment_status can be "paid" or "no_payment_required" for healthy subscriptions.
  return sub.status === "complete" && HEALTHY_PAYMENT_STATUSES.has(sub.payment_status);
};

const OrgDashboardPage: React.FC = () => {
  const navigate = useNavigate();
  const { activeOrganization, activeOrganizationId } = useAuth();
  const [summary, setSummary] = useState<GovernanceOrganizationSummaryResponse | null>(null);
  const [onboarding, setOnboarding] = useState<OrganizationOnboardingTokenStateResponse | null>(null);
  const [billingData, setBillingData] = useState<BillingSubscriptionManageResponse | null>(null);
  const [dashboardStats, setDashboardStats] = useState<DashboardStats | null>(null);
  const [, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const loadData = useCallback(async (isSilent = false) => {
    if (!isSilent) setLoading(true);
    else setRefreshing(true);

    try {
      const [summaryData, onboardingData, billing, stats] = await Promise.all([
        governanceService.getOrganizationSummary(),
        billingService.getOnboardingTokenState(),
        billingService.getSubscriptionManagement(),
        adminService.getDashboard().catch(() => null),
      ]);
      setSummary(summaryData);
      setOnboarding(onboardingData);
      setBillingData(billing);
      setDashboardStats(stats);
    } catch {
      toast.error("Failed to sync organization metrics");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const pipelineData = dashboardStats
    ? [
        { name: "Pending Review", value: dashboardStats.pending, status: "pending" },
        { name: "Under Review", value: dashboardStats.under_review, status: "under_review" },
        { name: "Approved", value: dashboardStats.approved, status: "approved" },
        { name: "Rejected", value: dashboardStats.rejected, status: "rejected" },
      ]
    : [];

  const recentActions = (dashboardStats?.recent_applications ?? []).slice(0, 5).map((app) => ({
    action:
      app.status === "under_review"
        ? "Under Review"
        : app.status === "approved"
          ? "Case Approved"
          : app.status === "rejected"
            ? "Case Rejected"
            : "New Application",
    target: app.applicant_name || app.case_id,
    time: formatRelativeTime(app.created_at),
    type: "case" as const,
  }));

  const sub = billingData?.subscription ?? null;
  const billingNeedsAttention = sub !== null && !isBillingHealthy(sub);

  if (!activeOrganizationId) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[40vh] space-y-4 text-center p-8">
        <AlertTriangle className="h-12 w-12 text-amber-500" />
        <h2 className="text-2xl font-bold">Active Organization Required</h2>
        <p className="text-muted-foreground max-w-md">
          Please select an active organization to access the organization governance workspace.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Org Header */}
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Building2 className="h-4 w-4 text-primary" />
            <span className="text-[10px] font-bold uppercase tracking-[0.2em] text-muted-foreground">
              {activeOrganization?.organization_type || "Organization"}
            </span>
          </div>
          <h1 className="text-3xl font-bold tracking-tight">
            {activeOrganization?.name ?? "Organization Workspace"}
          </h1>
          <p className="text-muted-foreground mt-1 text-sm md:text-base">
            Operational oversight of your organization&apos;s vetting pipeline and governance structure.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Button
            variant="outline"
            className="rounded-xl gap-2 bg-card/50 backdrop-blur-sm"
            onClick={() => void loadData(true)}
            disabled={refreshing}
          >
            <RefreshCw className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`} />
            Sync Dashboard
          </Button>
        </div>
      </div>

      {/* Billing Attention Banner */}
      {billingNeedsAttention && sub && (
        <Card className="p-5 rounded-2xl border-rose-500/30 bg-rose-500/5 shadow-sm">
          <div className="flex items-start gap-4">
            <AlertCircle className="h-5 w-5 text-rose-600 mt-0.5 shrink-0" />
            <div className="flex-1 min-w-0">
              <h3 className="text-sm font-bold text-rose-700">Billing Needs Attention</h3>
              {sub.latest_incident?.message && (
                <p className="text-xs text-rose-600 mt-1">{sub.latest_incident.message}</p>
              )}
              <div className="flex flex-wrap gap-3 mt-3">
                <Link
                  to={buildBillingPaymentFailureNotificationTraceHref()}
                  className="text-xs font-bold text-rose-700 underline hover:text-rose-800 flex items-center gap-1"
                >
                  <ExternalLink className="h-3 w-3" />
                  View Payment Failure Alerts
                </Link>
                <Link
                  to={buildBillingProcessingErrorNotificationTraceHref()}
                  className="text-xs font-bold text-rose-700 underline hover:text-rose-800 flex items-center gap-1"
                >
                  <ExternalLink className="h-3 w-3" />
                  View Processing Error Alerts
                </Link>
              </div>
            </div>
          </div>
        </Card>
      )}

      {/* Trial Plan Banner */}
      {activeOrganization?.tier === "trial" && !sub && (
        <Card className="p-5 rounded-2xl border-amber-400/40 bg-amber-400/5 shadow-sm">
          <div className="flex items-start gap-4">
            <Sparkles className="h-5 w-5 text-amber-600 mt-0.5 shrink-0" />
            <div className="flex-1 min-w-0">
              <h3 className="text-sm font-bold text-amber-700">You&apos;re on the Trial Plan</h3>
              <p className="text-xs text-amber-600 mt-1">
                Trial includes up to 15 candidates per month and 5 organization seats.
                Upgrade to a paid plan to unlock higher limits and full platform access.
              </p>
            </div>
            <Button
              variant="outline"
              size="sm"
              className="shrink-0 border-amber-400 text-amber-700 hover:bg-amber-50"
              onClick={() => navigate("/subscribe")}
            >
              Upgrade Plan
            </Button>
          </div>
        </Card>
      )}

      {/* Pulse Metrics */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="p-5 rounded-2xl border-border/70 bg-card/50 shadow-sm backdrop-blur-sm">
          <div className="flex items-center gap-4">
            <div className="h-10 w-10 rounded-xl bg-primary/10 text-primary flex items-center justify-center">
              <FolderOpen className="h-5 w-5" />
            </div>
            <div>
              <p className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">
                Active Cases
              </p>
              <p className="text-2xl font-bold">{dashboardStats?.total_applications ?? 0}</p>
            </div>
          </div>
        </Card>
        <Card className="p-5 rounded-2xl border-border/70 bg-card/50 shadow-sm backdrop-blur-sm">
          <div className="flex items-center gap-4">
            <div className="h-10 w-10 rounded-xl bg-emerald-500/10 text-emerald-500 flex items-center justify-center">
              <Users className="h-5 w-5" />
            </div>
            <div>
              <p className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">
                Active Personnel
              </p>
              <p className="text-2xl font-bold">{summary?.stats.members_active ?? 0}</p>
            </div>
          </div>
        </Card>
        <Card className="p-5 rounded-2xl border-border/70 bg-card/50 shadow-sm backdrop-blur-sm">
          <div className="flex items-center gap-4">
            <div className="h-10 w-10 rounded-xl bg-indigo-500/10 text-indigo-500 flex items-center justify-center">
              <Workflow className="h-5 w-5" />
            </div>
            <div>
              <p className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">
                Active Committees
              </p>
              <p className="text-2xl font-bold">{summary?.stats.committees_active ?? 0}</p>
            </div>
          </div>
        </Card>
        <Card className="p-5 rounded-2xl border-border/70 bg-card/50 shadow-sm backdrop-blur-sm">
          <div className="flex items-center gap-4">
            <div className="h-10 w-10 rounded-xl bg-amber-500/10 text-amber-500 flex items-center justify-center">
              <ShieldCheck className="h-5 w-5" />
            </div>
            <div>
              <p className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">
                Active Chairs
              </p>
              <p className="text-2xl font-bold">{summary?.stats.active_chairs ?? 0}</p>
            </div>
          </div>
        </Card>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-8">
        {/* Vetting Pipeline Visualization */}
        <div className="xl:col-span-2 space-y-6">
          <Card className="p-6 rounded-4xl border-border/70 bg-card/50 shadow-sm backdrop-blur-sm">
            <div className="flex items-center justify-between mb-8">
              <div>
                <h2 className="text-lg font-bold">Vetting Pipeline Pulse</h2>
                <p className="text-xs text-muted-foreground">
                  Distribution of cases across the lifecycle.
                </p>
              </div>
              <Badge variant="outline" className="rounded-full">
                Live Flow
              </Badge>
            </div>
            <div className="space-y-3">
                {pipelineData.map((item) => (
                  <button
                    key={item.name}
                    onClick={() => navigate(`/admin/org/${activeOrganizationId}/cases?status=${item.status}`)}
                    className="flex items-center justify-between w-full p-3 rounded-xl bg-background/50 border border-border/50 hover:bg-muted/60 hover:border-border transition-colors group"
                  >
                    <span className="text-xs font-medium group-hover:text-primary transition-colors">{item.name}</span>
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-bold">{item.value}</span>
                      <ChevronRight className="h-3 w-3 text-muted-foreground group-hover:text-primary transition-colors" />
                    </div>
                  </button>
                ))}
              </div>
          </Card>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Committee Health */}
            <Card className="p-6 rounded-4xl border-border/70 bg-card/50 shadow-sm">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-bold flex items-center gap-2">
                  <Workflow className="h-4 w-4 text-primary" />
                  Committee Health
                </h3>
                <Button
                  variant="link"
                  className="text-[10px] font-bold uppercase tracking-widest text-primary p-0 h-auto"
                  onClick={() => navigate(`/admin/org/${activeOrganizationId}/committees`)}
                >
                  Manage Hub
                </Button>
              </div>
              <div className="space-y-4">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-muted-foreground">Active Assignments</span>
                  <span className="font-bold">
                    {summary?.stats.committee_memberships_active ?? 0}
                  </span>
                </div>
              </div>
            </Card>

            {/* Onboarding Overview */}
            <Card className="p-6 rounded-4xl border-border/70 bg-card/50 shadow-sm">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-bold flex items-center gap-2">
                  <UserPlus className="h-4 w-4 text-indigo-500" />
                  Onboarding
                </h3>
                <Button
                  variant="link"
                  className="text-[10px] font-bold uppercase tracking-widest text-primary p-0 h-auto"
                  aria-label="Manage Onboarding"
                  onClick={() => navigate(`/admin/org/${activeOrganizationId}/onboarding`)}
                >
                  Manage Onboarding
                </Button>
              </div>
              {onboarding?.token && (
                <div className="space-y-2 mt-2">
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-muted-foreground font-bold uppercase tracking-widest text-[10px]">
                      Token Preview
                    </span>
                    <code className="font-mono text-xs bg-muted/60 px-2 py-0.5 rounded">
                      {onboarding.token.token_preview}
                    </code>
                  </div>
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-muted-foreground">Seats Remaining</span>
                    <span className="font-bold">
                      {onboarding.organization_seat_remaining ?? 0} / {onboarding.organization_seat_limit ?? 0}
                    </span>
                  </div>
                </div>
              )}
              {!onboarding?.token && (
                <p className="text-xs text-muted-foreground mt-2">No active onboarding token.</p>
              )}
            </Card>
          </div>
        </div>

        {/* Action Center Sidebar */}
        <div className="xl:col-span-1 space-y-6">
          <Card className="p-6 rounded-[2.5rem] border-border/70 bg-primary text-white shadow-xl relative overflow-hidden group">
            <div className="absolute top-[-20%] right-[-20%] h-[60%] w-[60%] rounded-full bg-white/10 blur-[60px] group-hover:bg-white/20 transition-all duration-500" />
            <div className="relative z-10">
              <ShieldCheck className="h-8 w-8 mb-4 text-primary-foreground/80" />
              <h2 className="text-xl font-bold mb-2">Governance Hub</h2>
              <p className="text-sm text-primary-foreground/80 mb-6 leading-relaxed">
                Orchestrate your organization&apos;s vetting pipeline and personnel roles.
              </p>
              <div className="space-y-2">
                <button
                  onClick={() => navigate(`/admin/org/${activeOrganizationId}/cases`)}
                  className="flex items-center justify-between w-full p-4 rounded-2xl bg-white/10 hover:bg-white/20 transition-all group/btn border border-white/5"
                >
                  <span className="text-sm font-bold">Initiate Vetting Case</span>
                  <ChevronRight className="h-4 w-4 transition-transform group-hover/btn:translate-x-1" />
                </button>
                <button
                  onClick={() => navigate(`/admin/org/${activeOrganizationId}/committees`)}
                  className="flex items-center justify-between w-full p-4 rounded-2xl bg-white/10 hover:bg-white/20 transition-all group/btn border border-white/5"
                >
                  <span className="text-sm font-bold">Form New Committee</span>
                  <ChevronRight className="h-4 w-4 transition-transform group-hover/btn:translate-x-1" />
                </button>
                <button
                  onClick={() => navigate(`/admin/org/${activeOrganizationId}/users`)}
                  className="flex items-center justify-between w-full p-4 rounded-2xl bg-white/10 hover:bg-white/20 transition-all group/btn border border-white/5"
                >
                  <span className="text-sm font-bold">Onboard Staff Member</span>
                  <ChevronRight className="h-4 w-4 transition-transform group-hover/btn:translate-x-1" />
                </button>
              </div>
            </div>
          </Card>

          <Card className="p-6 rounded-4xl border-border/70 bg-card/50 shadow-sm backdrop-blur-sm">
            <h3 className="text-sm font-bold flex items-center gap-2 mb-4">
              <Clock className="h-4 w-4 text-primary" />
              Recent Activity
            </h3>
            <div className="space-y-5">
              {recentActions.length === 0 && (
                <p className="text-xs text-muted-foreground">No recent activity.</p>
              )}
              {recentActions.map((log, i) => (
                <div key={i} className="flex items-start gap-3">
                  <div
                    className={`h-8 w-8 rounded-lg flex items-center justify-center shrink-0 ${
                      log.type === "case"
                        ? "bg-primary/10 text-primary"
                        : log.type === "gov"
                          ? "bg-indigo-500/10 text-indigo-500"
                          : "bg-emerald-500/10 text-emerald-500"
                    }`}
                  >
                    {log.type === "case" ? (
                      <FolderOpen className="h-4 w-4" />
                    ) : log.type === "gov" ? (
                      <Workflow className="h-4 w-4" />
                    ) : (
                      <Users className="h-4 w-4" />
                    )}
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-xs font-bold truncate">
                      {log.action}: {log.target}
                    </p>
                    <p className="text-[10px] text-muted-foreground mt-0.5">{log.time}</p>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
};

export default OrgDashboardPage;
