import React, { useCallback, useEffect, useMemo, useState } from "react";
import { ArrowLeft, BriefcaseBusiness, FileText, RefreshCw, ShieldCheck, UserRoundCheck } from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";

import { governmentService } from "@/services/government.service";
import type {
  AppointmentStatus,
  PublicAppointmentRecord,
  PublicTransparencyOfficeholder,
  PublicTransparencyPosition,
  PublicTransparencySummary,
} from "@/types";

import {
  PUBLIC_APPOINTMENT_STATUS_OPTIONS,
  buildPublicAppointmentFilterHref,
  formatPublicDate,
  normalizePublishedSearch,
  normalizePublishedStatus,
  publicStatusLabel,
} from "./publicTransparencyHelpers";

const PREVIEW_LIMIT = 4;

type PortalState = {
  summary: PublicTransparencySummary | null;
  publishedAppointments: PublicAppointmentRecord[];
  openAppointments: PublicAppointmentRecord[];
  vacantPositions: PublicTransparencyPosition[];
  officeholders: PublicTransparencyOfficeholder[];
};

const defaultPortalState: PortalState = {
  summary: null,
  publishedAppointments: [],
  openAppointments: [],
  vacantPositions: [],
  officeholders: [],
};

export const PublicTransparencyPage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const querySearch = useMemo(() => normalizePublishedSearch(searchParams.get("search")), [searchParams]);
  const queryStatus = useMemo(() => normalizePublishedStatus(searchParams.get("status")), [searchParams]);
  const [portalState, setPortalState] = useState<PortalState>(defaultPortalState);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchDraft, setSearchDraft] = useState(() => querySearch);
  const [statusDraft, setStatusDraft] = useState<"all" | AppointmentStatus>(() => queryStatus);
  const [appliedSearch, setAppliedSearch] = useState(() => querySearch);
  const [appliedStatus, setAppliedStatus] = useState<"all" | AppointmentStatus>(() => queryStatus);
  const gazetteHref = useMemo(
    () =>
      buildPublicAppointmentFilterHref("/gazette", {
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

  const loadPortal = useCallback(async () => {
    const normalizedSearch = appliedSearch.trim();
    const results = await Promise.allSettled([
      governmentService.getPublicTransparencySummary(),
      governmentService.listPublicTransparencyAppointments({
        ordering: "-published_at",
        search: normalizedSearch || undefined,
        status: appliedStatus === "all" ? undefined : appliedStatus,
      }),
      governmentService.listPublicTransparencyOpenAppointments({ ordering: "-nomination_date" }),
      governmentService.listPublicTransparencyVacantPositions(),
      governmentService.listPublicTransparencyOfficeholders(),
    ]);

    const [summaryResult, publishedResult, openResult, vacantResult, officeholderResult] = results;
    const unavailable: string[] = [];

    const nextState: PortalState = {
      summary: summaryResult.status === "fulfilled" ? summaryResult.value : null,
      publishedAppointments: publishedResult.status === "fulfilled" ? publishedResult.value : [],
      openAppointments: openResult.status === "fulfilled" ? openResult.value : [],
      vacantPositions: vacantResult.status === "fulfilled" ? vacantResult.value : [],
      officeholders: officeholderResult.status === "fulfilled" ? officeholderResult.value : [],
    };

    if (summaryResult.status === "rejected") unavailable.push("summary");
    if (publishedResult.status === "rejected") unavailable.push("published appointments");
    if (openResult.status === "rejected") unavailable.push("open appointments");
    if (vacantResult.status === "rejected") unavailable.push("vacant positions");
    if (officeholderResult.status === "rejected") unavailable.push("officeholders");

    setPortalState(nextState);
    setError(
      unavailable.length > 0
        ? `Some public transparency sections are temporarily unavailable: ${unavailable.join(", ")}.`
        : null,
    );
  }, [appliedSearch, appliedStatus]);

  useEffect(() => {
    const run = async () => {
      setLoading(true);
      await loadPortal();
      setLoading(false);
    };
    void run();
  }, [loadPortal]);

  const handleRefresh = async () => {
    setRefreshing(true);
    await loadPortal();
    setRefreshing(false);
  };

  const hasPublishedFilters = appliedSearch.trim().length > 0 || appliedStatus !== "all";

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

  const stats = useMemo(() => {
    if (portalState.summary) {
      return portalState.summary;
    }
    return {
      published_appointments: portalState.publishedAppointments.length,
      open_public_appointments: portalState.openAppointments.length,
      public_positions: 0,
      vacant_public_positions: portalState.vacantPositions.length,
      active_public_officeholders: portalState.officeholders.length,
      last_published_at:
        portalState.publishedAppointments.find((item) => Boolean(item.published_at))?.published_at || null,
    };
  }, [portalState]);

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-4 sm:px-6 lg:px-8">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-cyan-700">Public Transparency</p>
            <h1 className="text-2xl font-bold text-slate-900">Government Appointment Transparency Portal</h1>
            <p className="text-sm text-slate-700">
              Published and public appointment data only. Internal vetting notes, case evidence, and review-only records are excluded.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Link
              to="/"
              className="inline-flex items-center gap-2 rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-800 hover:bg-slate-100"
            >
              <ArrowLeft className="h-4 w-4" />
              Home
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

      <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        {error ? (
          <div className="mb-6 rounded-xl border border-amber-300 bg-amber-50 p-4">
            <p className="text-sm text-amber-900">{error}</p>
            <div className="mt-3 flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => void handleRefresh()}
                disabled={refreshing}
                className="inline-flex items-center gap-2 rounded-md border border-amber-300 bg-white px-3 py-2 text-sm font-semibold text-amber-900 hover:bg-amber-100 disabled:cursor-not-allowed disabled:opacity-60"
              >
                <RefreshCw className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`} />
                {refreshing ? "Retrying..." : "Retry Transparency Load"}
              </button>
              {hasPublishedFilters ? (
                <button
                  type="button"
                  onClick={handleClearFilters}
                  className="inline-flex rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-semibold text-slate-800 hover:bg-slate-100"
                >
                  Clear Published Filters
                </button>
              ) : null}
              <Link
                to={gazetteHref}
                className="inline-flex rounded-md bg-cyan-700 px-3 py-2 text-sm font-semibold text-white hover:bg-cyan-800"
              >
                Browse Gazette Feed
              </Link>
            </div>
          </div>
        ) : null}

        <section className="mb-6 grid gap-4 md:grid-cols-2 xl:grid-cols-5">
          <article className="rounded-xl border border-slate-200 bg-white p-4">
            <p className="text-sm text-slate-700">Published Appointments</p>
            <p className="mt-2 text-2xl font-black text-slate-900">{stats.published_appointments}</p>
          </article>
          <article className="rounded-xl border border-slate-200 bg-white p-4">
            <p className="text-sm text-slate-700">Open Public Appointments</p>
            <p className="mt-2 text-2xl font-black text-cyan-700">{stats.open_public_appointments}</p>
          </article>
          <article className="rounded-xl border border-slate-200 bg-white p-4">
            <p className="text-sm text-slate-700">Public Positions</p>
            <p className="mt-2 text-2xl font-black text-indigo-700">{stats.public_positions}</p>
          </article>
          <article className="rounded-xl border border-slate-200 bg-white p-4">
            <p className="text-sm text-slate-700">Vacant Public Positions</p>
            <p className="mt-2 text-2xl font-black text-emerald-700">{stats.vacant_public_positions}</p>
          </article>
          <article className="rounded-xl border border-slate-200 bg-white p-4">
            <p className="text-sm text-slate-700">Active Public Officeholders</p>
            <p className="mt-2 text-2xl font-black text-slate-900">{stats.active_public_officeholders}</p>
            <p className="mt-2 text-xs text-slate-700">
              Last publication: {formatPublicDate(stats.last_published_at)}
            </p>
          </article>
        </section>

        {loading ? (
          <div className="rounded-xl border border-slate-200 bg-white p-6 text-sm text-slate-700">
            Loading transparency portal...
          </div>
        ) : (
          <div className="grid gap-6">
            <section id="published-appointments" className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h2 className="text-lg font-bold text-slate-900">Recently Published Appointments</h2>
                  <p className="text-sm text-slate-700">Published outcomes that are safe for public viewing.</p>
                </div>
                <Link
                  to={gazetteHref}
                  className="inline-flex rounded-md border border-slate-300 px-3 py-2 text-sm font-semibold text-slate-800 hover:bg-slate-100"
                >
                  View Full Gazette
                </Link>
              </div>
              <form onSubmit={handleApplyFilters} className="mt-4 rounded-lg border border-slate-200 bg-slate-50 p-4">
                <div className="grid gap-3 md:grid-cols-[minmax(0,2fr)_minmax(0,1fr)_auto_auto]">
                  <label className="text-sm text-slate-800">
                    <span className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-700">
                      Search published appointments
                    </span>
                    <input
                      type="text"
                      value={searchDraft}
                      onChange={(event) => setSearchDraft(event.target.value)}
                      placeholder="Search office, institution, nominee, or publication reference"
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
                  Use this section to search the published appointment register without exposing internal vetting materials.
                </p>
              </form>
              {hasPublishedFilters ? (
                <p className="mt-4 text-sm text-slate-700">
                  Showing published appointments
                  {appliedSearch.trim() ? ` matching "${appliedSearch.trim()}"` : ""}
                  {appliedStatus !== "all" ? ` with status ${publicStatusLabel(appliedStatus)}` : ""}
                  .
                </p>
              ) : null}
              {portalState.publishedAppointments.length === 0 ? (
                <div className="mt-4 rounded-lg border border-slate-200 bg-slate-50 p-4">
                  <p className="text-sm text-slate-700">
                    {hasPublishedFilters
                      ? "No published appointments match the current filters."
                      : "No published appointments are available yet."}
                  </p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {hasPublishedFilters ? (
                      <button
                        type="button"
                        onClick={handleClearFilters}
                        className="inline-flex rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-semibold text-slate-800 hover:bg-slate-100"
                      >
                        Clear Published Filters
                      </button>
                    ) : null}
                    <Link
                      to={gazetteHref}
                      className="inline-flex rounded-md bg-cyan-700 px-3 py-2 text-sm font-semibold text-white hover:bg-cyan-800"
                    >
                      {hasPublishedFilters ? "Check Gazette Feed Instead" : "Browse Gazette Feed"}
                    </Link>
                  </div>
                </div>
              ) : (
                <div className="mt-4 grid gap-4 md:grid-cols-2">
                  {portalState.publishedAppointments.slice(0, PREVIEW_LIMIT).map((record) => (
                    <article key={record.id} className="rounded-lg border border-slate-200 bg-slate-50 p-4">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <h3 className="font-semibold text-slate-900">{record.position_title}</h3>
                          <p className="text-sm text-slate-700">{record.institution}</p>
                        </div>
                        <span className="rounded bg-cyan-100 px-2 py-1 text-xs font-semibold text-cyan-800">
                          {publicStatusLabel(record.status)}
                        </span>
                      </div>
                      <div className="mt-3 space-y-1 text-sm text-slate-700">
                        <p><span className="font-semibold text-slate-900">Nominee:</span> {record.nominee_name}</p>
                        <p><span className="font-semibold text-slate-900">Published:</span> {formatPublicDate(record.published_at)}</p>
                        <p><span className="font-semibold text-slate-900">Reference:</span> {record.publication_reference || "Not provided"}</p>
                      </div>
                      <Link
                        to={buildPublicAppointmentFilterHref(`/transparency/appointments/${record.id}`, {
                          search: appliedSearch,
                          status: appliedStatus,
                        })}
                        className="mt-4 inline-flex rounded-md bg-cyan-700 px-3 py-2 text-sm font-semibold text-white hover:bg-cyan-800"
                      >
                        Open Published Detail
                      </Link>
                    </article>
                  ))}
                </div>
              )}
            </section>

            <section className="grid gap-6 xl:grid-cols-2">
              <article className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
                <div className="mb-4 flex items-center gap-2">
                  <FileText className="h-4 w-4 text-cyan-700" />
                  <h2 className="text-lg font-bold text-slate-900">Open Public Appointments</h2>
                </div>
                {portalState.openAppointments.length === 0 ? (
                  <p className="text-sm text-slate-700">No open public appointments are listed right now.</p>
                ) : (
                  <div className="space-y-3">
                    {portalState.openAppointments.slice(0, PREVIEW_LIMIT).map((record) => (
                      <div key={record.id} className="rounded-lg border border-slate-200 bg-slate-50 p-4">
                        <div className="flex items-start justify-between gap-2">
                          <div>
                            <h3 className="font-semibold text-slate-900">{record.position_title}</h3>
                            <p className="text-sm text-slate-700">{record.institution}</p>
                          </div>
                          <span className="rounded bg-indigo-100 px-2 py-1 text-xs font-semibold text-indigo-800">
                            {publicStatusLabel(record.status)}
                          </span>
                        </div>
                        <p className="mt-3 text-sm text-slate-700">
                          <span className="font-semibold text-slate-900">Nominee:</span> {record.nominee_name}
                        </p>
                        <p className="mt-1 text-sm text-slate-700">
                          <span className="font-semibold text-slate-900">Nomination date:</span> {formatPublicDate(record.nomination_date || null)}
                        </p>
                      </div>
                    ))}
                  </div>
                )}
              </article>

              <article className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
                <div className="mb-4 flex items-center gap-2">
                  <BriefcaseBusiness className="h-4 w-4 text-emerald-700" />
                  <h2 className="text-lg font-bold text-slate-900">Vacant Public Offices</h2>
                </div>
                {portalState.vacantPositions.length === 0 ? (
                  <p className="text-sm text-slate-700">No vacant public offices are listed right now.</p>
                ) : (
                  <div className="space-y-3">
                    {portalState.vacantPositions.slice(0, PREVIEW_LIMIT).map((position) => (
                      <div key={position.id} className="rounded-lg border border-slate-200 bg-slate-50 p-4">
                        <div className="flex items-start justify-between gap-2">
                          <div>
                            <h3 className="font-semibold text-slate-900">{position.title}</h3>
                            <p className="text-sm text-slate-700">{position.institution}</p>
                          </div>
                          <span className="rounded bg-emerald-100 px-2 py-1 text-xs font-semibold text-emerald-800">
                            {position.branch}
                          </span>
                        </div>
                        <p className="mt-3 text-sm text-slate-700">
                          <span className="font-semibold text-slate-900">Authority:</span> {position.appointment_authority}
                        </p>
                        <p className="mt-1 text-sm text-slate-700">
                          <span className="font-semibold text-slate-900">Confirmation:</span>{" "}
                          {position.confirmation_required ? "Required" : "Not required"}
                        </p>
                      </div>
                    ))}
                  </div>
                )}
              </article>
            </section>

            <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <div className="mb-4 flex items-center gap-2">
                <UserRoundCheck className="h-4 w-4 text-indigo-700" />
                <h2 className="text-lg font-bold text-slate-900">Active Public Officeholders</h2>
              </div>
              {portalState.officeholders.length === 0 ? (
                <p className="text-sm text-slate-700">No public officeholder profiles are available yet.</p>
              ) : (
                <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                  {portalState.officeholders.slice(0, PREVIEW_LIMIT).map((officeholder) => (
                    <article key={officeholder.id} className="rounded-lg border border-slate-200 bg-slate-50 p-4">
                      <div className="mb-3 inline-flex rounded-md bg-indigo-100 p-2 text-indigo-700">
                        <ShieldCheck className="h-4 w-4" />
                      </div>
                      <h3 className="font-semibold text-slate-900">{officeholder.full_name}</h3>
                      <p className="mt-1 text-xs font-semibold uppercase tracking-wide text-slate-700">
                        {officeholder.gender || "Public profile"}
                      </p>
                      <p className="mt-3 text-sm text-slate-700">
                        {officeholder.bio_summary || "No public biography has been published yet."}
                      </p>
                    </article>
                  ))}
                </div>
              )}
            </section>
          </div>
        )}
      </main>
    </div>
  );
};

export default PublicTransparencyPage;
