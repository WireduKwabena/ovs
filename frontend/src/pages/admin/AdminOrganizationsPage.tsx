import React, { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowRightCircle, Building2, CheckCircle2, Loader2, LogOut, RefreshCw, Users2 } from "lucide-react";
import { toast } from "react-toastify";

import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/useAuth";
import type { OrganizationMembershipContext, OrganizationSummary } from "@/types";

const ORG_ADMIN_MEMBERSHIP_ROLES = new Set([
  "registry_admin",
  "org_admin",
  "organization_admin",
  "system_admin",
]);

const normalizeRole = (value: string | null | undefined): string => {
  return String(value || "")
    .trim()
    .toLowerCase()
    .replace(/[\s-]+/g, "_");
};

const resolveGovernanceState = (
  organizationId: string,
  memberships: OrganizationMembershipContext[],
): string => {
  const orgMemberships = memberships.filter(
    (membership) => String(membership.organization_id || "").trim() === organizationId,
  );
  const activeMemberships = orgMemberships.filter((membership) => Boolean(membership.is_active));

  if (activeMemberships.length === 0) {
    return "No active membership linked";
  }

  const hasOrgAdminMembership = activeMemberships.some((membership) =>
    ORG_ADMIN_MEMBERSHIP_ROLES.has(normalizeRole(membership.membership_role)),
  );

  if (hasOrgAdminMembership) {
    return "Organization admin membership active";
  }

  return "Active membership available";
};

const AdminOrganizationsPage: React.FC = () => {
  const navigate = useNavigate();
  const {
    organizations,
    organizationMemberships,
    activeOrganizationId,
    switchingActiveOrganization,
    selectActiveOrganization,
    refreshProfile,
  } = useAuth();

  const [pendingOrganizationId, setPendingOrganizationId] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const sortedOrganizations = useMemo(() => {
    const list = Array.isArray(organizations) ? [...organizations] : [];
    return list.sort((left, right) => left.name.localeCompare(right.name));
  }, [organizations]);

  const resolvedMemberships = Array.isArray(organizationMemberships)
    ? organizationMemberships
    : [];

  const handleEnterOrganization = async (organization: OrganizationSummary) => {
    const nextOrganizationId = String(organization.id || "").trim();
    if (!nextOrganizationId) {
      return;
    }

    try {
      setPendingOrganizationId(nextOrganizationId);
      await selectActiveOrganization(nextOrganizationId);
      toast.success(`Entered ${organization.name}.`);
      navigate("/organization/dashboard");
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : "Unable to enter organization context.";
      toast.error(message);
    } finally {
      setPendingOrganizationId(null);
    }
  };

  const handleReturnToPlatform = async () => {
    try {
      setPendingOrganizationId(activeOrganizationId);
      await selectActiveOrganization(null);
      toast.success("Returned to platform scope.");
      navigate("/admin/dashboard", { replace: true });
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : "Unable to exit organization context.";
      toast.error(message);
    } finally {
      setPendingOrganizationId(null);
    }
  };

  const handleRefresh = async () => {
    try {
      setRefreshing(true);
      await Promise.resolve(refreshProfile());
      toast.success("Organization context refreshed.");
    } finally {
      setRefreshing(false);
    }
  };

  const isBusy = switchingActiveOrganization || Boolean(pendingOrganizationId);

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="mx-auto max-w-7xl space-y-6 px-4 py-6 sm:px-6 lg:px-8">
        <section className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h1 className="text-2xl font-semibold text-gray-900">Organizations</h1>
              <p className="mt-1 text-sm text-slate-800">
                Select a tenant organization to enter governance mode intentionally.
              </p>
            </div>
            <div className="flex w-full flex-wrap gap-2 sm:w-auto">
              <Button
                type="button"
                variant="outline"
                className="border-slate-700 text-slate-900 hover:bg-slate-100"
                onClick={() => void handleRefresh()}
                disabled={refreshing}
              >
                {refreshing ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
                Refresh
              </Button>
              <Button
                type="button"
                variant="outline"
                className="border-slate-700 text-slate-900 hover:bg-slate-100"
                onClick={() => navigate("/organization/setup")}
              >
                <Building2 className="h-4 w-4" />
                Create Organization
              </Button>
              {activeOrganizationId ? (
                <Button
                  type="button"
                  variant="outline"
                  className="border-slate-700 text-slate-900 hover:bg-slate-100"
                  onClick={() => void handleReturnToPlatform()}
                  disabled={isBusy}
                >
                  <LogOut className="h-4 w-4" />
                  Return to Platform
                </Button>
              ) : null}
            </div>
          </div>
        </section>

        {sortedOrganizations.length === 0 ? (
          <section className="rounded-2xl border border-dashed border-slate-300 bg-white p-10 text-center shadow-sm">
            <Building2 className="mx-auto h-10 w-10 text-slate-500" />
            <h2 className="mt-3 text-lg font-semibold text-slate-900">No organizations available</h2>
            <p className="mt-2 text-sm text-slate-700">
              Add an organization first or refresh profile context to load tenant organizations.
            </p>
            <div className="mt-5 flex flex-wrap justify-center gap-2">
              <Button type="button" onClick={() => navigate("/organization/setup")}>
                Create Organization
              </Button>
              <Button
                type="button"
                variant="outline"
                className="border-slate-700 text-slate-900 hover:bg-slate-100"
                onClick={() => void handleRefresh()}
                disabled={refreshing}
              >
                Refresh
              </Button>
            </div>
          </section>
        ) : (
          <section className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            {sortedOrganizations.map((organization) => {
              const organizationId = String(organization.id || "").trim();
              const isActive = organizationId === activeOrganizationId;
              const governanceState = resolveGovernanceState(organizationId, resolvedMemberships);
              const enteringThisOrganization = pendingOrganizationId === organizationId;

              return (
                <article
                  key={organizationId}
                  className={`rounded-xl border bg-white p-5 shadow-sm ${
                    isActive ? "border-emerald-300" : "border-slate-200"
                  }`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <h2 className="truncate text-lg font-semibold text-slate-900">{organization.name}</h2>
                      <p className="mt-1 text-xs uppercase tracking-wide text-slate-700">
                        {organization.organization_type || "organization"}
                      </p>
                    </div>
                    <span
                      className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${
                        isActive
                          ? "bg-emerald-100 text-emerald-700"
                          : "bg-slate-100 text-slate-700"
                      }`}
                    >
                      {isActive ? "Active Context" : "Available"}
                    </span>
                  </div>

                  <div className="mt-4 space-y-2 text-sm">
                    <p className="text-slate-700">
                      <span className="font-semibold text-slate-900">Code:</span> {organization.code || "N/A"}
                    </p>
                    <p className="text-slate-700">
                      <span className="font-semibold text-slate-900">Governance state:</span>{" "}
                      {governanceState}
                    </p>
                  </div>

                  <div className="mt-5 flex flex-wrap items-center gap-2">
                    <Button
                      type="button"
                      onClick={() => void handleEnterOrganization(organization)}
                      disabled={isBusy || isActive}
                    >
                      {enteringThisOrganization ? (
                        <span className="inline-flex items-center gap-2">
                          <Loader2 className="h-4 w-4 animate-spin" />
                          Entering...
                        </span>
                      ) : isActive ? (
                        <span className="inline-flex items-center gap-2">
                          <CheckCircle2 className="h-4 w-4" />
                          Entered
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-2">
                          <ArrowRightCircle className="h-4 w-4" />
                          Enter Organization
                        </span>
                      )}
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      className="border-slate-700 text-slate-900 hover:bg-slate-100"
                      onClick={() => navigate("/admin/users")}
                    >
                      <Users2 className="h-4 w-4" />
                      Organization Admins
                    </Button>
                  </div>
                </article>
              );
            })}
          </section>
        )}
      </div>
    </div>
  );
};

export default AdminOrganizationsPage;

