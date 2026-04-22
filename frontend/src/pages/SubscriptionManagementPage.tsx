import React, { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { CreditCard, Loader2, RefreshCw } from "lucide-react";
import { toast } from "react-toastify";

import BillingAttentionPanel from "@/components/billing/BillingAttentionPanel";
import { useAuth } from "@/hooks/useAuth";
import {
  billingService,
  type BillingSubscriptionManageResponse,
} from "@/services/billing.service";
import { Button } from "@/components/ui/button";

const getErrorMessage = (error: unknown, fallback: string): string => {
  if (!error) return fallback;
  if (typeof error === "string") return error;
  if (error instanceof Error && error.message) return error.message;
  const payload = error as {
    response?: { data?: { detail?: string; error?: string; message?: string } };
    message?: string;
  };
  return (
    payload.response?.data?.detail ||
    payload.response?.data?.error ||
    payload.response?.data?.message ||
    payload.message ||
    fallback
  );
};

const formatDateTimeLabel = (value: string | null | undefined): string => {
  if (!value) return "N/A";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "N/A";
  return parsed.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
};

const SubscriptionManagementPage: React.FC = () => {
  const navigate = useNavigate();
  const {
    userType,
    canManageActiveOrganizationGovernance,
    activeOrganization,
    activeOrganizationId,
    hasRole,
    isOrgAdmin,
    isPlatformAdmin,
  } = useAuth();

  const [billingData, setBillingData] =
    useState<BillingSubscriptionManageResponse | null>(null);
  const [billingLoading, setBillingLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  const isRegistryAdmin = hasRole("registry_admin");
  const canViewBilling =
    (isOrgAdmin || isRegistryAdmin) &&
    userType !== "applicant" &&
    !isPlatformAdmin;
  const canManageOrganizationBilling =
    canViewBilling && canManageActiveOrganizationGovernance;
  const managedSubscription = billingData?.subscription ?? null;

  const fetchBillingManagement = useCallback(async () => {
    if (!canViewBilling) {
      setBillingData(null);
      return;
    }
    setBillingLoading(true);
    try {
      const response = await billingService.getSubscriptionManagement();
      setBillingData(response);
    } catch (error) {
      toast.error(getErrorMessage(error, "Failed to load billing details."));
      setBillingData(null);
    } finally {
      setBillingLoading(false);
    }
  }, [canViewBilling]);

  useEffect(() => {
    void fetchBillingManagement();
  }, [activeOrganizationId, fetchBillingManagement]);

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      await fetchBillingManagement();
      toast.success("Subscription details refreshed.");
    } finally {
      setRefreshing(false);
    }
  };

  return (
    <main className="mx-auto max-w-4xl px-4 py-8 sm:px-6 lg:px-6 xl:px-8">
      <header className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="inline-flex items-center gap-2 rounded-full border border-cyan-200 bg-cyan-50 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-cyan-800">
          <CreditCard className="h-4 w-4" />
          Subscription
        </div>
        <h1 className="mt-3 text-3xl font-black tracking-tight text-slate-900">
          Subscription Management
        </h1>
        <p className="mt-1 text-sm text-slate-700">
          Review plan status, payment state, and organization billing actions.
        </p>
        <div className="mt-4 flex flex-wrap gap-2">
          <Button
            type="button"
            variant="outline"
            onClick={() => void handleRefresh()}
            disabled={refreshing || billingLoading}
          >
            {refreshing ? (
              <span className="inline-flex items-center gap-2">
                <Loader2 className="h-4 w-4 animate-spin" />
                Refreshing...
              </span>
            ) : (
              <span className="inline-flex items-center gap-2">
                <RefreshCw className="h-4 w-4" />
                Refresh Subscription Data
              </span>
            )}
          </Button>
          <Button type="button" variant="outline" asChild>
            <Link to="/settings">Back to Profile & Settings</Link>
          </Button>
        </div>
      </header>

      <section className="mt-6 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-900">
          Active Organization
        </h2>
        <p className="mt-2 text-sm text-slate-700">
          {activeOrganization?.name || "Default organization scope"}
        </p>
      </section>

      {!canViewBilling ? (
        <section className="mt-6 rounded-2xl border border-amber-200 bg-amber-50 p-5 text-sm text-amber-900 shadow-sm">
          Subscription details are only available to organization admins and
          registry admins in an active organization context.
        </section>
      ) : (
        <section className="mt-6 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between gap-2">
            <h2 className="text-lg font-bold text-slate-900">
              Organization Subscription
            </h2>
            <CreditCard className="h-4 w-4 text-cyan-700" />
          </div>

          {billingLoading ? (
            <p className="mt-3 text-sm text-slate-700">
              Loading billing details...
            </p>
          ) : !managedSubscription ? (
            <div className="mt-3 space-y-3">
              <p className="text-sm text-slate-700">
                {billingData?.message ||
                  "No active subscription found for this workspace."}
              </p>
              {canManageOrganizationBilling ? (
                <Button
                  type="button"
                  variant="outline"
                  onClick={() =>
                    navigate(
                      activeOrganizationId
                        ? "/organization/dashboard"
                        : "/organization/setup?next=/organization/dashboard",
                    )
                  }
                >
                  Open Organization Billing
                </Button>
              ) : (
                <p className="rounded-lg border border-amber-200 bg-amber-50 px-2 py-1 text-[11px] text-amber-800">
                  Subscription management is restricted to organization admins.
                </p>
              )}
            </div>
          ) : (
            <div className="mt-3 space-y-3">
              <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs text-slate-800">
                <p>
                  <span className="font-semibold">Plan:</span>{" "}
                  {managedSubscription.plan_name} (
                  {managedSubscription.billing_cycle})
                </p>
                <p className="mt-1">
                  <span className="font-semibold">
                    Subscription organization:
                  </span>{" "}
                  {managedSubscription.organization_name ||
                    managedSubscription.organization_id ||
                    "Scoped by active organization"}
                </p>
                <p className="mt-1">
                  <span className="font-semibold">Status:</span>{" "}
                  {managedSubscription.status} /{" "}
                  {managedSubscription.payment_status}
                </p>
                <p className="mt-1">
                  <span className="font-semibold">Payment method:</span>{" "}
                  {managedSubscription.payment_method?.display ||
                    "Not available"}
                </p>
                <p className="mt-1">
                  <span className="font-semibold">Current period end:</span>{" "}
                  {formatDateTimeLabel(managedSubscription.current_period_end)}
                </p>
                {managedSubscription.cancel_at_period_end ? (
                  <p className="mt-1 text-amber-700">
                    Cancellation scheduled for{" "}
                    {formatDateTimeLabel(
                      managedSubscription.cancellation_effective_at,
                    )}
                    . Access remains active until then.
                  </p>
                ) : null}
              </div>

              {canManageOrganizationBilling ? (
                <BillingAttentionPanel
                  subscription={managedSubscription}
                  onAfterAction={fetchBillingManagement}
                  renewHref="/subscribe?returnTo=%2Fsettings%2Fsubscription"
                />
              ) : null}

              <p className="text-[11px] text-slate-700">
                Organization billing and onboarding administration is handled in
                the organization dashboard.
              </p>
              {canManageOrganizationBilling ? (
                <Button
                  type="button"
                  variant="outline"
                  onClick={() =>
                    navigate(
                      activeOrganizationId
                        ? "/organization/dashboard"
                        : "/organization/setup?next=/organization/dashboard",
                    )
                  }
                >
                  Open Organization Administration
                </Button>
              ) : (
                <p className="rounded-lg border border-amber-200 bg-amber-50 px-2 py-1 text-[11px] text-amber-800">
                  Organization administration remains restricted to organization
                  admins.
                </p>
              )}
            </div>
          )}
        </section>
      )}
    </main>
  );
};

export default SubscriptionManagementPage;
