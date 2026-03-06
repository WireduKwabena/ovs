import React, { useCallback, useEffect, useMemo, useState } from "react";
import { CheckCircle2, Clock3, Plus, RefreshCw, ShieldAlert } from "lucide-react";
import { toast } from "react-toastify";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { governmentService } from "@/services/government.service";
import type {
  AppointmentRecord,
  AppointmentStageAction,
  AppointmentStatus,
  GovernmentPosition,
  PersonnelRecord,
  VettingCampaign,
} from "@/types";

const STATUS_OPTIONS: AppointmentStatus[] = [
  "nominated",
  "under_vetting",
  "committee_review",
  "confirmation_pending",
  "appointed",
  "rejected",
  "withdrawn",
  "serving",
  "exited",
];

const AppointmentsRegistryPage: React.FC = () => {
  const [rows, setRows] = useState<AppointmentRecord[]>([]);
  const [positions, setPositions] = useState<GovernmentPosition[]>([]);
  const [personnel, setPersonnel] = useState<PersonnelRecord[]>([]);
  const [campaigns, setCampaigns] = useState<VettingCampaign[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [statusFilter, setStatusFilter] = useState<string>("all");

  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({
    position: "",
    nominee: "",
    appointment_exercise: "",
    nominated_by_display: "",
    nominated_by_org: "",
    nomination_date: new Date().toISOString().slice(0, 10),
    is_public: false,
  });

  const [rowActionLoadingId, setRowActionLoadingId] = useState<string | null>(null);
  const [rowActionStatus, setRowActionStatus] = useState<Record<string, AppointmentStatus>>({});
  const [rowActionReason, setRowActionReason] = useState<Record<string, string>>({});
  const [stageActions, setStageActions] = useState<Record<string, AppointmentStageAction[]>>({});
  const [openActionsFor, setOpenActionsFor] = useState<string | null>(null);

  const loadAll = useCallback(async () => {
    const [appointments, positionRows, personnelRows, campaignRows] = await Promise.all([
      governmentService.listAppointments({
        status: statusFilter === "all" ? undefined : statusFilter,
      }),
      governmentService.listPositions(),
      governmentService.listPersonnel(),
      governmentService.listCampaignsForAppointments(),
    ]);
    setRows(appointments);
    setPositions(positionRows);
    setPersonnel(personnelRows);
    setCampaigns(campaignRows);
  }, [statusFilter]);

  useEffect(() => {
    const run = async () => {
      setLoading(true);
      try {
        await loadAll();
      } catch (error) {
        toast.error(error instanceof Error ? error.message : "Failed to load appointment registry.");
      } finally {
        setLoading(false);
      }
    };
    void run();
  }, [loadAll]);

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      await loadAll();
      toast.success("Appointment registry refreshed.");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Refresh failed.");
    } finally {
      setRefreshing(false);
    }
  };

  const handleCreate = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!form.position || !form.nominee || !form.nominated_by_display.trim()) {
      toast.error("Position, nominee, and nominated by display are required.");
      return;
    }

    setCreating(true);
    try {
      await governmentService.createAppointment({
        position: form.position,
        nominee: form.nominee,
        appointment_exercise: form.appointment_exercise || null,
        nominated_by_display: form.nominated_by_display.trim(),
        nominated_by_org: form.nominated_by_org.trim(),
        nomination_date: form.nomination_date,
        is_public: form.is_public,
      });
      toast.success("Appointment record created and vetting linkage ensured.");
      setForm((previous) => ({
        ...previous,
        nominated_by_display: "",
        nominated_by_org: "",
        is_public: false,
      }));
      await loadAll();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to create appointment record.");
    } finally {
      setCreating(false);
    }
  };

  const applyRowStatusAction = async (row: AppointmentRecord) => {
    const targetStatus = rowActionStatus[row.id];
    if (!targetStatus || targetStatus === row.status) {
      toast.info("Choose a different status to advance.");
      return;
    }
    const reason = rowActionReason[row.id] || "";

    setRowActionLoadingId(row.id);
    try {
      if (targetStatus === "appointed") {
        await governmentService.appoint(row.id, reason);
      } else if (targetStatus === "rejected") {
        await governmentService.reject(row.id, reason);
      } else {
        await governmentService.advanceAppointmentStage(row.id, {
          status: targetStatus,
          reason_note: reason,
        });
      }
      toast.success("Appointment stage updated.");
      await loadAll();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to advance appointment stage.");
    } finally {
      setRowActionLoadingId(null);
    }
  };

  const handleEnsureLinkage = async (row: AppointmentRecord) => {
    setRowActionLoadingId(row.id);
    try {
      await governmentService.ensureVettingLinkage(row.id);
      toast.success("Vetting linkage ensured.");
      await loadAll();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to ensure linkage.");
    } finally {
      setRowActionLoadingId(null);
    }
  };

  const handleToggleActions = async (row: AppointmentRecord) => {
    if (openActionsFor === row.id) {
      setOpenActionsFor(null);
      return;
    }

    setOpenActionsFor(row.id);
    if (stageActions[row.id]) {
      return;
    }
    try {
      const actions = await governmentService.listStageActions(row.id);
      setStageActions((previous) => ({ ...previous, [row.id]: actions }));
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to load stage actions.");
    }
  };

  const stats = useMemo(() => {
    const total = rows.length;
    const active = rows.filter((row) =>
      ["nominated", "under_vetting", "committee_review", "confirmation_pending"].includes(row.status),
    ).length;
    const appointed = rows.filter((row) => row.status === "appointed" || row.status === "serving").length;
    const rejected = rows.filter((row) => row.status === "rejected").length;
    return { total, active, appointed, rejected };
  }, [rows]);

  return (
    <main className="mx-auto max-w-7xl px-4 py-8 space-y-6">
      <header className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-3xl font-black tracking-tight text-slate-900">Appointment Registry</h1>
            <p className="mt-1 text-sm text-slate-700">
              Manage nomination, vetting progression, and appointment decisions.
            </p>
          </div>
          <Button type="button" variant="outline" onClick={() => void handleRefresh()} disabled={refreshing}>
            <RefreshCw className={`mr-2 h-4 w-4 ${refreshing ? "animate-spin" : ""}`} />
            Refresh
          </Button>
        </div>
      </header>

      <section className="grid gap-4 md:grid-cols-4">
        <article className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <p className="text-sm text-slate-700">Total Records</p>
          <p className="mt-2 text-3xl font-black text-slate-900">{stats.total}</p>
        </article>
        <article className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <p className="text-sm text-slate-700">Active Pipeline</p>
          <p className="mt-2 text-3xl font-black text-indigo-700">{stats.active}</p>
        </article>
        <article className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <p className="text-sm text-slate-700">Appointed / Serving</p>
          <p className="mt-2 text-3xl font-black text-emerald-700">{stats.appointed}</p>
        </article>
        <article className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <p className="text-sm text-slate-700">Rejected</p>
          <p className="mt-2 text-3xl font-black text-rose-700">{stats.rejected}</p>
        </article>
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="text-lg font-bold text-slate-900">Create Appointment Record</h2>
        <form onSubmit={handleCreate} className="mt-4 grid gap-3 md:grid-cols-2">
          <div>
            <label className="mb-1 block text-xs font-semibold uppercase text-slate-700">Position</label>
            <select
              className="h-10 w-full rounded-md border border-slate-300 px-3 text-sm text-slate-900"
              value={form.position}
              onChange={(event) => setForm((p) => ({ ...p, position: event.target.value }))}
            >
              <option value="">Select position</option>
              {positions.map((position) => (
                <option key={position.id} value={position.id}>
                  {position.title} - {position.institution}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="mb-1 block text-xs font-semibold uppercase text-slate-700">Nominee</label>
            <select
              className="h-10 w-full rounded-md border border-slate-300 px-3 text-sm text-slate-900"
              value={form.nominee}
              onChange={(event) => setForm((p) => ({ ...p, nominee: event.target.value }))}
            >
              <option value="">Select nominee</option>
              {personnel.map((row) => (
                <option key={row.id} value={row.id}>
                  {row.full_name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="mb-1 block text-xs font-semibold uppercase text-slate-700">Appointment Exercise (Campaign)</label>
            <select
              className="h-10 w-full rounded-md border border-slate-300 px-3 text-sm text-slate-900"
              value={form.appointment_exercise}
              onChange={(event) => setForm((p) => ({ ...p, appointment_exercise: event.target.value }))}
            >
              <option value="">None</option>
              {campaigns.map((campaign) => (
                <option key={campaign.id} value={campaign.id}>
                  {campaign.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="mb-1 block text-xs font-semibold uppercase text-slate-700">Nomination Date</label>
            <Input
              type="date"
              value={form.nomination_date}
              onChange={(event) => setForm((p) => ({ ...p, nomination_date: event.target.value }))}
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-semibold uppercase text-slate-700">Nominated By (Display)</label>
            <Input
              value={form.nominated_by_display}
              onChange={(event) => setForm((p) => ({ ...p, nominated_by_display: event.target.value }))}
              placeholder="H.E. President"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-semibold uppercase text-slate-700">Nominating Organization</label>
            <Input
              value={form.nominated_by_org}
              onChange={(event) => setForm((p) => ({ ...p, nominated_by_org: event.target.value }))}
              placeholder="Office of the President"
            />
          </div>
          <label className="inline-flex items-center gap-2 text-sm text-slate-800 md:col-span-2">
            <input
              type="checkbox"
              checked={form.is_public}
              onChange={(event) => setForm((p) => ({ ...p, is_public: event.target.checked }))}
            />
            Mark record public
          </label>
          <div className="md:col-span-2 flex justify-end">
            <Button type="submit" disabled={creating}>
              <Plus className="mr-2 h-4 w-4" />
              {creating ? "Saving..." : "Create Appointment"}
            </Button>
          </div>
        </form>
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-lg font-bold text-slate-900">Appointment Records</h2>
          <select
            className="h-10 rounded-md border border-slate-300 px-3 text-sm text-slate-900"
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value)}
          >
            <option value="all">All statuses</option>
            {STATUS_OPTIONS.map((status) => (
              <option key={status} value={status}>
                {status}
              </option>
            ))}
          </select>
        </div>

        {loading ? (
          <p className="mt-4 text-sm text-slate-700">Loading appointment records...</p>
        ) : rows.length === 0 ? (
          <div className="mt-4 rounded-lg border border-dashed border-slate-300 p-6 text-center text-sm text-slate-700">
            No appointment records found.
          </div>
        ) : (
          <div className="mt-4 space-y-4">
            {rows.map((row) => {
              const statusTarget = rowActionStatus[row.id] || row.status;
              const reason = rowActionReason[row.id] || "";
              const actionsOpen = openActionsFor === row.id;
              const itemActions = stageActions[row.id] || [];
              return (
                <article key={row.id} className="rounded-xl border border-slate-200 p-4">
                  <div className="flex flex-wrap items-start justify-between gap-4">
                    <div>
                      <p className="text-lg font-semibold text-slate-900">{row.position_title || row.position}</p>
                      <p className="text-sm text-slate-700">
                        Nominee: {row.nominee_name || row.nominee} | Status:{" "}
                        <span className="font-semibold text-indigo-700">{row.status}</span>
                      </p>
                      <p className="text-xs text-slate-700">
                        Nominated by: {row.nominated_by_display} on {new Date(row.nomination_date).toLocaleDateString()}
                      </p>
                      <div className="mt-1 flex flex-wrap items-center gap-2 text-xs">
                        {row.vetting_case ? (
                          <span className="inline-flex items-center gap-1 rounded bg-emerald-100 px-2 py-1 font-semibold text-emerald-800">
                            <CheckCircle2 className="h-3 w-3" />
                            Linked case
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 rounded bg-amber-100 px-2 py-1 font-semibold text-amber-800">
                            <ShieldAlert className="h-3 w-3" />
                            Missing case
                          </span>
                        )}
                        {row.is_public ? (
                          <span className="inline-flex rounded bg-indigo-100 px-2 py-1 font-semibold text-indigo-800">Public</span>
                        ) : null}
                      </div>
                    </div>
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => void handleEnsureLinkage(row)}
                      disabled={rowActionLoadingId === row.id}
                    >
                      <Clock3 className="mr-2 h-4 w-4" />
                      Ensure Linkage
                    </Button>
                  </div>

                  <div className="mt-3 grid gap-2 md:grid-cols-3">
                    <select
                      className="h-10 rounded-md border border-slate-300 px-3 text-sm text-slate-900"
                      value={statusTarget}
                      onChange={(event) =>
                        setRowActionStatus((previous) => ({
                          ...previous,
                          [row.id]: event.target.value as AppointmentStatus,
                        }))
                      }
                    >
                      {STATUS_OPTIONS.map((status) => (
                        <option key={status} value={status}>
                          {status}
                        </option>
                      ))}
                    </select>
                    <Input
                      value={reason}
                      onChange={(event) =>
                        setRowActionReason((previous) => ({
                          ...previous,
                          [row.id]: event.target.value,
                        }))
                      }
                      placeholder="Reason note (optional)"
                    />
                    <Button
                      type="button"
                      onClick={() => void applyRowStatusAction(row)}
                      disabled={rowActionLoadingId === row.id}
                    >
                      {rowActionLoadingId === row.id ? "Updating..." : "Apply Status"}
                    </Button>
                  </div>

                  <div className="mt-3">
                    <button
                      type="button"
                      className="text-sm font-semibold text-indigo-700 hover:text-indigo-800"
                      onClick={() => void handleToggleActions(row)}
                    >
                      {actionsOpen ? "Hide stage actions" : "Show stage actions"}
                    </button>
                    {actionsOpen ? (
                      <div className="mt-2 rounded-lg border border-slate-200 bg-slate-50 p-3">
                        {itemActions.length === 0 ? (
                          <p className="text-xs text-slate-700">No stage actions available yet.</p>
                        ) : (
                          <ul className="space-y-2 text-xs text-slate-800">
                            {itemActions.map((item) => (
                              <li key={item.id} className="rounded border border-slate-200 bg-white p-2">
                                <p className="font-semibold">
                                  {item.previous_status}
                                  {" -> "}
                                  {item.new_status}
                                </p>
                                <p>Actor: {item.actor_email || item.actor}</p>
                                <p>Role: {item.actor_role}</p>
                                <p>At: {new Date(item.acted_at).toLocaleString()}</p>
                                {item.reason_note ? <p>Reason: {item.reason_note}</p> : null}
                              </li>
                            ))}
                          </ul>
                        )}
                      </div>
                    ) : null}
                  </div>
                </article>
              );
            })}
          </div>
        )}
      </section>
    </main>
  );
};

export default AppointmentsRegistryPage;
