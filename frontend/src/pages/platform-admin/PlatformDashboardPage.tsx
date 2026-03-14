import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Building2, CreditCard, ExternalLink, Power, RefreshCw, ShieldCheck } from "lucide-react";
import { toast } from "react-toastify";

import BillingHealthCard from "@/components/admin/BillingHealthCard";
import { Button } from "@/components/ui/button";
import { governanceService } from "@/services/governance.service";
import type { GovernancePlatformOrganizationOversight } from "@/types";

const adminBaseUrl = (
  (import.meta as { env?: Record<string, string> }).env?.VITE_DJANGO_ADMIN_URL ||
  "http://localhost:8000/admin/"
).replace(/\/?$/, "/");

const billingSubscriptionsAdminUrl = `${adminBaseUrl}billing/billingsubscription/`;

const getSubscriptionTone = (
  subscription: GovernancePlatformOrganizationOversight["subscription"],
): string => {
  if (!subscription) {
    return "bg-amber-100 text-amber-800";
  }
  if (subscription.source === "active") {
    return "bg-emerald-100 text-emerald-800";
  }
  return "bg-rose-100 text-rose-800";
};

const getSubscriptionLabel = (
  subscription: GovernancePlatformOrganizationOversight["subscription"],
): string => {
  if (!subscription) {
    return "No subscription";
  }
  if (subscription.source === "active") {
    return "Active subscription";
  }
  return "Latest billing record";
};

const formatDateTime = (value?: string | null): string => {
  if (!value) {
    return "Not available";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return "Not available";
  }
  return parsed.toLocaleString();
};

const PlatformDashboardPage: React.FC = () => {
  const [organizations, setOrganizations] = useState<GovernancePlatformOrganizationOversight[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [updatingOrganizationId, setUpdatingOrganizationId] = useState<string | null>(null);

  const loadOrganizations = useCallback(async (options?: { silent?: boolean }) => {
    if (options?.silent) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }

    try {
      const payload = await governanceService.listPlatformOrganizations();
      setOrganizations(Array.isArray(payload.results) ? payload.results : []);
      setError(null);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Failed to load organizations.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void loadOrganizations();
  }, [loadOrganizations]);

  const stats = useMemo(() => {
    const activeOrganizations = organizations.filter((organization) => organization.is_active).length;
    const activeSubscriptions = organizations.filter(
      (organization) => organization.subscription?.source === "active",
    ).length;
    const needsAttention = organizations.filter(
      (organization) => !organization.subscription || organization.subscription.source !== "active",
    ).length;

    return {
      totalOrganizations: organizations.length,
      activeOrganizations,
      activeSubscriptions,
      needsAttention,
    };
  }, [organizations]);

  const handleToggleOrganizationStatus = useCallback(
    async (organization: GovernancePlatformOrganizationOversight) => {
      setUpdatingOrganizationId(organization.id);
      try {
        const updated = await governanceService.updatePlatformOrganizationStatus(organization.id, {
          is_active: !organization.is_active,
        });
        setOrganizations((current) =>
          current.map((entry) => (entry.id === organization.id ? updated : entry)),
        );
        toast.success(
          updated.is_active
            ? `${updated.name} reactivated.`
            : `${updated.name} deactivated.`,
        );
      } catch (updateError) {
        toast.error(
          updateError instanceof Error
            ? updateError.message
            : "Failed to update organization status.",
        );
      } finally {
        setUpdatingOrganizationId(null);
      }
    },
    [],
  );

  return (
    <div className="min-h-screen bg-background">
      <div className="mx-auto max-w-7xl space-y-6 px-4 py-6 sm:px-6 lg:px-6 xl:px-8">
        <section className="rounded-[2rem] border border-border bg-card p-6 shadow-sm">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div className="max-w-3xl">
              <div className="inline-flex items-center rounded-full border border-primary/20 bg-primary/10 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-primary">
                Platform Administration
              </div>
              <h1 className="mt-4 text-3xl font-bold tracking-tight text-foreground">
                Organization subscription and status oversight
              </h1>
              <p className="mt-3 text-sm leading-7 text-muted-foreground sm:text-base">
                Platform admin is intentionally limited here. This workspace now covers only
                organization subscription posture and organization active or inactive status.
                Appointment exercises, cases, users, members, committees, onboarding, videos,
                rubrics, offices, nominees, and appointment workflow stay with each organization
                administrator.
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-3">
              <Button
                type="button"
                variant="outline"
                onClick={() => void loadOrganizations({ silent: true })}
                disabled={refreshing}
                className="gap-2"
              >
                <RefreshCw className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`} />
                {refreshing ? "Refreshing..." : "Refresh"}
              </Button>
              <a
                href={billingSubscriptionsAdminUrl}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-2 rounded-xl border border-border bg-background px-4 py-2 text-sm font-medium text-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
              >
                Open Billing Records
                <ExternalLink className="h-4 w-4" />
              </a>
            </div>
          </div>
        </section>

        <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1.7fr)_minmax(320px,1fr)]">
          <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <article className="rounded-2xl border border-border bg-card p-5 shadow-sm">
              <div className="inline-flex h-11 w-11 items-center justify-center rounded-2xl bg-primary/10 text-primary">
                <Building2 className="h-5 w-5" />
              </div>
              <p className="mt-4 text-sm font-medium text-muted-foreground">Organizations</p>
              <p className="mt-2 text-3xl font-bold text-foreground">{stats.totalOrganizations}</p>
            </article>

            <article className="rounded-2xl border border-border bg-card p-5 shadow-sm">
              <div className="inline-flex h-11 w-11 items-center justify-center rounded-2xl bg-emerald-100 text-emerald-700">
                <ShieldCheck className="h-5 w-5" />
              </div>
              <p className="mt-4 text-sm font-medium text-muted-foreground">Active Organizations</p>
              <p className="mt-2 text-3xl font-bold text-foreground">{stats.activeOrganizations}</p>
            </article>

            <article className="rounded-2xl border border-border bg-card p-5 shadow-sm">
              <div className="inline-flex h-11 w-11 items-center justify-center rounded-2xl bg-sky-100 text-sky-700">
                <CreditCard className="h-5 w-5" />
              </div>
              <p className="mt-4 text-sm font-medium text-muted-foreground">Active Subscriptions</p>
              <p className="mt-2 text-3xl font-bold text-foreground">{stats.activeSubscriptions}</p>
            </article>

            <article className="rounded-2xl border border-border bg-card p-5 shadow-sm">
              <div className="inline-flex h-11 w-11 items-center justify-center rounded-2xl bg-amber-100 text-amber-700">
                <Power className="h-5 w-5" />
              </div>
              <p className="mt-4 text-sm font-medium text-muted-foreground">Needs Attention</p>
              <p className="mt-2 text-3xl font-bold text-foreground">{stats.needsAttention}</p>
            </article>
          </section>

          <BillingHealthCard />
        </div>

        <section className="rounded-[2rem] border border-border bg-card p-6 shadow-sm">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <h2 className="text-xl font-semibold text-foreground">Organization oversight</h2>
              <p className="mt-1 text-sm text-muted-foreground">
                Review current subscription posture and enable or disable organization access when
                required.
              </p>
            </div>
            <div className="rounded-2xl border border-primary/20 bg-primary/10 px-4 py-3 text-sm text-primary">
              Platform admin actions stop at subscription oversight and organization status.
            </div>
          </div>

          {loading ? (
            <div className="mt-6 rounded-2xl border border-dashed border-border bg-muted/30 p-8 text-sm text-muted-foreground">
              Loading organization oversight...
            </div>
          ) : null}

          {!loading && error ? (
            <div className="mt-6 rounded-2xl border border-destructive/30 bg-destructive/5 p-5 text-sm text-destructive">
              {error}
            </div>
          ) : null}

          {!loading && !error && organizations.length === 0 ? (
            <div className="mt-6 rounded-2xl border border-dashed border-border bg-muted/30 p-8 text-sm text-muted-foreground">
              No organizations are available for platform oversight yet.
            </div>
          ) : null}

          {!loading && !error && organizations.length > 0 ? (
            <div className="mt-6 space-y-4">
              {organizations.map((organization) => {
                const subscription = organization.subscription;
                const toggling = updatingOrganizationId === organization.id;

                return (
                  <article
                    key={organization.id}
                    className="rounded-[1.5rem] border border-border bg-background/80 p-5 shadow-sm"
                  >
                    <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
                      <div className="space-y-3">
                        <div className="flex flex-wrap items-center gap-2">
                          <h3 className="text-lg font-semibold text-foreground">
                            {organization.name}
                          </h3>
                          <span className="rounded-full bg-muted px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                            {organization.organization_type.replace(/_/g, " ")}
                          </span>
                          <span
                            className={[
                              "rounded-full px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.16em]",
                              organization.is_active
                                ? "bg-emerald-100 text-emerald-800"
                                : "bg-slate-200 text-slate-700",
                            ].join(" ")}
                          >
                            {organization.is_active ? "Active" : "Inactive"}
                          </span>
                        </div>

                        <div className="grid grid-cols-1 gap-3 text-sm text-muted-foreground sm:grid-cols-3">
                          <div>
                            <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                              Organization Code
                            </p>
                            <p className="mt-1 font-medium text-foreground">{organization.code}</p>
                          </div>
                          <div>
                            <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                              Active Members
                            </p>
                            <p className="mt-1 font-medium text-foreground">
                              {organization.active_member_count}
                            </p>
                          </div>
                          <div>
                            <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                              Subscription Source
                            </p>
                            <p className="mt-1 font-medium text-foreground">
                              {subscription ? getSubscriptionLabel(subscription) : "No billing record"}
                            </p>
                          </div>
                        </div>
                      </div>

                      <div className="flex items-start gap-3">
                        <Button
                          type="button"
                          variant={organization.is_active ? "outline" : "default"}
                          disabled={toggling}
                          onClick={() => void handleToggleOrganizationStatus(organization)}
                        >
                          {toggling
                            ? "Saving..."
                            : organization.is_active
                              ? "Deactivate Organization"
                              : "Reactivate Organization"}
                        </Button>
                      </div>
                    </div>

                    <div className="mt-5 rounded-[1.25rem] border border-border/70 bg-card p-4">
                      <div className="flex flex-wrap items-center gap-2">
                        <span
                          className={[
                            "rounded-full px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.16em]",
                            getSubscriptionTone(subscription),
                          ].join(" ")}
                        >
                          {getSubscriptionLabel(subscription)}
                        </span>
                        {subscription ? (
                          <>
                            <span className="rounded-full bg-muted px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                              {subscription.provider}
                            </span>
                            <span className="rounded-full bg-muted px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                              {subscription.status}
                            </span>
                            {subscription.payment_status ? (
                              <span className="rounded-full bg-muted px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                                {subscription.payment_status}
                              </span>
                            ) : null}
                          </>
                        ) : null}
                      </div>

                      {subscription ? (
                        <div className="mt-4 grid grid-cols-1 gap-3 text-sm sm:grid-cols-2 xl:grid-cols-4">
                          <div>
                            <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                              Plan
                            </p>
                            <p className="mt-1 font-medium text-foreground">
                              {subscription.plan_name} ({subscription.billing_cycle})
                            </p>
                          </div>
                          <div>
                            <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                              Payment Route
                            </p>
                            <p className="mt-1 font-medium text-foreground">
                              {subscription.payment_method.replace(/_/g, " ") || "Not available"}
                            </p>
                          </div>
                          <div>
                            <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                              Current Period End
                            </p>
                            <p className="mt-1 font-medium text-foreground">
                              {formatDateTime(subscription.current_period_end)}
                            </p>
                          </div>
                          <div>
                            <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                              Last Billing Update
                            </p>
                            <p className="mt-1 font-medium text-foreground">
                              {formatDateTime(subscription.updated_at)}
                            </p>
                          </div>
                        </div>
                      ) : (
                        <p className="mt-4 text-sm text-muted-foreground">
                          No subscription has been recorded for this organization yet.
                        </p>
                      )}
                    </div>
                  </article>
                );
              })}
            </div>
          ) : null}
        </section>
      </div>
    </div>
  );
};

export default PlatformDashboardPage;
