import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { Loader2, RefreshCw, UsersRound, UserRoundCheck } from "lucide-react";
import { toast } from "react-toastify";

import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/useAuth";
import { governanceService } from "@/services/governance.service";
import type {
  GovernanceChoiceOption,
  GovernanceCommittee,
  GovernanceCommitteeMembership,
  GovernanceMemberOption,
} from "@/types";

type MembershipDraft = {
  committee_role: string;
  can_vote: boolean;
  is_active: boolean;
};

const SELECT_FIELD_CLASS =
  "h-10 rounded-md border border-border bg-input px-3 text-sm text-foreground shadow-xs outline-none transition-[color,box-shadow] focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px] disabled:cursor-not-allowed disabled:opacity-60";

const CommitteeDetailPage: React.FC = () => {
  const navigate = useNavigate();
  const { committeeId = "" } = useParams<{ committeeId: string }>();
  const { userType, activeOrganizationId, canManageActiveOrganizationGovernance } = useAuth();

  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [savingId, setSavingId] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [chairAssigning, setChairAssigning] = useState(false);
  const [showInactive, setShowInactive] = useState(false);
  const [committee, setCommittee] = useState<GovernanceCommittee | null>(null);
  const [memberships, setMemberships] = useState<GovernanceCommitteeMembership[]>([]);
  const [memberOptions, setMemberOptions] = useState<GovernanceMemberOption[]>([]);
  const [committeeRoleOptions, setCommitteeRoleOptions] = useState<GovernanceChoiceOption[]>([]);
  const [drafts, setDrafts] = useState<Record<string, MembershipDraft>>({});
  const [createForm, setCreateForm] = useState({
    organization_membership_id: "",
    committee_role: "member",
    can_vote: true,
  });
  const [chairTargetMembershipId, setChairTargetMembershipId] = useState("");
  const [chairCanVote, setChairCanVote] = useState(true);

  const canManage = userType !== "applicant" && canManageActiveOrganizationGovernance;

  const loadData = useCallback(async () => {
    if (!committeeId || !canManage || !activeOrganizationId) {
      setCommittee(null);
      setMemberships([]);
      setMemberOptions([]);
      setCommitteeRoleOptions([]);
      return;
    }

    const [committeeResponse, membershipsResponse, memberOptionsResponse, choicesResponse] = await Promise.all([
      governanceService.getCommittee(committeeId),
      governanceService.listCommitteeMemberships({
        committee: committeeId,
        is_active: showInactive ? undefined : true,
      }),
      governanceService.listMemberOptions({ active_only: true }),
      governanceService.getGovernanceChoices(),
    ]);

    setCommittee(committeeResponse);
    setMemberships(membershipsResponse.results || []);
    setMemberOptions(memberOptionsResponse || []);
    setCommitteeRoleOptions(choicesResponse.committee_roles || []);

    setDrafts((previous) => {
      const next: Record<string, MembershipDraft> = {};
      for (const item of membershipsResponse.results || []) {
        next[item.id] = previous[item.id] || {
          committee_role: item.committee_role,
          can_vote: Boolean(item.can_vote),
          is_active: Boolean(item.is_active),
        };
      }
      return next;
    });

    setCreateForm((previous) => ({
      ...previous,
      organization_membership_id:
        previous.organization_membership_id || memberOptionsResponse[0]?.organization_membership_id || "",
      committee_role:
        previous.committee_role ||
        (choicesResponse.committee_roles || []).find((item) => item.value !== "chair")?.value ||
        "member",
    }));
  }, [activeOrganizationId, canManage, committeeId, showInactive]);

  useEffect(() => {
    const run = async () => {
      setLoading(true);
      try {
        await loadData();
      } catch (error) {
        toast.error(error instanceof Error ? error.message : "Failed to load committee workspace.");
      } finally {
        setLoading(false);
      }
    };
    void run();
  }, [loadData]);

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      await loadData();
      toast.success("Committee workspace refreshed.");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Unable to refresh committee workspace.");
    } finally {
      setRefreshing(false);
    }
  };

  const selectedMemberOption = useMemo(
    () =>
      memberOptions.find(
        (option) => option.organization_membership_id === createForm.organization_membership_id,
      ) || null,
    [createForm.organization_membership_id, memberOptions],
  );

  const activeChair = useMemo(
    () => memberships.find((membership) => membership.committee_role === "chair" && membership.is_active) || null,
    [memberships],
  );

  const chairCandidates = useMemo(
    () =>
      memberships.filter(
        (membership) => membership.is_active && membership.id !== activeChair?.id,
      ),
    [activeChair?.id, memberships],
  );

  const handleCreateMembership = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!committeeId || !selectedMemberOption) {
      toast.error("Select an organization member to assign.");
      return;
    }
    if (createForm.committee_role === "chair") {
      toast.error("Use chair reassignment flow to assign committee chair.");
      return;
    }
    setCreating(true);
    try {
      await governanceService.createCommitteeMembership({
        committee: committeeId,
        user: selectedMemberOption.user_id,
        organization_membership: selectedMemberOption.organization_membership_id,
        committee_role: createForm.committee_role,
        can_vote: createForm.committee_role === "observer" ? false : createForm.can_vote,
        is_active: true,
      });
      toast.success("Committee membership created.");
      await loadData();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to create committee membership.");
    } finally {
      setCreating(false);
    }
  };

  const handleSaveMembership = async (membership: GovernanceCommitteeMembership) => {
    const draft = drafts[membership.id];
    if (!draft) {
      return;
    }
    if (membership.committee_role === "chair") {
      toast.info("Use dedicated chair reassignment flow to change committee chair.");
      return;
    }

    setSavingId(membership.id);
    try {
      await governanceService.updateCommitteeMembership(membership.id, {
        committee_role: draft.committee_role,
        can_vote: draft.committee_role === "observer" ? false : draft.can_vote,
        is_active: draft.is_active,
      });
      toast.success("Committee membership updated.");
      await loadData();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to update committee membership.");
    } finally {
      setSavingId(null);
    }
  };

  const handleDeactivateMembership = async (membership: GovernanceCommitteeMembership) => {
    setSavingId(membership.id);
    try {
      await governanceService.deactivateCommitteeMembership(membership.id);
      toast.success("Committee membership deactivated.");
      await loadData();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to deactivate committee membership.");
    } finally {
      setSavingId(null);
    }
  };

  const handleReassignChair = async () => {
    if (!committeeId || !chairTargetMembershipId) {
      toast.error("Select a target committee member for chair reassignment.");
      return;
    }
    setChairAssigning(true);
    try {
      await governanceService.reassignCommitteeChair(committeeId, {
        target_committee_membership_id: chairTargetMembershipId,
        can_vote: chairCanVote,
      });
      toast.success("Committee chair reassigned.");
      setChairTargetMembershipId("");
      await loadData();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to reassign committee chair.");
    } finally {
      setChairAssigning(false);
    }
  };

  if (!canManage) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-slate-100 px-4 py-10 sm:px-6 lg:px-6 xl:px-8">
        <section className="w-full max-w-xl rounded-2xl border border-amber-200 bg-white p-8 shadow-sm text-center">
          <h1 className="text-2xl font-black text-slate-900">Organization Admin Access Required</h1>
          <p className="mt-3 text-sm text-slate-700">
            Committee workspace is restricted to organization admins.
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
      <main className="flex min-h-screen items-center justify-center bg-slate-100 px-4 py-10 sm:px-6 lg:px-6 xl:px-8">
        <section className="w-full max-w-xl rounded-2xl border border-amber-200 bg-white p-8 shadow-sm text-center">
          <h1 className="text-2xl font-black text-slate-900">Active Organization Required</h1>
          <p className="mt-3 text-sm text-slate-700">
            Select an active organization before managing committee membership.
          </p>
          <div className="mt-6 flex items-center justify-center gap-3">
            <Button type="button" onClick={() => navigate("/organization/setup")}>
              Organization Setup
            </Button>
            <Button type="button" variant="outline" onClick={() => navigate("/organization/committees")}>
              Committees
            </Button>
          </div>
        </section>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-7xl space-y-6 px-4 py-8 sm:px-6 lg:px-6 xl:px-8">
      <header className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border border-cyan-200 bg-cyan-50 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-cyan-800">
              <UsersRound className="h-3.5 w-3.5" />
              Committee Workspace
            </div>
            <h1 className="mt-3 text-3xl font-black tracking-tight text-slate-900">
              {committee?.name || "Committee"}
            </h1>
            <p className="mt-1 text-sm text-slate-700">
              Code: <span className="font-semibold">{committee?.code || "N/A"}</span>
              {" · "}
              Type: <span className="font-semibold">{committee?.committee_type || "N/A"}</span>
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Link
              to="/organization/committees"
              className="inline-flex h-10 items-center rounded-md border border-slate-300 px-3 text-sm font-semibold text-slate-700 hover:bg-slate-50"
            >
              Back to Committees
            </Link>
            <Button type="button" variant="outline" onClick={() => void handleRefresh()} disabled={refreshing || loading}>
              <RefreshCw className={`mr-2 h-4 w-4 ${refreshing ? "animate-spin" : ""}`} />
              Refresh
            </Button>
          </div>
        </div>
      </header>

      {loading ? (
        <section className="rounded-2xl border border-slate-200 bg-white p-10 text-center text-sm text-slate-700">
          <span className="inline-flex items-center gap-2">
            <Loader2 className="h-4 w-4 animate-spin" />
            Loading committee workspace...
          </span>
        </section>
      ) : (
        <>
          <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <h2 className="text-lg font-bold text-slate-900">Assign Committee Member</h2>
            <form className="mt-4 grid gap-3 md:grid-cols-4" onSubmit={handleCreateMembership}>
              <select
                className={SELECT_FIELD_CLASS}
                value={createForm.organization_membership_id}
                onChange={(event) =>
                  setCreateForm((previous) => ({
                    ...previous,
                    organization_membership_id: event.target.value,
                  }))
                }
              >
                {memberOptions.map((option) => (
                  <option key={option.organization_membership_id} value={option.organization_membership_id}>
                    {option.user_full_name || option.user_email} ({option.membership_role || "member"})
                  </option>
                ))}
              </select>
              <select
                className={SELECT_FIELD_CLASS}
                value={createForm.committee_role}
                onChange={(event) =>
                  setCreateForm((previous) => {
                    const nextRole = event.target.value;
                    return {
                      ...previous,
                      committee_role: nextRole,
                      can_vote: nextRole === "observer" ? false : previous.can_vote,
                    };
                  })
                }
              >
                {committeeRoleOptions
                  .filter((option) => option.value !== "chair")
                  .map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
              </select>
              <label className="inline-flex items-center gap-2 rounded-md border border-slate-300 px-3 text-sm text-slate-800">
                <input
                  type="checkbox"
                  checked={createForm.can_vote}
                  disabled={createForm.committee_role === "observer"}
                  onChange={(event) =>
                    setCreateForm((previous) => ({
                      ...previous,
                      can_vote: event.target.checked,
                    }))
                  }
                />
                Voting member
              </label>
              <Button type="submit" disabled={creating || !selectedMemberOption}>
                {creating ? "Assigning..." : "Assign Member"}
              </Button>
            </form>
          </section>

          <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 className="text-lg font-bold text-slate-900">Chair Reassignment</h2>
              <p className="text-xs text-slate-700">
                Current chair: {activeChair?.user_email || "No active chair assigned"}
              </p>
            </div>
            <div className="mt-3 grid gap-3 md:grid-cols-3">
              <select
                className={SELECT_FIELD_CLASS}
                value={chairTargetMembershipId}
                onChange={(event) => setChairTargetMembershipId(event.target.value)}
              >
                <option value="">Select member for chair reassignment</option>
                {chairCandidates.map((membership) => (
                  <option key={membership.id} value={membership.id}>
                    {membership.user_email} ({membership.committee_role})
                  </option>
                ))}
              </select>
              <label className="inline-flex items-center gap-2 rounded-md border border-slate-300 px-3 text-sm text-slate-800">
                <input
                  type="checkbox"
                  checked={chairCanVote}
                  onChange={(event) => setChairCanVote(event.target.checked)}
                />
                Chair can vote
              </label>
              <Button type="button" onClick={() => void handleReassignChair()} disabled={chairAssigning || !chairTargetMembershipId}>
                <UserRoundCheck className="mr-2 h-4 w-4" />
                {chairAssigning ? "Reassigning..." : "Reassign Chair"}
              </Button>
            </div>
          </section>

          <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="mb-3 flex items-center justify-between gap-2">
              <h2 className="text-lg font-bold text-slate-900">Committee Memberships</h2>
              <label className="inline-flex items-center gap-2 text-sm text-slate-700">
                <input
                  type="checkbox"
                  checked={showInactive}
                  onChange={(event) => setShowInactive(event.target.checked)}
                />
                Include inactive
              </label>
            </div>

            {memberships.length === 0 ? (
              <div className="rounded-lg border border-dashed border-slate-300 p-6 text-center text-sm text-slate-700">
                No memberships found for this committee.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-slate-200 text-sm">
                  <thead>
                    <tr className="text-left text-xs font-semibold uppercase tracking-wide text-slate-700">
                      <th className="px-3 py-2">Member</th>
                      <th className="px-3 py-2">Role</th>
                      <th className="px-3 py-2">Voting</th>
                      <th className="px-3 py-2">Status</th>
                      <th className="px-3 py-2">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {memberships.map((membership) => {
                      const draft = drafts[membership.id] || {
                        committee_role: membership.committee_role,
                        can_vote: Boolean(membership.can_vote),
                        is_active: Boolean(membership.is_active),
                      };
                      const isSaving = savingId === membership.id;
                      const isChair = membership.committee_role === "chair";
                      return (
                        <tr key={membership.id}>
                          <td className="px-3 py-3">
                            <p className="font-semibold text-slate-900">{membership.user_email}</p>
                            <p className="text-xs text-slate-700">{membership.organization_name}</p>
                          </td>
                          <td className="px-3 py-3">
                            <select
                              className={SELECT_FIELD_CLASS}
                              value={draft.committee_role}
                              disabled={isSaving || isChair}
                              onChange={(event) =>
                                setDrafts((previous) => {
                                  const nextRole = event.target.value;
                                  return {
                                    ...previous,
                                    [membership.id]: {
                                      ...draft,
                                      committee_role: nextRole,
                                      can_vote: nextRole === "observer" ? false : draft.can_vote,
                                    },
                                  };
                                })
                              }
                            >
                              {committeeRoleOptions
                                .filter((option) => option.value !== "chair")
                                .map((option) => (
                                  <option key={option.value} value={option.value}>
                                    {option.label}
                                  </option>
                                ))}
                            </select>
                            {isChair ? (
                              <p className="mt-1 text-xs text-amber-700">
                                Chair role can be changed only through reassignment.
                              </p>
                            ) : null}
                          </td>
                          <td className="px-3 py-3">
                            <label className="inline-flex items-center gap-2 text-sm text-slate-700">
                              <input
                                type="checkbox"
                                checked={draft.can_vote}
                                disabled={isSaving || draft.committee_role === "observer" || isChair}
                                onChange={(event) =>
                                  setDrafts((previous) => ({
                                    ...previous,
                                    [membership.id]: {
                                      ...draft,
                                      can_vote: event.target.checked,
                                    },
                                  }))
                                }
                              />
                              Can vote
                            </label>
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
                              <Button
                                type="button"
                                size="sm"
                                variant="outline"
                                onClick={() => void handleSaveMembership(membership)}
                                disabled={isSaving || isChair}
                              >
                                Save
                              </Button>
                              <Button
                                type="button"
                                size="sm"
                                variant="outline"
                                onClick={() => void handleDeactivateMembership(membership)}
                                disabled={isSaving || !membership.is_active}
                              >
                                Deactivate
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
          </section>
        </>
      )}
    </main>
  );
};

export default CommitteeDetailPage;
