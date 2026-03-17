import React, { useCallback, useEffect, useMemo, useState } from "react";
import { ArrowLeft, FileText, RefreshCw, Stamp } from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";

import { governmentService } from "@/services/government.service";
import type { AppointmentStatus, PublicAppointmentRecord } from "@/types";
import {
  PUBLIC_APPOINTMENT_STATUS_OPTIONS,
  buildPublicAppointmentFilterHref,
  formatPublicDate,
  normalizePublishedSearch,
  normalizePublishedStatus,
  publicStatusLabel,
} from "./publicTransparencyHelpers";

function filterLegacyGazetteRecords(
  records: PublicAppointmentRecord[],
  search: string,
  status: "all" | AppointmentStatus,
): PublicAppointmentRecord[] {
  const normalizedSearch = search.trim().toLowerCase();
  return records.filter((record) => {
    if (status !== "all" && record.status !== status) {
      return false;
    }
    if (!normalizedSearch) {
      return true;
    }
    const haystack = [
      record.position_title,
      record.institution,
      record.nominee_name,
      record.nominated_by_display,
      record.nominated_by_org,
      record.publication_reference,
      record.gazette_number,
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    return haystack.includes(normalizedSearch);
  });
}

export const PublicGazettePage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const querySearch = useMemo(() => normalizePublishedSearch(searchParams.get("search")), [searchParams]);
  const queryStatus = useMemo(() => normalizePublishedStatus(searchParams.get("status")), [searchParams]);
  const [records, setRecords] = useState<PublicAppointmentRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchDraft, setSearchDraft] = useState(() => querySearch);
  const [statusDraft, setStatusDraft] = useState<"all" | AppointmentStatus>(() => queryStatus);
  const [appliedSearch, setAppliedSearch] = useState(() => querySearch);
  const [appliedStatus, setAppliedStatus] = useState<"all" | AppointmentStatus>(() => queryStatus);
  const transparencyHref = useMemo(
    () =>
      buildPublicAppointmentFilterHref("/transparency", {
        search: appliedSearch,
        status: appliedStatus,
      }),
    [appliedSearch, appliedStatus],
  );

  useEffect(() => {
    setSearchDraft(querySearch);
    setStatusDraft(queryStatus);
    setAppliedSearch(querySearch);
    setAppliedStatus(queryStatus);
  }, [querySearch, queryStatus]);

  const loadFeed = useCallback(async () => {
    setError(null);
    try {
      const feed = await governmentService.listPublicTransparencyGazetteFeed({
        ordering: "-published_at",
        search: appliedSearch.trim() || undefined,
        status: appliedStatus === "all" ? undefined : appliedStatus,
      });
      setRecords(feed);
    } catch {
      try {
        const legacyFeed = await governmentService.listPublicGazetteFeed();
        setRecords(filterLegacyGazetteRecords(legacyFeed, appliedSearch, appliedStatus));
      } catch (legacyError) {
        setError(legacyError instanceof Error ? legacyError.message : "Unable to load gazette feed.");
      }
    }
  }, [appliedSearch, appliedStatus]);

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

  const hasFilters = appliedSearch.trim().length > 0 || appliedStatus !== "all";

  const handleApplyFilters = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const nextParams = new URLSearchParams(searchParams);
    const normalizedSearch = searchDraft.trim();
    if (normalizedSearch) {
      nextParams.set("search", normalizedSearch);
    } else {
      nextParams.delete("search");
    }
    if (statusDraft !== "all") {
      nextParams.set("status", statusDraft);
    } else {
      nextParams.delete("status");
    }
    setSearchParams(nextParams);
  };

  const handleClearFilters = () => {
    const nextParams = new URLSearchParams(searchParams);
    nextParams.delete("search");
    nextParams.delete("status");
    setSearchParams(nextParams);
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
            <Link
              to={transparencyHref}
              className="inline-flex rounded-md border border-cyan-200 bg-cyan-50 px-3 py-2 text-sm font-medium text-cyan-800 hover:bg-cyan-100"
            >
              Transparency Portal
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
        <form onSubmit={handleApplyFilters} className="mb-6 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <div className="grid gap-3 md:grid-cols-[minmax(0,2fr)_minmax(0,1fr)_auto_auto]">
            <label className="text-sm text-slate-800">
              <span className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-700">
                Search gazette feed
              </span>
              <input
                type="text"
                value={searchDraft}
                onChange={(event) => setSearchDraft(event.target.value)}
                placeholder="Search office, institution, nominee, reference, or gazette number"
                className="h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm text-slate-900 outline-none transition focus:border-cyan-400 focus:ring-2 focus:ring-cyan-100"
              />
            </label>
            <label className="text-sm text-slate-800">
              <span className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-700">
                Status
              </span>
              <select
                value={statusDraft}
                onChange={(event) => setStatusDraft(event.target.value as "all" | AppointmentStatus)}
                className="h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm text-slate-900 outline-none transition focus:border-cyan-400 focus:ring-2 focus:ring-cyan-100"
              >
                {PUBLIC_APPOINTMENT_STATUS_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
            <button
              type="submit"
              className="h-10 rounded-md bg-cyan-700 px-4 text-sm font-semibold text-white transition hover:bg-cyan-800"
            >
              Apply Filters
            </button>
            <button
              type="button"
              onClick={handleClearFilters}
              className="h-10 rounded-md border border-slate-300 bg-white px-4 text-sm font-semibold text-slate-800 transition hover:bg-slate-100"
            >
              Clear
            </button>
          </div>
          <p className="mt-3 text-xs text-slate-700">
            Use shareable filters to browse published gazette records without exposing internal vetting data.
          </p>
        </form>

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
                {refreshing ? "Retrying..." : "Retry Gazette Load"}
              </button>
              {hasFilters ? (
                <button
                  type="button"
                  onClick={handleClearFilters}
                  className="inline-flex rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-semibold text-slate-800 hover:bg-slate-100"
                >
                  Clear Gazette Filters
                </button>
              ) : null}
              <Link
                to={transparencyHref}
                className="inline-flex rounded-md bg-cyan-700 px-3 py-2 text-sm font-semibold text-white hover:bg-cyan-800"
              >
                Open Transparency Portal
              </Link>
            </div>
          </div>
        ) : records.length === 0 ? (
          <div className="rounded-xl border border-slate-200 bg-white p-6">
            <p className="text-sm text-slate-700">
              {hasFilters ? "No gazette records match the current filters." : "No published appointments are available yet."}
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              {hasFilters ? (
                <button
                  type="button"
                  onClick={handleClearFilters}
                  className="inline-flex rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-semibold text-slate-800 hover:bg-slate-100"
                >
                  Clear Gazette Filters
                </button>
              ) : null}
              <Link
                to={transparencyHref}
                className="inline-flex rounded-md bg-cyan-700 px-3 py-2 text-sm font-semibold text-white hover:bg-cyan-800"
              >
                {hasFilters ? "Switch to Transparency Portal" : "Open Transparency Portal"}
              </Link>
            </div>
          </div>
        ) : (
          <div className="grid gap-4">
            {hasFilters ? (
              <p className="text-sm text-slate-700">
                Showing gazette records
                {appliedSearch.trim() ? ` matching "${appliedSearch.trim()}"` : ""}
                {appliedStatus !== "all" ? ` with status ${publicStatusLabel(appliedStatus)}` : ""}
                .
              </p>
            ) : null}
            {records.map((record) => (
              <article key={record.id} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <h2 className="text-lg font-semibold text-slate-900">{record.position_title}</h2>
                    <p className="text-sm text-slate-700">{record.institution}</p>
                  </div>
                  <span className="rounded bg-cyan-100 px-2 py-1 text-xs font-semibold text-cyan-800">
                    {publicStatusLabel(record.status)}
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
                    {formatPublicDate(record.appointment_date)}
                  </p>
                  <p>
                    <span className="font-semibold text-slate-900">Gazette number:</span>{" "}
                    {record.gazette_number || "Pending"}
                  </p>
                  <p>
                    <span className="font-semibold text-slate-900">Gazette date:</span>{" "}
                    {formatPublicDate(record.gazette_date)}
                  </p>
                  <p className="md:col-span-2">
                    <span className="font-semibold text-slate-900">Publication reference:</span>{" "}
                    {record.publication_reference || "Not provided"}
                  </p>
                  <p className="md:col-span-2">
                    <span className="font-semibold text-slate-900">Published at:</span>{" "}
                    {formatPublicDate(record.published_at)}
                  </p>
                </div>
                <div className="mt-4">
                  <Link
                    to={buildPublicAppointmentFilterHref(`/transparency/appointments/${record.id}`, {
                      search: appliedSearch,
                      status: appliedStatus,
                    })}
                    className="inline-flex rounded-md bg-cyan-700 px-3 py-2 text-sm font-semibold text-white hover:bg-cyan-800"
                  >
                    Open Published Detail
                  </Link>
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
