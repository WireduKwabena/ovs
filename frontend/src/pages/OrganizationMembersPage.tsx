import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Loader2, RefreshCw, UserCog, Users } from "lucide-react";
import { toast } from "react-toastify";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/hooks/useAuth";
import { governanceService } from "@/services/governance.service";
import type { GovernanceOrganizationMember } from "@/types";

const roleFilterOptions = [
  { value: "", label: "All roles" },
  { value: "registry_admin", label: "Registry Admin" },
  { value: "vetting_officer", label: "Vetting Officer" },
  { value: "committee_member", label: "Committee Member" },
  { value: "committee_chair", label: "Committee Chair" },
  { value: "appointing_authority", label: "Appointing Authority" },
  { value: "publication_officer", label: "Publication Officer" },
  { value: "auditor", label: "Auditor" },
  { value: "nominee", label: "Nominee" },
];

type MemberDraft = {
  title: string;
  membership_role: string;
  is_active: boolean;
};

const SELECT_FIELD_CLASS =
  "h-10 rounded-md border border-border bg-input px-3 text-sm text-foreground shadow-xs outline-none transition-[color,box-shadow] focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px] disabled:cursor-not-allowed disabled:opacity-60";

const OrganizationMembersPage: React.FC = () => {
  const navigate = useNavigate();
  const { userType, activeOrganization, activeOrganizationId, canManageActiveOrganizationGovernance } = useAuth();
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [savingId, setSavingId] = useState<string | null>(null);
  const [rows, setRows] = useState<GovernanceOrganizationMember[]>([]);
  const [count, setCount] = useState(0);
  const [nextPageUrl, setNextPageUrl] = useState<string | null>(null);
  const [previousPageUrl, setPreviousPageUrl] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [roleFilter, setRoleFilter] = useState("");
  const [isActiveFilter, setIsActiveFilter] = useState<"all" | "true" | "false">("all");
  const [drafts, setDrafts] = useState<Record<string, MemberDraft>>({});

  const canManage = userType !== "applicant" && canManageActiveOrganizationGovernance;

  const loadMembers = useCallback(async () => {
    if (!canManage || !activeOrganizationId) {
      setRows([]);
      setCount(0);
      setNextPageUrl(null);
      setPreviousPageUrl(null);
      return;
    }

    const response = await governanceService.listOrganizationMembers({
      page,
      search: search.trim() || undefined,
      membership_role: roleFilter || undefined,
      is_active:
        isActiveFilter === "all" ? undefined : isActiveFilter === "true",
    });
    setRows(response.results || []);
    setCount(response.count || 0);
    setNextPageUrl(response.next || null);
    setPreviousPageUrl(response.previous || null);
    setDrafts((previous) => {
      const next: Record<string, MemberDraft> = {};
      for (const item of response.results || []) {
        next[item.id] = previous[item.id] || {
          title: item.title || "",
          membership_role: item.membership_role || "",
          is_active: Boolean(item.is_active),
        };
      }
      return next;
    });
  }, [activeOrganizationId, canManage, isActiveFilter, page, roleFilter, search]);

  useEffect(() => {
    const run = async () => {
      setLoading(true);
      try {
        await loadMembers();
      } catch (error) {
        toast.error(error instanceof Error ? error.message : "Failed to load organization members.");
      } finally {
        setLoading(false);
      }
    };
    void run();
  }, [loadMembers]);

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      await loadMembers();
      toast.success("Organization members refreshed.");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Unable to refresh members.");
    } finally {
      setRefreshing(false);
    }
  };

  const handleSave = async (member: GovernanceOrganizationMember) => {
    const draft = drafts[member.id];
    if (!draft) {
      return;
    }
    setSavingId(member.id);
    try {
      await governanceService.updateOrganizationMember(member.id, {
        title: draft.title.trim(),
        membership_role: draft.membership_role.trim(),
        is_active: draft.is_active,
      });
      toast.success("Member updated.");
      await loadMembers();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to update member.");
    } finally {
      setSavingId(null);
    }
  };

  const handleActiveToggle = async (member: GovernanceOrganizationMember) => {
    const current = drafts[member.id] || {
      title: member.title || "",
      membership_role: member.membership_role || "",
      is_active: Boolean(member.is_active),
    };
    setSavingId(member.id);
    try {
      await governanceService.updateOrganizationMember(member.id, {
        is_active: !current.is_active,
      });
      toast.success(current.is_active ? "Member deactivated." : "Member reactivated.");
      await loadMembers();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to update member status.");
    } finally {
      setSavingId(null);
    }
  };

  const pageSummary = useMemo(() => {
    if (count === 0) return "No members";
    return `${count} total members`;
  }, [count]);

  if (!canManage) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-slate-100 px-4 py-10">
        <section className="w-full max-w-xl rounded-2xl border border-amber-200 bg-white p-8 shadow-sm text-center">
          <h1 className="text-2xl font-black text-slate-900">Organization Admin Access Required</h1>
          <p className="mt-3 text-sm text-slate-700">
            Member governance controls are restricted to organization admins and platform admins.
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

  if (!activeOrganizationId) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-slate-100 px-4 py-10">
        <section className="w-full max-w-xl rounded-2xl border border-amber-200 bg-white p-8 shadow-sm text-center">
          <h1 className="text-2xl font-black text-slate-900">Active Organization Required</h1>
          <p className="mt-3 text-sm text-slate-700">
            Select an active organization before managing members.
          </p>
          <div className="mt-6 flex items-center justify-center gap-3">
            <Button type="button" onClick={() => navigate("/organization/setup")}>
              Organization Setup
            </Button>
            <Button type="button" variant="outline" onClick={() => navigate("/organization/dashboard")}>
              Organization Dashboard
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
              <Users className="h-3.5 w-3.5" />
              Organization Members
            </div>
            <h1 className="mt-3 text-3xl font-black tracking-tight text-slate-900">Member Registry</h1>
            <p className="mt-1 text-sm text-slate-700">
              Active organization: <span className="font-semibold">{activeOrganization?.name || "N/A"}</span>
            </p>
            <p className="mt-1 text-xs text-slate-700">{pageSummary}</p>
          </div>
          <div className="flex items-center gap-2">
            <Button type="button" variant="outline" onClick={() => navigate("/organization/dashboard")}>
              Dashboard
            </Button>
            <Button type="button" variant="outline" onClick={() => void handleRefresh()} disabled={refreshing || loading}>
              <RefreshCw className={`mr-2 h-4 w-4 ${refreshing ? "animate-spin" : ""}`} />
              Refresh
            </Button>
          </div>
        </div>
      </header>

      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="grid gap-3 md:grid-cols-4">
          <Input
            value={search}
            onChange={(event) => {
              setPage(1);
              setSearch(event.target.value);
            }}
            placeholder="Search name, email, title"
          />
          <select
            className={SELECT_FIELD_CLASS}
            value={roleFilter}
            onChange={(event) => {
              setPage(1);
              setRoleFilter(event.target.value);
            }}
          >
            {roleFilterOptions.map((option) => (
              <option key={option.value || "all"} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <select
            className={SELECT_FIELD_CLASS}
            value={isActiveFilter}
            onChange={(event) => {
              setPage(1);
              setIsActiveFilter(event.target.value as "all" | "true" | "false");
            }}
          >
            <option value="all">All statuses</option>
            <option value="true">Active only</option>
            <option value="false">Inactive only</option>
          </select>
          <Button type="button" variant="outline" onClick={() => void handleRefresh()} disabled={refreshing || loading}>
            Apply Filters
          </Button>
        </div>

        {loading ? (
          <div className="mt-4 rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm text-slate-700">
            <span className="inline-flex items-center gap-2">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading organization members...
            </span>
          </div>
        ) : rows.length === 0 ? (
          <div className="mt-4 rounded-lg border border-dashed border-slate-300 p-6 text-center text-sm text-slate-700">
            No organization members found for this filter.
          </div>
        ) : (
          <div className="mt-4 overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200 text-sm">
              <thead>
                <tr className="text-left text-xs font-semibold uppercase tracking-wide text-slate-700">
                  <th className="px-3 py-2">Member</th>
                  <th className="px-3 py-2">Role</th>
                  <th className="px-3 py-2">Title</th>
                  <th className="px-3 py-2">Status</th>
                  <th className="px-3 py-2">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {rows.map((member) => {
                  const draft = drafts[member.id] || {
                    title: member.title || "",
                    membership_role: member.membership_role || "",
                    is_active: Boolean(member.is_active),
                  };
                  const isSaving = savingId === member.id;
                  return (
                    <tr key={member.id}>
                      <td className="px-3 py-3">
                        <p className="font-semibold text-slate-900">{member.user_full_name || "Unnamed user"}</p>
                        <p className="text-xs text-slate-700">{member.user_email}</p>
                      </td>
                      <td className="px-3 py-3">
                        <Input
                          value={draft.membership_role}
                          onChange={(event) =>
                            setDrafts((previous) => ({
                              ...previous,
                              [member.id]: {
                                ...draft,
                                membership_role: event.target.value,
                              },
                            }))
                          }
                          disabled={isSaving}
                        />
                      </td>
                      <td className="px-3 py-3">
                        <Input
                          value={draft.title}
                          onChange={(event) =>
                            setDrafts((previous) => ({
                              ...previous,
                              [member.id]: {
                                ...draft,
                                title: event.target.value,
                              },
                            }))
                          }
                          disabled={isSaving}
                        />
                      </td>
                      <td className="px-3 py-3">
                        <span
                          className={`inline-flex rounded px-2 py-1 text-xs font-semibold ${
                            draft.is_active ? "bg-emerald-100 text-emerald-800" : "bg-slate-100 text-slate-700"
                          }`}
                        >
                          {draft.is_active ? "Active" : "Inactive"}
                        </span>
                        {member.is_default ? (
                          <span className="ml-2 inline-flex rounded bg-cyan-100 px-2 py-1 text-xs font-semibold text-cyan-800">
                            Default
                          </span>
                        ) : null}
                      </td>
                      <td className="px-3 py-3">
                        <div className="flex flex-wrap gap-2">
                          <Button
                            type="button"
                            size="sm"
                            variant="outline"
                            onClick={() => void handleSave(member)}
                            disabled={isSaving}
                          >
                            <UserCog className="mr-1.5 h-3.5 w-3.5" />
                            Save
                          </Button>
                          <Button
                            type="button"
                            size="sm"
                            variant="outline"
                            onClick={() => void handleActiveToggle(member)}
                            disabled={isSaving}
                          >
                            {draft.is_active ? "Deactivate" : "Activate"}
                          </Button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        <div className="mt-4 flex flex-wrap items-center justify-between gap-2">
          <p className="text-xs text-slate-700">
            Page {page}
          </p>
          <div className="flex items-center gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={!previousPageUrl || loading}
              onClick={() => setPage((previous) => Math.max(1, previous - 1))}
            >
              Previous
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={!nextPageUrl || loading}
              onClick={() => setPage((previous) => previous + 1)}
            >
              Next
            </Button>
          </div>
        </div>
      </section>
    </main>
  );
};

export default OrganizationMembersPage;
