import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Plus, RefreshCw, Users } from "lucide-react";
import { toast } from "react-toastify";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/hooks/useAuth";
import type { PersonnelRecord } from "@/types";
import { governmentService } from "@/services/government.service";

const GovernmentPersonnelPage: React.FC = () => {
  const { activeOrganization, activeOrganizationId } = useAuth();
  const [rows, setRows] = useState<PersonnelRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [search, setSearch] = useState("");
  const [officeholdersOnly, setOfficeholdersOnly] = useState(false);

  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({
    full_name: "",
    nationality: "Ghanaian",
    gender: "",
    contact_email: "",
    contact_phone: "",
    bio_summary: "",
    is_active_officeholder: false,
    is_public: true,
  });

  const loadPersonnel = useCallback(async () => {
    const data = await governmentService.listPersonnel({
      is_active_officeholder: officeholdersOnly ? true : undefined,
      search: search.trim() || undefined,
    });
    setRows(data);
  }, [activeOrganizationId, officeholdersOnly, search]);

  useEffect(() => {
    const run = async () => {
      setLoading(true);
      try {
        await loadPersonnel();
      } catch (error) {
        toast.error(error instanceof Error ? error.message : "Failed to load personnel records.");
      } finally {
        setLoading(false);
      }
    };
    void run();
  }, [loadPersonnel]);

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      await loadPersonnel();
      toast.success("Personnel registry refreshed.");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Refresh failed.");
    } finally {
      setRefreshing(false);
    }
  };

  const handleCreate = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!form.full_name.trim()) {
      toast.error("Full name is required.");
      return;
    }
    setCreating(true);
    try {
      await governmentService.createPersonnel({
        full_name: form.full_name.trim(),
        nationality: form.nationality.trim() || "Ghanaian",
        gender: form.gender.trim(),
        contact_email: form.contact_email.trim(),
        contact_phone: form.contact_phone.trim(),
        bio_summary: form.bio_summary.trim(),
        is_active_officeholder: form.is_active_officeholder,
        is_public: form.is_public,
      });
      toast.success("Personnel record created.");
      setForm((previous) => ({
        ...previous,
        full_name: "",
        gender: "",
        contact_email: "",
        contact_phone: "",
        bio_summary: "",
      }));
      await loadPersonnel();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to create personnel record.");
    } finally {
      setCreating(false);
    }
  };

  const scopedRows = useMemo(() => {
    return rows.filter((item) => {
      if (!activeOrganizationId) {
        return true;
      }
      if (!item.organization) {
        return true;
      }
      return String(item.organization) === activeOrganizationId;
    });
  }, [activeOrganizationId, rows]);

  const stats = useMemo(() => {
    const total = scopedRows.length;
    const officeholders = scopedRows.filter((item) => item.is_active_officeholder).length;
    const publicCount = scopedRows.filter((item) => item.is_public).length;
    return { total, officeholders, publicCount };
  }, [scopedRows]);

  return (
    <main className="mx-auto max-w-7xl px-4 py-8 space-y-6">
      <header className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-3xl font-black tracking-tight text-slate-900">Government Personnel</h1>
            <p className="mt-1 text-sm text-slate-700">
              Manage nominee and officeholder records used in appointment lifecycle workflows.
            </p>
            <p className="mt-1 text-xs font-semibold uppercase tracking-wide text-slate-700">
              Active organization scope: {activeOrganization?.name || "Default"}
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
          <p className="text-sm text-slate-700">Total Personnel</p>
          <p className="mt-2 text-3xl font-black text-slate-900">{stats.total}</p>
        </article>
        <article className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <p className="text-sm text-slate-700">Active Officeholders</p>
          <p className="mt-2 text-3xl font-black text-indigo-700">{stats.officeholders}</p>
        </article>
        <article className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <p className="text-sm text-slate-700">Public Profiles</p>
          <p className="mt-2 text-3xl font-black text-emerald-700">{stats.publicCount}</p>
        </article>
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="text-lg font-bold text-slate-900">Register Personnel Record</h2>
        <form onSubmit={handleCreate} className="mt-4 grid gap-3 md:grid-cols-2">
          <div>
            <label className="mb-1 block text-xs font-semibold uppercase text-slate-700">Full Name</label>
            <Input
              value={form.full_name}
              onChange={(event) => setForm((p) => ({ ...p, full_name: event.target.value }))}
              placeholder="Jane Doe"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-semibold uppercase text-slate-700">Nationality</label>
            <Input
              value={form.nationality}
              onChange={(event) => setForm((p) => ({ ...p, nationality: event.target.value }))}
              placeholder="Ghanaian"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-semibold uppercase text-slate-700">Gender</label>
            <Input
              value={form.gender}
              onChange={(event) => setForm((p) => ({ ...p, gender: event.target.value }))}
              placeholder="Female / Male / ..."
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-semibold uppercase text-slate-700">Email</label>
            <Input
              value={form.contact_email}
              onChange={(event) => setForm((p) => ({ ...p, contact_email: event.target.value }))}
              placeholder="nominee@example.com"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-semibold uppercase text-slate-700">Phone</label>
            <Input
              value={form.contact_phone}
              onChange={(event) => setForm((p) => ({ ...p, contact_phone: event.target.value }))}
              placeholder="+233..."
            />
          </div>
          <div className="md:col-span-2">
            <label className="mb-1 block text-xs font-semibold uppercase text-slate-700">Bio Summary</label>
            <Input
              value={form.bio_summary}
              onChange={(event) => setForm((p) => ({ ...p, bio_summary: event.target.value }))}
              placeholder="Brief role/profile summary"
            />
          </div>
          <div className="flex flex-wrap items-center gap-3 md:col-span-2">
            <label className="inline-flex items-center gap-2 text-sm text-slate-800">
              <input
                type="checkbox"
                checked={form.is_active_officeholder}
                onChange={(event) => setForm((p) => ({ ...p, is_active_officeholder: event.target.checked }))}
              />
              Active officeholder
            </label>
            <label className="inline-flex items-center gap-2 text-sm text-slate-800">
              <input
                type="checkbox"
                checked={form.is_public}
                onChange={(event) => setForm((p) => ({ ...p, is_public: event.target.checked }))}
              />
              Public profile
            </label>
          </div>
          <div className="md:col-span-2 flex justify-end">
            <Button type="submit" disabled={creating}>
              <Plus className="mr-2 h-4 w-4" />
              {creating ? "Saving..." : "Create Personnel"}
            </Button>
          </div>
        </form>
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-lg font-bold text-slate-900">Personnel Registry</h2>
          <div className="flex w-full flex-wrap items-center gap-2 md:w-auto">
            <Input
              className="w-full md:w-72"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search name, email, phone"
            />
            <label className="inline-flex items-center gap-2 text-sm text-slate-800">
              <input
                type="checkbox"
                checked={officeholdersOnly}
                onChange={(event) => setOfficeholdersOnly(event.target.checked)}
              />
              Officeholders only
            </label>
          </div>
        </div>

        {loading ? (
          <p className="mt-4 text-sm text-slate-700">Loading personnel...</p>
        ) : scopedRows.length === 0 ? (
          <div className="mt-4 rounded-lg border border-dashed border-slate-300 p-6 text-center text-sm text-slate-700">
            No personnel records found.
          </div>
        ) : (
          <div className="mt-4 overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200 text-sm">
              <thead>
                <tr className="text-left text-xs font-semibold uppercase tracking-wide text-slate-700">
                  <th className="px-3 py-2">Name</th>
                  <th className="px-3 py-2">Contacts</th>
                  <th className="px-3 py-2">Nationality</th>
                  <th className="px-3 py-2">Linked Candidate</th>
                  <th className="px-3 py-2">Flags</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {scopedRows.map((row) => (
                  <tr key={row.id}>
                    <td className="px-3 py-3">
                      <p className="font-semibold text-slate-900">{row.full_name}</p>
                      <p className="text-xs text-slate-700">{row.gender || "Gender not specified"}</p>
                    </td>
                    <td className="px-3 py-3 text-slate-800">
                      <p>{row.contact_email || "-"}</p>
                      <p className="text-xs text-slate-700">{row.contact_phone || "-"}</p>
                    </td>
                    <td className="px-3 py-3 text-slate-800">{row.nationality}</td>
                    <td className="px-3 py-3 text-slate-800">{row.linked_candidate_email || "-"}</td>
                    <td className="px-3 py-3">
                      <div className="flex flex-wrap gap-1">
                        {row.is_active_officeholder ? (
                          <span className="inline-flex items-center gap-1 rounded bg-indigo-100 px-2 py-1 text-xs font-semibold text-indigo-800">
                            <Users className="h-3 w-3" />
                            Serving
                          </span>
                        ) : (
                          <span className="inline-flex rounded bg-slate-100 px-2 py-1 text-xs font-semibold text-slate-700">
                            Nominee
                          </span>
                        )}
                        {row.is_public ? (
                          <span className="inline-flex rounded bg-emerald-100 px-2 py-1 text-xs font-semibold text-emerald-800">
                            Public
                          </span>
                        ) : (
                          <span className="inline-flex rounded bg-amber-100 px-2 py-1 text-xs font-semibold text-amber-800">
                            Private
                          </span>
                        )}
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

export default GovernmentPersonnelPage;
