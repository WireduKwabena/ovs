import React, { useCallback, useEffect, useMemo, useState } from "react";
import { ArrowLeft, BriefcaseBusiness, FileText, RefreshCw, ShieldCheck, UserRoundCheck } from "lucide-react";
import { Link, useLocation, useSearchParams } from "react-router-dom";

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
  const location = useLocation();
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
  const [showAllOpen, setShowAllOpen] = useState(false);
  const [showAllVacant, setShowAllVacant] = useState(false);
  const [showAllOfficeholders, setShowAllOfficeholders] = useState(false);
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

  // Scroll to hash anchor after data finishes loading
  useEffect(() => {
    if (loading) return;
    const hash = location.hash.replace(/^#/, "");
    if (!hash) return;
    const id = window.setTimeout(() => {
      document.getElementById(hash)?.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 80);
    return () => window.clearTimeout(id);
  }, [loading, location.hash]);

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
    <div className="min-h-screen bg-background text-foreground">
      <header className="border-b border-border bg-background">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-4 sm:px-6 lg:px-8">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-primary">Public Transparency</p>
            <h1 className="text-2xl font-bold text-foreground">Government Appointment Transparency Portal</h1>
            <p className="text-sm text-muted-foreground">
              Published and public appointment data only. Internal vetting notes, case evidence, and review-only records are excluded.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Link
              to="/"
              className="inline-flex items-center gap-2 rounded-md border border-border bg-transparent px-3 py-2 text-sm font-medium text-foreground hover:bg-accent"
            >
              <ArrowLeft className="h-4 w-4" />
              Home
            </Link>
            <Link
              to={gazetteHref}
              className="inline-flex rounded-md border border-primary/30 bg-primary/10 px-3 py-2 text-sm font-medium text-primary hover:bg-primary/20"
            >
              Gazette Feed
            </Link>
            <button
              type="button"
              onClick={() => void handleRefresh()}
              disabled={refreshing}
              className="inline-flex items-center gap-2 rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
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
                  className="inline-flex rounded-md border border-amber-300 bg-white px-3 py-2 text-sm font-semibold text-amber-900 hover:bg-amber-100"
                >
                  Clear Published Filters
                </button>
              ) : null}
              <Link
                to={gazetteHref}
                className="inline-flex rounded-md bg-primary px-3 py-2 text-sm font-semibold text-primary-foreground hover:opacity-90"
              >
                Browse Gazette Feed
              </Link>
            </div>
          </div>
        ) : null}

        <section className="mb-6 grid gap-4 md:grid-cols-2 xl:grid-cols-5">
          <article className="rounded-xl border border-border bg-card p-4">
            <p className="text-sm text-muted-foreground">Published Appointments</p>
            <p className="mt-2 text-2xl font-black text-foreground">{stats.published_appointments}</p>
          </article>
          <article className="rounded-xl border border-border bg-card p-4">
            <p className="text-sm text-muted-foreground">Open Public Appointments</p>
            <p className="mt-2 text-2xl font-black text-primary">{stats.open_public_appointments}</p>
          </article>
          <article className="rounded-xl border border-border bg-card p-4">
            <p className="text-sm text-muted-foreground">Public Positions</p>
            <p className="mt-2 text-2xl font-black text-indigo-500">{stats.public_positions}</p>
          </article>
          <article className="rounded-xl border border-border bg-card p-4">
            <p className="text-sm text-muted-foreground">Vacant Public Positions</p>
            <p className="mt-2 text-2xl font-black text-emerald-500">{stats.vacant_public_positions}</p>
          </article>
          <article className="rounded-xl border border-border bg-card p-4">
            <p className="text-sm text-muted-foreground">Active Public Officeholders</p>
            <p className="mt-2 text-2xl font-black text-foreground">{stats.active_public_officeholders}</p>
            <p className="mt-2 text-xs text-muted-foreground">
              Last publication: {formatPublicDate(stats.last_published_at)}
            </p>
          </article>
        </section>

        {loading ? (
          <div className="rounded-xl border border-border bg-card p-6 text-sm text-muted-foreground">
            Loading transparency portal...
          </div>
        ) : (
          <div className="grid gap-6">
            <section id="published-appointments" className="rounded-xl border border-border bg-card p-5 shadow-sm">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h2 className="text-lg font-bold text-foreground">Recently Published Appointments</h2>
                  <p className="text-sm text-muted-foreground">Published outcomes that are safe for public viewing.</p>
                </div>
                <Link
                  to={gazetteHref}
                  className="inline-flex rounded-md border border-border px-3 py-2 text-sm font-semibold text-foreground hover:bg-accent"
                >
                  View Full Gazette
                </Link>
              </div>
              <form onSubmit={handleApplyFilters} className="mt-4 rounded-lg border border-border bg-muted/50 p-4">
                <div className="grid gap-3 md:grid-cols-[minmax(0,2fr)_minmax(0,1fr)_auto_auto]">
                  <label className="text-sm text-foreground">
                    <span className="mb-1 block text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                      Search published appointments
                    </span>
                    <input
                      type="text"
                      value={searchDraft}
                      onChange={(event) => setSearchDraft(event.target.value)}
                      placeholder="Search office, institution, nominee, or publication reference"
                      className="h-10 w-full rounded-md border border-border bg-input px-3 text-sm text-foreground outline-none transition focus:border-ring focus:ring-2 focus:ring-ring/20"
                    />
                  </label>
                  <label className="text-sm text-foreground">
                    <span className="mb-1 block text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                      Status
                    </span>
                    <select
                      value={statusDraft}
                      onChange={(event) => setStatusDraft(event.target.value as "all" | AppointmentStatus)}
                      className="h-10 w-full rounded-md border border-border bg-input px-3 text-sm text-foreground outline-none transition focus:border-ring focus:ring-2 focus:ring-ring/20"
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
                    className="h-10 rounded-md bg-primary px-4 text-sm font-semibold text-primary-foreground transition hover:opacity-90"
                  >
                    Apply Filters
                  </button>
                  <button
                    type="button"
                    onClick={handleClearFilters}
                    className="h-10 rounded-md border border-border bg-transparent px-4 text-sm font-semibold text-foreground transition hover:bg-accent"
                  >
                    Clear
                  </button>
                </div>
                <p className="mt-3 text-xs text-muted-foreground">
                  Use this section to search the published appointment register without exposing internal vetting materials.
                </p>
              </form>
              {hasPublishedFilters ? (
                <p className="mt-4 text-sm text-muted-foreground">
                  Showing published appointments
                  {appliedSearch.trim() ? ` matching "${appliedSearch.trim()}"` : ""}
                  {appliedStatus !== "all" ? ` with status ${publicStatusLabel(appliedStatus)}` : ""}
                  .
                </p>
              ) : null}
              {portalState.publishedAppointments.length === 0 ? (
                <div className="mt-4 rounded-lg border border-border bg-muted/50 p-4">
                  <p className="text-sm text-muted-foreground">
                    {hasPublishedFilters
                      ? "No published appointments match the current filters."
                      : "No published appointments are available yet."}
                  </p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {hasPublishedFilters ? (
                      <button
                        type="button"
                        onClick={handleClearFilters}
                        className="inline-flex rounded-md border border-border bg-transparent px-3 py-2 text-sm font-semibold text-foreground hover:bg-accent"
                      >
                        Clear Published Filters
                      </button>
                    ) : null}
                    <Link
                      to={gazetteHref}
                      className="inline-flex rounded-md bg-primary px-3 py-2 text-sm font-semibold text-primary-foreground hover:opacity-90"
                    >
                      {hasPublishedFilters ? "Check Gazette Feed Instead" : "Browse Gazette Feed"}
                    </Link>
                  </div>
                </div>
              ) : (
                <div className="mt-4 grid gap-4 md:grid-cols-2">
                  {portalState.publishedAppointments.slice(0, PREVIEW_LIMIT).map((record) => (
                    <article key={record.id} className="rounded-lg border border-border bg-muted/50 p-4">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <h3 className="font-semibold text-foreground">{record.position_title}</h3>
                          <p className="text-sm text-muted-foreground">{record.institution}</p>
                        </div>
                        <span className="rounded bg-cyan-100 px-2 py-1 text-xs font-semibold text-cyan-800">
                          {publicStatusLabel(record.status)}
                        </span>
                      </div>
                      <div className="mt-3 space-y-1 text-sm text-muted-foreground">
                        <p><span className="font-semibold text-foreground">Nominee:</span> {record.nominee_name}</p>
                        <p><span className="font-semibold text-foreground">Published:</span> {formatPublicDate(record.published_at)}</p>
                        <p><span className="font-semibold text-foreground">Reference:</span> {record.publication_reference || "Not provided"}</p>
                      </div>
                      <Link
                        to={buildPublicAppointmentFilterHref(`/transparency/appointments/${record.id}`, {
                          search: appliedSearch,
                          status: appliedStatus,
                        })}
                        className="mt-4 inline-flex rounded-md bg-primary px-3 py-2 text-sm font-semibold text-primary-foreground hover:opacity-90"
                      >
                        Open Published Detail
                      </Link>
                    </article>
                  ))}
                </div>
              )}
            </section>

            <section className="grid gap-6 xl:grid-cols-2">
              <article className="rounded-xl border border-border bg-card p-5 shadow-sm">
                <div className="mb-4 flex items-center gap-2">
                  <FileText className="h-4 w-4 text-primary" />
                  <h2 className="text-lg font-bold text-foreground">Open Public Appointments</h2>
                </div>
                {portalState.openAppointments.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No open public appointments are listed right now.</p>
                ) : (
                  <>
                    <div className="space-y-3">
                      {portalState.openAppointments.slice(0, showAllOpen ? undefined : PREVIEW_LIMIT).map((record) => (
                        <div key={record.id} className="rounded-lg border border-border bg-muted/50 p-4">
                          <div className="flex items-start justify-between gap-2">
                            <div>
                              <h3 className="font-semibold text-foreground">{record.position_title}</h3>
                              <p className="text-sm text-muted-foreground">{record.institution}</p>
                            </div>
                            <span className="rounded bg-indigo-100 px-2 py-1 text-xs font-semibold text-indigo-800">
                              {publicStatusLabel(record.status)}
                            </span>
                          </div>
                          <p className="mt-3 text-sm text-muted-foreground">
                            <span className="font-semibold text-foreground">Nominee:</span> {record.nominee_name}
                          </p>
                          <p className="mt-1 text-sm text-muted-foreground">
                            <span className="font-semibold text-foreground">Nomination date:</span> {formatPublicDate(record.nomination_date || null)}
                          </p>
                        </div>
                      ))}
                    </div>
                    {portalState.openAppointments.length > PREVIEW_LIMIT && (
                      <button
                        type="button"
                        onClick={() => setShowAllOpen((v) => !v)}
                        className="mt-3 text-sm font-semibold text-primary hover:underline"
                      >
                        {showAllOpen
                          ? "Show less"
                          : `Show all ${portalState.openAppointments.length} open appointments`}
                      </button>
                    )}
                  </>
                )}
              </article>

              <article className="rounded-xl border border-border bg-card p-5 shadow-sm">
                <div className="mb-4 flex items-center gap-2">
                  <BriefcaseBusiness className="h-4 w-4 text-emerald-600" />
                  <h2 className="text-lg font-bold text-foreground">Vacant Public Offices</h2>
                </div>
                {portalState.vacantPositions.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No vacant public offices are listed right now.</p>
                ) : (
                  <>
                    <div className="space-y-3">
                      {portalState.vacantPositions.slice(0, showAllVacant ? undefined : PREVIEW_LIMIT).map((position) => (
                        <div key={position.id} className="rounded-lg border border-border bg-muted/50 p-4">
                          <div className="flex items-start justify-between gap-2">
                            <div>
                              <h3 className="font-semibold text-foreground">{position.title}</h3>
                              <p className="text-sm text-muted-foreground">{position.institution}</p>
                            </div>
                            <span className="rounded bg-emerald-100 px-2 py-1 text-xs font-semibold text-emerald-800">
                              {position.branch}
                            </span>
                          </div>
                          <p className="mt-3 text-sm text-muted-foreground">
                            <span className="font-semibold text-foreground">Authority:</span> {position.appointment_authority}
                          </p>
                          <p className="mt-1 text-sm text-muted-foreground">
                            <span className="font-semibold text-foreground">Confirmation:</span>{" "}
                            {position.confirmation_required ? "Required" : "Not required"}
                          </p>
                        </div>
                      ))}
                    </div>
                    {portalState.vacantPositions.length > PREVIEW_LIMIT && (
                      <button
                        type="button"
                        onClick={() => setShowAllVacant((v) => !v)}
                        className="mt-3 text-sm font-semibold text-primary hover:underline"
                      >
                        {showAllVacant
                          ? "Show less"
                          : `Show all ${portalState.vacantPositions.length} vacant offices`}
                      </button>
                    )}
                  </>
                )}
              </article>
            </section>

            <section className="rounded-xl border border-border bg-card p-5 shadow-sm">
              <div className="mb-4 flex items-center gap-2">
                <UserRoundCheck className="h-4 w-4 text-indigo-500" />
                <h2 className="text-lg font-bold text-foreground">Active Public Officeholders</h2>
              </div>
              {portalState.officeholders.length === 0 ? (
                <p className="text-sm text-muted-foreground">No public officeholder profiles are available yet.</p>
              ) : (
                <>
                  <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                    {portalState.officeholders.slice(0, showAllOfficeholders ? undefined : PREVIEW_LIMIT).map((officeholder) => (
                      <article key={officeholder.id} className="rounded-lg border border-border bg-muted/50 p-4">
                        <div className="mb-3 inline-flex rounded-md bg-indigo-100 p-2 text-indigo-700">
                          <ShieldCheck className="h-4 w-4" />
                        </div>
                        <h3 className="font-semibold text-foreground">{officeholder.full_name}</h3>
                        <p className="mt-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                          {officeholder.is_active_officeholder ? "Active Officeholder" : "Former Officeholder"}
                        </p>
                        <p className="mt-3 text-sm text-muted-foreground">
                          {officeholder.bio_summary || "No public biography has been published yet."}
                        </p>
                      </article>
                    ))}
                  </div>
                  {portalState.officeholders.length > PREVIEW_LIMIT && (
                    <button
                      type="button"
                      onClick={() => setShowAllOfficeholders((v) => !v)}
                      className="mt-4 text-sm font-semibold text-primary hover:underline"
                    >
                      {showAllOfficeholders
                        ? "Show less"
                        : `Show all ${portalState.officeholders.length} officeholders`}
                    </button>
                  )}
                </>
              )}
            </section>
          </div>
        )}
      </main>
    </div>
  );
};

export default PublicTransparencyPage;
