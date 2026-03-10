import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Loader2, Plus, RefreshCw, UsersRound, Workflow } from "lucide-react";
import { toast } from "react-toastify";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/hooks/useAuth";
import { governanceService } from "@/services/governance.service";
import type { GovernanceChoiceOption, GovernanceCommittee } from "@/types";

const SELECT_FIELD_CLASS =
  "h-10 rounded-md border border-border bg-input px-3 text-sm text-foreground shadow-xs outline-none transition-[color,box-shadow] focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px] disabled:cursor-not-allowed disabled:opacity-60";

type CommitteeDraft = {
  code: string;
  name: string;
  committee_type: string;
  description: string;
  is_active: boolean;
};

const OrganizationCommitteesPage: React.FC = () => {
  const navigate = useNavigate();
  const { userType, activeOrganization, activeOrganizationId, canManageActiveOrganizationGovernance } = useAuth();
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [savingId, setSavingId] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [rows, setRows] = useState<GovernanceCommittee[]>([]);
  const [count, setCount] = useState(0);
  const [nextPageUrl, setNextPageUrl] = useState<string | null>(null);
  const [previousPageUrl, setPreviousPageUrl] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [isActiveFilter, setIsActiveFilter] = useState<"all" | "true" | "false">("all");
  const [committeeTypeFilter, setCommitteeTypeFilter] = useState("");
  const [committeeTypeOptions, setCommitteeTypeOptions] = useState<GovernanceChoiceOption[]>([]);
  const [drafts, setDrafts] = useState<Record<string, CommitteeDraft>>({});
  const [createForm, setCreateForm] = useState({
    code: "",
    name: "",
    committee_type: "",
    description: "",
  });

  const canManage = userType !== "applicant" && canManageActiveOrganizationGovernance;

  const loadChoices = useCallback(async () => {
    const choices = await governanceService.getGovernanceChoices();
    const committeeChoices = choices.committee_types || [];
    setCommitteeTypeOptions(committeeChoices);
    setCreateForm((previous) => ({
      ...previous,
      committee_type: previous.committee_type || committeeChoices[0]?.value || "other",
    }));
  }, []);

  const loadCommittees = useCallback(async () => {
    if (!canManage || !activeOrganizationId) {
      setRows([]);
      setCount(0);
      setNextPageUrl(null);
      setPreviousPageUrl(null);
      return;
    }

    const response = await governanceService.listCommittees({
      page,
      search: search.trim() || undefined,
      committee_type: committeeTypeFilter || undefined,
      is_active: isActiveFilter === "all" ? undefined : isActiveFilter === "true",
    });
    setRows(response.results || []);
    setCount(response.count || 0);
    setNextPageUrl(response.next || null);
    setPreviousPageUrl(response.previous || null);
    setDrafts((previous) => {
      const next: Record<string, CommitteeDraft> = {};
      for (const item of response.results || []) {
        next[item.id] = previous[item.id] || {
          code: item.code || "",
          name: item.name || "",
          committee_type: item.committee_type || "",
          description: item.description || "",
          is_active: Boolean(item.is_active),
        };
      }
      return next;
    });
  }, [activeOrganizationId, canManage, committeeTypeFilter, isActiveFilter, page, search]);

  useEffect(() => {
    const run = async () => {
      setLoading(true);
      try {
        await Promise.all([loadChoices(), loadCommittees()]);
      } catch (error) {
        toast.error(error instanceof Error ? error.message : "Failed to load committees.");
      } finally {
        setLoading(false);
      }
    };
    void run();
  }, [loadChoices, loadCommittees]);

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      await Promise.all([loadChoices(), loadCommittees()]);
      toast.success("Committee registry refreshed.");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Unable to refresh committees.");
    } finally {
      setRefreshing(false);
    }
  };

  const handleCreate = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!createForm.code.trim() || !createForm.name.trim() || !createForm.committee_type.trim()) {
      toast.error("Committee code, name, and type are required.");
      return;
    }
    setCreating(true);
    try {
      await governanceService.createCommittee({
        code: createForm.code.trim(),
        name: createForm.name.trim(),
        committee_type: createForm.committee_type.trim(),
        description: createForm.description.trim(),
      });
      toast.success("Committee created.");
      setCreateForm((previous) => ({
        ...previous,
        code: "",
        name: "",
        description: "",
      }));
      await loadCommittees();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to create committee.");
    } finally {
      setCreating(false);
    }
  };

  const handleSave = async (committee: GovernanceCommittee) => {
    const draft = drafts[committee.id];
    if (!draft) {
      return;
    }
    setSavingId(committee.id);
    try {
      await governanceService.updateCommittee(committee.id, {
        code: draft.code.trim(),
        name: draft.name.trim(),
        committee_type: draft.committee_type.trim(),
        description: draft.description.trim(),
        is_active: draft.is_active,
      });
      toast.success("Committee updated.");
      await loadCommittees();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to update committee.");
    } finally {
      setSavingId(null);
    }
  };

  const handleDeactivate = async (committee: GovernanceCommittee) => {
    setSavingId(committee.id);
    try {
      await governanceService.deactivateCommittee(committee.id);
      toast.success("Committee deactivated.");
      await loadCommittees();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to deactivate committee.");
    } finally {
      setSavingId(null);
    }
  };

  const pageSummary = useMemo(() => {
    if (count === 0) return "No committees";
    return `${count} total committees`;
  }, [count]);

  if (!canManage) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-slate-100 px-4 py-10">
        <section className="w-full max-w-xl rounded-2xl border border-amber-200 bg-white p-8 shadow-sm text-center">
          <h1 className="text-2xl font-black text-slate-900">Organization Admin Access Required</h1>
          <p className="mt-3 text-sm text-slate-700">
            Committee governance controls are restricted to organization admins and platform admins.
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
            Select an active organization before managing committees.
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
              <Workflow className="h-3.5 w-3.5" />
              Organization Committees
            </div>
            <h1 className="mt-3 text-3xl font-black tracking-tight text-slate-900">Committee Registry</h1>
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
        <h2 className="text-lg font-bold text-slate-900">Create Committee</h2>
        <form className="mt-4 grid gap-3 md:grid-cols-2 lg:grid-cols-4" onSubmit={handleCreate}>
          <Input
            value={createForm.code}
            onChange={(event) => setCreateForm((previous) => ({ ...previous, code: event.target.value }))}
            placeholder="committee-code"
          />
          <Input
            value={createForm.name}
            onChange={(event) => setCreateForm((previous) => ({ ...previous, name: event.target.value }))}
            placeholder="Committee name"
          />
          <select
            className={SELECT_FIELD_CLASS}
            value={createForm.committee_type}
            onChange={(event) =>
              setCreateForm((previous) => ({
                ...previous,
                committee_type: event.target.value,
              }))
            }
          >
            {committeeTypeOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <Button type="submit" disabled={creating}>
            <Plus className="mr-2 h-4 w-4" />
            {creating ? "Creating..." : "Create"}
          </Button>
          <div className="md:col-span-2 lg:col-span-4">
            <Input
              value={createForm.description}
              onChange={(event) =>
                setCreateForm((previous) => ({
                  ...previous,
                  description: event.target.value,
                }))
              }
              placeholder="Description (optional)"
            />
          </div>
        </form>
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="grid gap-3 md:grid-cols-4">
          <Input
            value={search}
            onChange={(event) => {
              setPage(1);
              setSearch(event.target.value);
            }}
            placeholder="Search code or name"
          />
          <select
            className={SELECT_FIELD_CLASS}
            value={committeeTypeFilter}
            onChange={(event) => {
              setPage(1);
              setCommitteeTypeFilter(event.target.value);
            }}
          >
            <option value="">All committee types</option>
            {committeeTypeOptions.map((option) => (
              <option key={option.value} value={option.value}>
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
              Loading committees...
            </span>
          </div>
        ) : rows.length === 0 ? (
          <div className="mt-4 rounded-lg border border-dashed border-slate-300 p-6 text-center text-sm text-slate-700">
            No committees found for this filter.
          </div>
        ) : (
          <div className="mt-4 overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200 text-sm">
              <thead>
                <tr className="text-left text-xs font-semibold uppercase tracking-wide text-slate-700">
                  <th className="px-3 py-2">Committee</th>
                  <th className="px-3 py-2">Type</th>
                  <th className="px-3 py-2">Description</th>
                  <th className="px-3 py-2">Status</th>
                  <th className="px-3 py-2">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {rows.map((committee) => {
                  const draft = drafts[committee.id] || {
                    code: committee.code || "",
                    name: committee.name || "",
                    committee_type: committee.committee_type || "",
                    description: committee.description || "",
                    is_active: Boolean(committee.is_active),
                  };
                  const isSaving = savingId === committee.id;
                  return (
                    <tr key={committee.id}>
                      <td className="px-3 py-3">
                        <Input
                          value={draft.name}
                          onChange={(event) =>
                            setDrafts((previous) => ({
                              ...previous,
                              [committee.id]: {
                                ...draft,
                                name: event.target.value,
                              },
                            }))
                          }
                          disabled={isSaving}
                        />
                        <Input
                          className="mt-2"
                          value={draft.code}
                          onChange={(event) =>
                            setDrafts((previous) => ({
                              ...previous,
                              [committee.id]: {
                                ...draft,
                                code: event.target.value,
                              },
                            }))
                          }
                          disabled={isSaving}
                        />
                      </td>
                      <td className="px-3 py-3">
                        <select
                          className={SELECT_FIELD_CLASS}
                          value={draft.committee_type}
                          onChange={(event) =>
                            setDrafts((previous) => ({
                              ...previous,
                              [committee.id]: {
                                ...draft,
                                committee_type: event.target.value,
                              },
                            }))
                          }
                          disabled={isSaving}
                        >
                          {committeeTypeOptions.map((option) => (
                            <option key={option.value} value={option.value}>
                              {option.label}
                            </option>
                          ))}
                        </select>
                      </td>
                      <td className="px-3 py-3">
                        <Input
                          value={draft.description}
                          onChange={(event) =>
                            setDrafts((previous) => ({
                              ...previous,
                              [committee.id]: {
                                ...draft,
                                description: event.target.value,
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
                      </td>
                      <td className="px-3 py-3">
                        <div className="flex flex-wrap gap-2">
                          <Button type="button" size="sm" variant="outline" onClick={() => void handleSave(committee)} disabled={isSaving}>
                            Save
                          </Button>
                          <Button
                            type="button"
                            size="sm"
                            variant="outline"
                            onClick={() => void handleDeactivate(committee)}
                            disabled={isSaving || !draft.is_active}
                          >
                            Deactivate
                          </Button>
                          <Link
                            to={`/organization/committees/${committee.id}`}
                            className="inline-flex h-9 items-center rounded-md border border-slate-300 px-3 text-xs font-semibold text-slate-700 hover:bg-slate-50"
                          >
                            <UsersRound className="mr-1.5 h-3.5 w-3.5" />
                            Workspace
                          </Link>
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
          <p className="text-xs text-slate-700">Page {page}</p>
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

export default OrganizationCommitteesPage;

