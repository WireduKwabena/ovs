import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Building2, Plus, RefreshCw, ShieldCheck } from "lucide-react";
import { toast } from "react-toastify";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { GovernmentPosition } from "@/types";
import { governmentService } from "@/services/government.service";

type BranchOption = GovernmentPosition["branch"];

const branchOptions: Array<{ value: BranchOption; label: string }> = [
  { value: "executive", label: "Executive" },
  { value: "legislative", label: "Legislative" },
  { value: "judicial", label: "Judicial" },
  { value: "independent", label: "Independent" },
  { value: "local", label: "Local Government" },
];

const GovernmentPositionsPage: React.FC = () => {
  const [rows, setRows] = useState<GovernmentPosition[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [search, setSearch] = useState("");

  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({
    title: "",
    branch: "executive" as BranchOption,
    institution: "",
    appointment_authority: "",
    constitutional_basis: "",
    required_qualifications: "",
    confirmation_required: false,
    is_public: true,
    is_vacant: true,
  });

  const loadPositions = useCallback(async () => {
    const data = await governmentService.listPositions({
      search: search.trim() || undefined,
    });
    setRows(data);
  }, [search]);

  useEffect(() => {
    const run = async () => {
      setLoading(true);
      try {
        await loadPositions();
      } catch (error) {
        toast.error(error instanceof Error ? error.message : "Failed to load government positions.");
      } finally {
        setLoading(false);
      }
    };
    void run();
  }, [loadPositions]);

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      await loadPositions();
      toast.success("Government positions refreshed.");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Refresh failed.");
    } finally {
      setRefreshing(false);
    }
  };

  const handleCreate = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!form.title.trim() || !form.institution.trim() || !form.appointment_authority.trim()) {
      toast.error("Title, institution, and appointment authority are required.");
      return;
    }

    setCreating(true);
    try {
      await governmentService.createPosition({
        ...form,
        title: form.title.trim(),
        institution: form.institution.trim(),
        appointment_authority: form.appointment_authority.trim(),
        constitutional_basis: form.constitutional_basis.trim(),
        required_qualifications: form.required_qualifications.trim(),
      });
      toast.success("Government position created.");
      setForm((previous) => ({
        ...previous,
        title: "",
        institution: "",
        appointment_authority: "",
        constitutional_basis: "",
        required_qualifications: "",
      }));
      await loadPositions();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to create position.");
    } finally {
      setCreating(false);
    }
  };

  const stats = useMemo(() => {
    const total = rows.length;
    const vacant = rows.filter((item) => item.is_vacant).length;
    const publicCount = rows.filter((item) => item.is_public).length;
    return { total, vacant, publicCount };
  }, [rows]);

  return (
    <main className="mx-auto max-w-7xl px-4 py-8 space-y-6">
      <header className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-3xl font-black tracking-tight text-slate-900">Government Positions</h1>
            <p className="mt-1 text-sm text-slate-700">
              Manage official positions that feed nomination, vetting, and appointment workflows.
            </p>
          </div>
          <Button type="button" variant="outline" onClick={() => void handleRefresh()} disabled={refreshing}>
            <RefreshCw className={`mr-2 h-4 w-4 ${refreshing ? "animate-spin" : ""}`} />
            Refresh
          </Button>
        </div>
      </header>

      <section className="grid gap-4 md:grid-cols-3">
        <article className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <p className="text-sm text-slate-700">Total Positions</p>
          <p className="mt-2 text-3xl font-black text-slate-900">{stats.total}</p>
        </article>
        <article className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <p className="text-sm text-slate-700">Vacant Positions</p>
          <p className="mt-2 text-3xl font-black text-indigo-700">{stats.vacant}</p>
        </article>
        <article className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <p className="text-sm text-slate-700">Public Positions</p>
          <p className="mt-2 text-3xl font-black text-emerald-700">{stats.publicCount}</p>
        </article>
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="text-lg font-bold text-slate-900">Register Position</h2>
        <form onSubmit={handleCreate} className="mt-4 grid gap-3 md:grid-cols-2">
          <div>
            <label className="mb-1 block text-xs font-semibold uppercase text-slate-700">Title</label>
            <Input
              value={form.title}
              onChange={(event) => setForm((p) => ({ ...p, title: event.target.value }))}
              placeholder="Minister of Finance"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-semibold uppercase text-slate-700">Branch</label>
            <select
              className="h-10 w-full rounded-md border border-slate-300 px-3 text-sm text-slate-900"
              value={form.branch}
              onChange={(event) => setForm((p) => ({ ...p, branch: event.target.value as BranchOption }))}
            >
              {branchOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="mb-1 block text-xs font-semibold uppercase text-slate-700">Institution</label>
            <Input
              value={form.institution}
              onChange={(event) => setForm((p) => ({ ...p, institution: event.target.value }))}
              placeholder="Ministry of Finance"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-semibold uppercase text-slate-700">Appointment Authority</label>
            <Input
              value={form.appointment_authority}
              onChange={(event) => setForm((p) => ({ ...p, appointment_authority: event.target.value }))}
              placeholder="President"
            />
          </div>
          <div className="md:col-span-2">
            <label className="mb-1 block text-xs font-semibold uppercase text-slate-700">Constitutional Basis</label>
            <Input
              value={form.constitutional_basis}
              onChange={(event) => setForm((p) => ({ ...p, constitutional_basis: event.target.value }))}
              placeholder="Article..."
            />
          </div>
          <div className="md:col-span-2">
            <label className="mb-1 block text-xs font-semibold uppercase text-slate-700">Required Qualifications</label>
            <Input
              value={form.required_qualifications}
              onChange={(event) => setForm((p) => ({ ...p, required_qualifications: event.target.value }))}
              placeholder="Professional and academic requirements"
            />
          </div>
          <label className="inline-flex items-center gap-2 rounded-md border border-slate-200 px-3 py-2 text-sm text-slate-800">
            <input
              type="checkbox"
              checked={form.confirmation_required}
              onChange={(event) => setForm((p) => ({ ...p, confirmation_required: event.target.checked }))}
            />
            Parliamentary confirmation required
          </label>
          <div className="flex flex-wrap items-center gap-3">
            <label className="inline-flex items-center gap-2 text-sm text-slate-800">
              <input
                type="checkbox"
                checked={form.is_public}
                onChange={(event) => setForm((p) => ({ ...p, is_public: event.target.checked }))}
              />
              Public
            </label>
            <label className="inline-flex items-center gap-2 text-sm text-slate-800">
              <input
                type="checkbox"
                checked={form.is_vacant}
                onChange={(event) => setForm((p) => ({ ...p, is_vacant: event.target.checked }))}
              />
              Vacant
            </label>
          </div>
          <div className="md:col-span-2 flex justify-end">
            <Button type="submit" disabled={creating}>
              <Plus className="mr-2 h-4 w-4" />
              {creating ? "Saving..." : "Create Position"}
            </Button>
          </div>
        </form>
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-lg font-bold text-slate-900">Position Registry</h2>
          <Input
            className="w-full md:w-72"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search title, institution, authority"
          />
        </div>

        {loading ? (
          <p className="mt-4 text-sm text-slate-700">Loading positions...</p>
        ) : rows.length === 0 ? (
          <div className="mt-4 rounded-lg border border-dashed border-slate-300 p-6 text-center text-sm text-slate-700">
            No government positions found.
          </div>
        ) : (
          <div className="mt-4 overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200 text-sm">
              <thead>
                <tr className="text-left text-xs font-semibold uppercase tracking-wide text-slate-700">
                  <th className="px-3 py-2">Title</th>
                  <th className="px-3 py-2">Institution</th>
                  <th className="px-3 py-2">Branch</th>
                  <th className="px-3 py-2">Authority</th>
                  <th className="px-3 py-2">Flags</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {rows.map((position) => (
                  <tr key={position.id}>
                    <td className="px-3 py-3">
                      <p className="font-semibold text-slate-900">{position.title}</p>
                      <p className="text-xs text-slate-700">{position.current_holder_name || "No current holder"}</p>
                    </td>
                    <td className="px-3 py-3 text-slate-800">{position.institution}</td>
                    <td className="px-3 py-3 text-slate-800">
                      <span className="inline-flex rounded-full bg-slate-100 px-2 py-1 text-xs font-semibold text-slate-700">
                        {position.branch}
                      </span>
                    </td>
                    <td className="px-3 py-3 text-slate-800">{position.appointment_authority}</td>
                    <td className="px-3 py-3">
                      <div className="flex flex-wrap gap-1">
                        {position.is_vacant ? (
                          <span className="inline-flex rounded bg-amber-100 px-2 py-1 text-xs font-semibold text-amber-800">
                            Vacant
                          </span>
                        ) : (
                          <span className="inline-flex rounded bg-emerald-100 px-2 py-1 text-xs font-semibold text-emerald-800">
                            Occupied
                          </span>
                        )}
                        {position.is_public ? (
                          <span className="inline-flex items-center gap-1 rounded bg-indigo-100 px-2 py-1 text-xs font-semibold text-indigo-800">
                            <ShieldCheck className="h-3 w-3" />
                            Public
                          </span>
                        ) : null}
                        {position.confirmation_required ? (
                          <span className="inline-flex items-center gap-1 rounded bg-cyan-100 px-2 py-1 text-xs font-semibold text-cyan-800">
                            <Building2 className="h-3 w-3" />
                            Confirm
                          </span>
                        ) : null}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </main>
  );
};

export default GovernmentPositionsPage;
