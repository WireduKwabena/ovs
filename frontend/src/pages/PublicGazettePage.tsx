import React, { useCallback, useEffect, useMemo, useState } from "react";
import { ArrowLeft, FileText, RefreshCw, Stamp } from "lucide-react";
import { Link } from "react-router-dom";

import { governmentService } from "@/services/government.service";
import type { AppointmentStatus, PublicAppointmentRecord } from "@/types";

function formatDate(value: string | null): string {
  if (!value) {
    return "Not specified";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleDateString();
}

function statusLabel(value: AppointmentStatus): string {
  return value
    .split("_")
    .map((part) => `${part.slice(0, 1).toUpperCase()}${part.slice(1)}`)
    .join(" ");
}

export const PublicGazettePage: React.FC = () => {
  const [records, setRecords] = useState<PublicAppointmentRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadFeed = useCallback(async () => {
    setError(null);
    try {
      const feed = await governmentService.listPublicGazetteFeed();
      setRecords(feed);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load gazette feed.");
    }
  }, []);

  useEffect(() => {
    const run = async () => {
      setLoading(true);
      await loadFeed();
      setLoading(false);
    };
    void run();
  }, [loadFeed]);

  const publishedCount = useMemo(
    () => records.filter((item) => item.publication_status === "published").length,
    [records],
  );

  const handleRefresh = async () => {
    setRefreshing(true);
    await loadFeed();
    setRefreshing(false);
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-3 px-4 py-4 sm:px-6 lg:px-8">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-cyan-700">Public Record</p>
            <h1 className="text-2xl font-bold text-slate-900">Government Gazette Feed</h1>
            <p className="text-sm text-slate-700">Published appointments only. Internal vetting data is not displayed.</p>
          </div>
          <div className="flex items-center gap-2">
            <Link
              to="/"
              className="inline-flex items-center gap-2 rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-800 hover:bg-slate-100"
            >
              <ArrowLeft className="h-4 w-4" />
              Home
            </Link>
            <button
              type="button"
              onClick={() => void handleRefresh()}
              disabled={refreshing}
              className="inline-flex items-center gap-2 rounded-md bg-cyan-700 px-3 py-2 text-sm font-medium text-white hover:bg-cyan-800 disabled:cursor-not-allowed disabled:opacity-60"
            >
              <RefreshCw className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`} />
              {refreshing ? "Refreshing..." : "Refresh"}
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        <section className="mb-6 grid gap-4 md:grid-cols-2">
          <article className="rounded-xl border border-slate-200 bg-white p-4">
            <div className="mb-2 inline-flex rounded-md bg-cyan-50 p-2 text-cyan-700">
              <Stamp className="h-4 w-4" />
            </div>
            <p className="text-sm text-slate-700">Published records</p>
            <p className="text-2xl font-bold text-slate-900">{publishedCount}</p>
          </article>
          <article className="rounded-xl border border-slate-200 bg-white p-4">
            <div className="mb-2 inline-flex rounded-md bg-slate-100 p-2 text-slate-700">
              <FileText className="h-4 w-4" />
            </div>
            <p className="text-sm text-slate-700">Total entries in feed</p>
            <p className="text-2xl font-bold text-slate-900">{records.length}</p>
          </article>
        </section>

        {loading ? (
          <div className="rounded-xl border border-slate-200 bg-white p-6 text-sm text-slate-700">
            Loading gazette feed...
          </div>
        ) : error ? (
          <div className="rounded-xl border border-rose-200 bg-rose-50 p-6 text-sm text-rose-800">{error}</div>
        ) : records.length === 0 ? (
          <div className="rounded-xl border border-slate-200 bg-white p-6 text-sm text-slate-700">
            No published appointments are available yet.
          </div>
        ) : (
          <div className="grid gap-4">
            {records.map((record) => (
              <article key={record.id} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <h2 className="text-lg font-semibold text-slate-900">{record.position_title}</h2>
                    <p className="text-sm text-slate-700">{record.institution}</p>
                  </div>
                  <span className="rounded bg-cyan-100 px-2 py-1 text-xs font-semibold text-cyan-800">
                    {statusLabel(record.status)}
                  </span>
                </div>

                <div className="mt-3 grid gap-2 text-sm text-slate-700 md:grid-cols-2">
                  <p>
                    <span className="font-semibold text-slate-900">Nominee:</span> {record.nominee_name}
                  </p>
                  <p>
                    <span className="font-semibold text-slate-900">Nominated by:</span> {record.nominated_by_display}
                  </p>
                  <p>
                    <span className="font-semibold text-slate-900">Organization:</span>{" "}
                    {record.nominated_by_org || "Not specified"}
                  </p>
                  <p>
                    <span className="font-semibold text-slate-900">Appointment date:</span>{" "}
                    {formatDate(record.appointment_date)}
                  </p>
                  <p>
                    <span className="font-semibold text-slate-900">Gazette number:</span>{" "}
                    {record.gazette_number || "Pending"}
                  </p>
                  <p>
                    <span className="font-semibold text-slate-900">Gazette date:</span>{" "}
                    {formatDate(record.gazette_date)}
                  </p>
                  <p className="md:col-span-2">
                    <span className="font-semibold text-slate-900">Publication reference:</span>{" "}
                    {record.publication_reference || "Not provided"}
                  </p>
                  <p className="md:col-span-2">
                    <span className="font-semibold text-slate-900">Published at:</span>{" "}
                    {formatDate(record.published_at)}
                  </p>
                </div>
              </article>
            ))}
          </div>
        )}
      </main>
    </div>
  );
};

export default PublicGazettePage;
