import React, { useCallback, useEffect, useState } from "react";
import { ArrowLeft, FileText, RefreshCw, ShieldCheck } from "lucide-react";
import { Link, useParams, useSearchParams } from "react-router-dom";

import { governmentService } from "@/services/government.service";
import type { AppointmentStatus, PublicAppointmentRecord } from "@/types";

import {
  buildPublicAppointmentFilterHref,
  formatPublicDate,
  normalizePublishedSearch,
  normalizePublishedStatus,
  publicStatusLabel,
} from "./publicTransparencyHelpers";

export const PublicAppointmentDetailPage: React.FC = () => {
  const { appointmentId } = useParams<{ appointmentId: string }>();
  const [searchParams] = useSearchParams();
  const [record, setRecord] = useState<PublicAppointmentRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const publicSearch = normalizePublishedSearch(searchParams.get("search"));
  const publicStatus = normalizePublishedStatus(searchParams.get("status")) as "all" | AppointmentStatus;
  const hasPublicFilters = publicSearch.length > 0 || publicStatus !== "all";
  const transparencyHref = buildPublicAppointmentFilterHref("/transparency", {
    search: publicSearch,
    status: publicStatus,
    hash: "published-appointments",
  });
  const gazetteHref = buildPublicAppointmentFilterHref("/gazette", {
    search: publicSearch,
    status: publicStatus,
  });

  const loadDetail = useCallback(async () => {
    if (!appointmentId) {
      setError("Missing published appointment identifier.");
      setRecord(null);
      return;
    }
    setError(null);
    try {
      const detail = await governmentService.getPublicTransparencyAppointmentDetail(appointmentId);
      setRecord(detail);
    } catch (err) {
      setRecord(null);
      setError(err instanceof Error ? err.message : "Unable to load published appointment detail.");
    }
  }, [appointmentId]);

  useEffect(() => {
    const run = async () => {
      setLoading(true);
      await loadDetail();
      setLoading(false);
    };
    void run();
  }, [loadDetail]);

  const handleRefresh = async () => {
    setRefreshing(true);
    await loadDetail();
    setRefreshing(false);
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-3 px-4 py-4 sm:px-6 lg:px-8">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-cyan-700">Published Appointment</p>
            <h1 className="text-2xl font-bold text-slate-900">Public Appointment Detail</h1>
            <p className="text-sm text-slate-700">
              This page shows published appointment information only. Internal vetting evidence and review notes remain private.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Link
              to={transparencyHref}
              className="inline-flex items-center gap-2 rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-800 hover:bg-slate-100"
            >
              <ArrowLeft className="h-4 w-4" />
              Transparency Portal
            </Link>
            <Link
              to={gazetteHref}
              className="inline-flex rounded-md border border-cyan-200 bg-cyan-50 px-3 py-2 text-sm font-medium text-cyan-800 hover:bg-cyan-100"
            >
              Gazette Feed
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

      <main className="mx-auto max-w-5xl px-4 py-8 sm:px-6 lg:px-8">
        {loading ? (
          <div className="rounded-xl border border-slate-200 bg-white p-6 text-sm text-slate-700">
            Loading published appointment detail...
          </div>
        ) : error ? (
          <div className="rounded-xl border border-rose-200 bg-rose-50 p-6">
            <p className="text-sm text-rose-800">{error}</p>
            <div className="mt-3 flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => void handleRefresh()}
                disabled={refreshing}
                className="inline-flex items-center gap-2 rounded-md border border-rose-300 bg-white px-3 py-2 text-sm font-semibold text-rose-900 hover:bg-rose-100 disabled:cursor-not-allowed disabled:opacity-60"
              >
                <RefreshCw className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`} />
                {refreshing ? "Retrying..." : "Retry Detail Load"}
              </button>
              <Link
                to={transparencyHref}
                className="inline-flex rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-semibold text-slate-800 hover:bg-slate-100"
              >
                {hasPublicFilters ? "Back to Filtered Results" : "Back to Published Appointments"}
              </Link>
              <Link
                to={gazetteHref}
                className="inline-flex rounded-md bg-cyan-700 px-3 py-2 text-sm font-semibold text-white hover:bg-cyan-800"
              >
                Open Gazette Feed
              </Link>
            </div>
          </div>
        ) : !record ? (
          <div className="rounded-xl border border-slate-200 bg-white p-6 text-sm text-slate-700">
            No published appointment detail is available.
          </div>
        ) : (
          <div className="space-y-6">
            <section className="rounded-xl border border-cyan-200 bg-cyan-50 p-4 shadow-sm">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold text-cyan-900">
                    {hasPublicFilters ? "Keep browsing with the same public filters." : "Return to the published appointments register."}
                  </p>
                  <p className="mt-1 text-sm text-cyan-800">
                    {hasPublicFilters
                      ? "Go back to the filtered published appointments list without losing your current public search context."
                      : "Go back to the published appointments section and continue browsing public records."}
                  </p>
                </div>
                <Link
                  to={transparencyHref}
                  className="inline-flex items-center gap-2 rounded-md bg-cyan-700 px-3 py-2 text-sm font-semibold text-white hover:bg-cyan-800"
                >
                  <ArrowLeft className="h-4 w-4" />
                  {hasPublicFilters ? "Back to Filtered Results" : "Back to Published Appointments"}
                </Link>
              </div>
            </section>

            <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-cyan-700">Published Office Record</p>
                  <h2 className="mt-1 text-3xl font-black text-slate-900">{record.position_title}</h2>
                  <p className="mt-2 text-sm text-slate-700">{record.institution}</p>
                </div>
                <span className="rounded bg-cyan-100 px-3 py-1 text-xs font-semibold text-cyan-800">
                  {publicStatusLabel(record.status)}
                </span>
              </div>
              <div className="mt-6 grid gap-4 md:grid-cols-2">
                <article className="rounded-lg border border-slate-200 bg-slate-50 p-4">
                  <div className="mb-3 inline-flex rounded-md bg-indigo-100 p-2 text-indigo-700">
                    <ShieldCheck className="h-4 w-4" />
                  </div>
                  <h3 className="font-semibold text-slate-900">Nominee</h3>
                  <p className="mt-2 text-sm text-slate-700">{record.nominee_name}</p>
                  <p className="mt-1 text-sm text-slate-700">
                    <span className="font-semibold text-slate-900">Nominated by:</span> {record.nominated_by_display}
                  </p>
                  <p className="mt-1 text-sm text-slate-700">
                    <span className="font-semibold text-slate-900">Organization:</span> {record.nominated_by_org || "Not specified"}
                  </p>
                </article>
                <article className="rounded-lg border border-slate-200 bg-slate-50 p-4">
                  <div className="mb-3 inline-flex rounded-md bg-cyan-100 p-2 text-cyan-700">
                    <FileText className="h-4 w-4" />
                  </div>
                  <h3 className="font-semibold text-slate-900">Publication</h3>
                  <p className="mt-2 text-sm text-slate-700">
                    <span className="font-semibold text-slate-900">Publication reference:</span> {record.publication_reference || "Not provided"}
                  </p>
                  <p className="mt-1 text-sm text-slate-700">
                    <span className="font-semibold text-slate-900">Gazette number:</span> {record.gazette_number || "Pending"}
                  </p>
                  <p className="mt-1 text-sm text-slate-700">
                    <span className="font-semibold text-slate-900">Published at:</span> {formatPublicDate(record.published_at)}
                  </p>
                </article>
              </div>
            </section>

            <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
              <h3 className="text-lg font-bold text-slate-900">Timeline</h3>
              <div className="mt-4 grid gap-4 md:grid-cols-2">
                <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-700">Nomination date</p>
                  <p className="mt-2 text-sm text-slate-900">{formatPublicDate(record.nomination_date || null)}</p>
                </div>
                <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-700">Appointment date</p>
                  <p className="mt-2 text-sm text-slate-900">{formatPublicDate(record.appointment_date)}</p>
                </div>
                <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-700">Gazette date</p>
                  <p className="mt-2 text-sm text-slate-900">{formatPublicDate(record.gazette_date)}</p>
                </div>
                <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-700">Publication status</p>
                  <p className="mt-2 text-sm text-slate-900">{record.publication_status}</p>
                </div>
              </div>
            </section>
          </div>
        )}
      </main>
    </div>
  );
};

export default PublicAppointmentDetailPage;
