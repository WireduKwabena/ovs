import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ClipboardCopy, Clock3, RefreshCw, Search, ShieldCheck } from "lucide-react";
import { toast } from "react-toastify";

import ExportActions from "@/components/common/ExportActions";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { backgroundCheckService } from "@/services/backgroundCheck.service";
import { applicationService } from "@/services/application.service";
import type {
  ApplicationWithDocuments,
  BackgroundCheck,
  BackgroundCheckEvent,
  BackgroundCheckStatus,
  BackgroundCheckType,
} from "@/types";
import { downloadCsvFile, isoDateStamp } from "@/utils/csv";
import { downloadJsonFile } from "@/utils/json";
import { formatDate } from "@/utils/helper";

type CheckTypeFilter = BackgroundCheckType | "all";
type CheckStatusFilter = BackgroundCheckStatus | "all";

const CHECK_TYPE_OPTIONS: Array<{ value: BackgroundCheckType; label: string }> = [
  { value: "criminal", label: "Criminal Records" },
  { value: "employment", label: "Employment History" },
  { value: "education", label: "Education Verification" },
  { value: "kyc_aml", label: "KYC/AML" },
  { value: "identity", label: "Identity Verification" },
];

const STATUS_OPTIONS: Array<{ value: CheckStatusFilter; label: string }> = [
  { value: "all", label: "All Statuses" },
  { value: "pending", label: "Pending" },
  { value: "submitted", label: "Submitted" },
  { value: "in_progress", label: "In Progress" },
  { value: "completed", label: "Completed" },
  { value: "manual_review", label: "Manual Review" },
  { value: "failed", label: "Failed" },
  { value: "cancelled", label: "Cancelled" },
];

const statusPillClass: Record<BackgroundCheckStatus, string> = {
  pending: "bg-slate-200 text-slate-800",
  submitted: "bg-indigo-100 text-indigo-700",
  in_progress: "bg-amber-100 text-amber-700",
  completed: "bg-emerald-100 text-emerald-700",
  manual_review: "bg-orange-100 text-orange-700",
  failed: "bg-rose-100 text-rose-700",
  cancelled: "bg-zinc-100 text-zinc-700",
};

const getApiBaseUrl = (): string => {
  const configured = ((import.meta as unknown as { env?: Record<string, string> }).env?.VITE_API_URL || "").trim();
  return configured || "http://localhost:8000/api";
};

const buildProviderWebhookUrl = (provider: string): string => {
  const base = getApiBaseUrl().replace(/\/+$/, "");
  const safeProvider = (provider || "mock").trim() || "mock";
  return `${base}/background-checks/providers/${safeProvider}/webhook/`;
};

const BackgroundChecksPage: React.FC = () => {
  const [checks, setChecks] = useState<BackgroundCheck[]>([]);
  const [cases, setCases] = useState<ApplicationWithDocuments[]>([]);
  const [eventsByCheck, setEventsByCheck] = useState<Record<string, BackgroundCheckEvent[]>>({});
  const [expandedCheckId, setExpandedCheckId] = useState<string | null>(null);

  const [loadingChecks, setLoadingChecks] = useState(true);
  const [refreshingList, setRefreshingList] = useState(false);
  const [loadingCases, setLoadingCases] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [refreshingId, setRefreshingId] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const [caseFilter, setCaseFilter] = useState<string>("all");
  const [checkTypeFilter, setCheckTypeFilter] = useState<CheckTypeFilter>("all");
  const [statusFilter, setStatusFilter] = useState<CheckStatusFilter>("all");

  const [selectedCase, setSelectedCase] = useState<string>("");
  const [selectedCheckType, setSelectedCheckType] = useState<BackgroundCheckType>("criminal");
  const [providerKey, setProviderKey] = useState("mock");
  const [runAsync, setRunAsync] = useState(true);
  const [consentNotes, setConsentNotes] = useState("");
  const [consentRecorded, setConsentRecorded] = useState(true);
  const [copyingWebhook, setCopyingWebhook] = useState(false);
  const [copyingHeader, setCopyingHeader] = useState(false);

  const caseOptions = useMemo(
    () =>
      cases.map((item) => ({
        id: String(item.id),
        case_id: item.case_id,
        status: item.status,
      })),
    [cases],
  );

  const loadChecks = useCallback(async () => {
    try {
      setErrorMessage(null);
      const data = await backgroundCheckService.list({
        case_id: caseFilter !== "all" ? caseFilter : undefined,
        check_type: checkTypeFilter,
        status: statusFilter,
      });
      setChecks(data);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to fetch background checks.";
      setErrorMessage(message);
    }
  }, [caseFilter, checkTypeFilter, statusFilter]);

  const loadCaseOptions = useCallback(async () => {
    try {
      setLoadingCases(true);
      const list = await applicationService.getAll();
      setCases(Array.isArray(list) ? list : []);
    } catch {
      setCases([]);
    } finally {
      setLoadingCases(false);
    }
  }, []);

  useEffect(() => {
    const run = async () => {
      setLoadingChecks(true);
      await Promise.all([loadChecks(), loadCaseOptions()]);
      setLoadingChecks(false);
    };

    void run();
  }, [loadChecks, loadCaseOptions]);

  const handleCreateCheck = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    if (!selectedCase) {
      toast.error("Select a case before creating a background check.");
      return;
    }

    if (!consentRecorded) {
      toast.error("Consent evidence is required for background checks.");
      return;
    }

    setSubmitting(true);
    try {
      const created = await backgroundCheckService.create({
        case: Number(selectedCase),
        check_type: selectedCheckType,
        provider_key: providerKey.trim() || "mock",
        request_payload: {},
        consent_evidence: {
          consent_recorded: true,
          recorded_at: new Date().toISOString(),
          notes: consentNotes.trim(),
        },
        run_async: runAsync,
      });

      setChecks((current) => [created, ...current]);
      setConsentNotes("");
      toast.success("Background check submitted successfully.");
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to create background check.";
      toast.error(message);
    } finally {
      setSubmitting(false);
    }
  };

  const handleRefreshCheck = async (checkId: string) => {
    setRefreshingId(checkId);
    try {
      const refreshed = await backgroundCheckService.refresh(checkId);
      setChecks((current) => current.map((item) => (item.id === checkId ? refreshed : item)));
      toast.success("Background check refreshed.");
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to refresh background check.";
      toast.error(message);
    } finally {
      setRefreshingId(null);
    }
  };

  const toggleEvents = async (checkId: string) => {
    if (expandedCheckId === checkId) {
      setExpandedCheckId(null);
      return;
    }

    setExpandedCheckId(checkId);
    if (!eventsByCheck[checkId]) {
      try {
        const events = await backgroundCheckService.getEvents(checkId);
        setEventsByCheck((current) => ({ ...current, [checkId]: events }));
      } catch (error) {
        const message = error instanceof Error ? error.message : "Failed to fetch check events.";
        toast.error(message);
      }
    }
  };

  const handleRefreshList = async () => {
    setRefreshingList(true);
    await loadChecks();
    setRefreshingList(false);
  };

  const exportChecksCsv = () => {
    if (checks.length === 0) {
      toast.info("No background check rows to export.");
      return;
    }

    const header = [
      "case_id",
      "check_type",
      "status",
      "provider_key",
      "risk_level",
      "recommendation",
      "score",
      "applicant_email",
      "external_reference",
      "created_at",
      "submitted_at",
      "completed_at",
      "error_code",
      "error_message",
    ];
    const rows = checks.map((check) => [
      check.case_id,
      check.check_type,
      check.status,
      check.provider_key,
      check.risk_level,
      check.recommendation,
      typeof check.score === "number" ? check.score.toFixed(4) : "",
      check.applicant_email,
      check.external_reference,
      check.created_at,
      check.submitted_at || "",
      check.completed_at || "",
      check.error_code || "",
      check.error_message || "",
    ]);
    downloadCsvFile(header, rows, `background-checks-${isoDateStamp()}.csv`);
    toast.success(`Exported ${checks.length} background check row(s).`);
  };

  const exportChecksJson = () => {
    if (checks.length === 0) {
      toast.info("No background check rows to export.");
      return;
    }

    downloadJsonFile(
      {
        exported_at: new Date().toISOString(),
        filters: {
          case_id: caseFilter,
          check_type: checkTypeFilter,
          status: statusFilter,
        },
        total_rows: checks.length,
        checks,
      },
      `background-checks-${isoDateStamp()}.json`,
    );
    toast.success(`Exported ${checks.length} background check row(s) as JSON.`);
  };

  const webhookUrl = useMemo(() => buildProviderWebhookUrl(providerKey), [providerKey]);

  const handleCopyWebhookUrl = async () => {
    try {
      setCopyingWebhook(true);
      await navigator.clipboard.writeText(webhookUrl);
      toast.success("Webhook URL copied.");
    } catch {
      toast.error("Unable to copy webhook URL.");
    } finally {
      setCopyingWebhook(false);
    }
  };

  const handleCopyWebhookHeader = async () => {
    try {
      setCopyingHeader(true);
      await navigator.clipboard.writeText("X-Background-Webhook-Token: <token>");
      toast.success("Webhook header template copied.");
    } catch {
      toast.error("Unable to copy webhook header template.");
    } finally {
      setCopyingHeader(false);
    }
  };

  return (
    <main className="mx-auto max-w-7xl px-4 py-8 space-y-6">
      <header className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-3xl font-black tracking-tight text-slate-900">Background Checks</h1>
            <p className="mt-1 text-sm text-slate-700">
              Submit and monitor third-party verification checks tied to vetting cases.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <ExportActions
              onCsv={exportChecksCsv}
              onJson={exportChecksJson}
              csvDisabled={loadingChecks || checks.length === 0}
              jsonDisabled={loadingChecks || checks.length === 0}
            />
            <Button
              type="button"
              variant="outline"
              onClick={() => void handleRefreshList()}
              disabled={refreshingList}
            >
              <RefreshCw className={`mr-2 h-4 w-4 ${refreshingList ? "animate-spin" : ""}`} />
              Refresh
            </Button>
          </div>
        </div>
      </header>

      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="text-lg font-bold text-slate-900">Provider Operations</h2>
        <p className="mt-1 text-sm text-slate-700">
          Use this webhook endpoint for provider callbacks. The backend validates provider key and optional token header.
        </p>

        <div className="mt-4 grid gap-3 md:grid-cols-2">
          <article className="rounded-xl border border-slate-200 p-4">
            <p className="text-xs font-semibold uppercase text-slate-700">Webhook URL</p>
            <p className="mt-2 break-all text-sm text-slate-800">{webhookUrl}</p>
            <Button
              type="button"
              variant="outline"
              className="mt-3"
              onClick={() => void handleCopyWebhookUrl()}
              disabled={copyingWebhook}
            >
              <ClipboardCopy className="mr-2 h-4 w-4" />
              {copyingWebhook ? "Copying..." : "Copy URL"}
            </Button>
          </article>

          <article className="rounded-xl border border-slate-200 p-4">
            <p className="text-xs font-semibold uppercase text-slate-700">Auth Header Template</p>
            <p className="mt-2 text-sm text-slate-800">X-Background-Webhook-Token: &lt;token&gt;</p>
            <Button
              type="button"
              variant="outline"
              className="mt-3"
              onClick={() => void handleCopyWebhookHeader()}
              disabled={copyingHeader}
            >
              <ClipboardCopy className="mr-2 h-4 w-4" />
              {copyingHeader ? "Copying..." : "Copy Header"}
            </Button>
          </article>
        </div>

        <div className="mt-4 rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 text-xs text-slate-700">
          <p className="font-semibold text-slate-800">Expected webhook payload keys</p>
          <p className="mt-1">
            Include `external_reference` and provider result fields (for example status and result summary) so the
            backend can map updates to the correct background check.
          </p>
        </div>
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="text-lg font-bold text-slate-900">Filters</h2>
        <div className="mt-4 grid gap-3 md:grid-cols-3">
          <div>
            <label htmlFor="bg-check-case-filter" className="mb-1 block text-xs font-semibold uppercase text-slate-700">
              Case
            </label>
            <Select value={caseFilter} onValueChange={setCaseFilter}>
              <SelectTrigger id="bg-check-case-filter" className="w-full">
                <SelectValue placeholder="All cases" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All cases</SelectItem>
                {caseOptions.map((option) => (
                  <SelectItem key={option.id} value={option.case_id}>
                    {option.case_id}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div>
            <label htmlFor="bg-check-type-filter" className="mb-1 block text-xs font-semibold uppercase text-slate-700">
              Check Type
            </label>
            <Select value={checkTypeFilter} onValueChange={(value) => setCheckTypeFilter(value as CheckTypeFilter)}>
              <SelectTrigger id="bg-check-type-filter" className="w-full">
                <SelectValue placeholder="All types" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All types</SelectItem>
                {CHECK_TYPE_OPTIONS.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div>
            <label htmlFor="bg-check-status-filter" className="mb-1 block text-xs font-semibold uppercase text-slate-700">
              Status
            </label>
            <Select value={statusFilter} onValueChange={(value) => setStatusFilter(value as CheckStatusFilter)}>
              <SelectTrigger id="bg-check-status-filter" className="w-full">
                <SelectValue placeholder="All statuses" />
              </SelectTrigger>
              <SelectContent>
                {STATUS_OPTIONS.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="text-lg font-bold text-slate-900">Submit Background Check</h2>
        <form className="mt-4 grid gap-3 md:grid-cols-2" onSubmit={handleCreateCheck}>
          <div>
            <label htmlFor="bg-check-case" className="mb-1 block text-xs font-semibold uppercase text-slate-700">
              Case
            </label>
            <Select value={selectedCase} onValueChange={setSelectedCase} disabled={loadingCases || submitting}>
              <SelectTrigger id="bg-check-case" className="w-full">
                <SelectValue placeholder={loadingCases ? "Loading cases..." : "Select case"} />
              </SelectTrigger>
              <SelectContent>
                {caseOptions.map((option) => (
                  <SelectItem key={option.id} value={option.id}>
                    {option.case_id} ({option.status})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div>
            <label htmlFor="bg-check-type" className="mb-1 block text-xs font-semibold uppercase text-slate-700">
              Check Type
            </label>
            <Select
              value={selectedCheckType}
              onValueChange={(value) => setSelectedCheckType(value as BackgroundCheckType)}
              disabled={submitting}
            >
              <SelectTrigger id="bg-check-type" className="w-full">
                <SelectValue placeholder="Select check type" />
              </SelectTrigger>
              <SelectContent>
                {CHECK_TYPE_OPTIONS.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div>
            <label htmlFor="bg-check-provider" className="mb-1 block text-xs font-semibold uppercase text-slate-700">
              Provider Key
            </label>
            <Input
              id="bg-check-provider"
              value={providerKey}
              onChange={(event) => setProviderKey(event.target.value)}
              placeholder="mock"
              disabled={submitting}
            />
          </div>

          <div>
            <label htmlFor="bg-check-consent-notes" className="mb-1 block text-xs font-semibold uppercase text-slate-700">
              Consent Notes
            </label>
            <Input
              id="bg-check-consent-notes"
              value={consentNotes}
              onChange={(event) => setConsentNotes(event.target.value)}
              placeholder="How consent was captured"
              disabled={submitting}
            />
          </div>

          <div className="md:col-span-2 flex flex-wrap items-center gap-4 pt-1">
            <label className="inline-flex items-center gap-2 text-sm text-slate-700">
              <input
                type="checkbox"
                checked={consentRecorded}
                onChange={(event) => setConsentRecorded(event.target.checked)}
                disabled={submitting}
              />
              Consent recorded
            </label>
            <label className="inline-flex items-center gap-2 text-sm text-slate-700">
              <input
                type="checkbox"
                checked={runAsync}
                onChange={(event) => setRunAsync(event.target.checked)}
                disabled={submitting}
              />
              Queue async refresh after submit
            </label>
            <Button type="submit" disabled={submitting}>
              {submitting ? "Submitting..." : "Submit Check"}
            </Button>
          </div>
        </form>
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-bold text-slate-900">Background Check Runs</h2>
          <p className="text-sm text-slate-700">{checks.length} records</p>
        </div>

        {loadingChecks ? (
          <div className="py-10 text-center text-slate-700">Loading checks...</div>
        ) : errorMessage ? (
          <div className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
            {errorMessage}
          </div>
        ) : checks.length === 0 ? (
          <div className="rounded-lg border border-dashed border-slate-700 px-4 py-8 text-center text-sm text-slate-700">
            No background checks found for the current filter.
          </div>
        ) : (
          <div className="space-y-3">
            {checks.map((check) => (
              <article key={check.id} className="rounded-xl border border-slate-200 p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-slate-900">{check.case_id}</p>
                    <p className="text-xs text-slate-700">
                      {check.check_type} | provider: {check.provider_key}
                    </p>
                    <p className="text-xs text-slate-700 mt-1">Submitted: {formatDate(check.created_at)}</p>
                  </div>
                  <span
                    className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${
                      statusPillClass[check.status]
                    }`}
                  >
                    {check.status.replace("_", " ")}
                  </span>
                </div>

                <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-slate-700 md:grid-cols-5">
                  <div>
                    <p className="text-slate-700">Risk</p>
                    <p className="font-semibold">{check.risk_level}</p>
                  </div>
                  <div>
                    <p className="text-slate-700">Recommendation</p>
                    <p className="font-semibold">{check.recommendation}</p>
                  </div>
                  <div>
                    <p className="text-slate-700">Score</p>
                    <p className="font-semibold">{typeof check.score === "number" ? check.score.toFixed(1) : "-"}</p>
                  </div>
                  <div>
                    <p className="text-slate-700">Applicant</p>
                    <p className="font-semibold">{check.applicant_email || "-"}</p>
                  </div>
                  <div>
                    <p className="text-slate-700">External Ref</p>
                    <p className="font-semibold">{check.external_reference || "-"}</p>
                  </div>
                </div>

                <div className="mt-3 flex flex-wrap items-center gap-2">
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => void handleRefreshCheck(check.id)}
                    disabled={refreshingId === check.id}
                  >
                    <RefreshCw className={`mr-2 h-4 w-4 ${refreshingId === check.id ? "animate-spin" : ""}`} />
                    Refresh Check
                  </Button>
                  <Button type="button" variant="outline" onClick={() => void toggleEvents(check.id)}>
                    <Clock3 className="mr-2 h-4 w-4" />
                    {expandedCheckId === check.id ? "Hide Events" : "View Events"}
                  </Button>
                  <Button asChild variant="outline">
                    <Link to={`/applications/${check.case_id}`}>
                      <Search className="mr-2 h-4 w-4" />
                      Open Case
                    </Link>
                  </Button>
                  {check.refresh_queued ? (
                    <span className="inline-flex items-center gap-1 rounded-full bg-indigo-50 px-2 py-1 text-xs font-medium text-indigo-700">
                      <ShieldCheck className="h-3.5 w-3.5" />
                      Async refresh queued
                    </span>
                  ) : null}
                </div>

                {expandedCheckId === check.id ? (
                  <div className="mt-3 rounded-lg border border-slate-200 bg-slate-50 p-3">
                    <p className="text-xs font-semibold uppercase text-slate-700">Events</p>
                    {(eventsByCheck[check.id] || []).length === 0 ? (
                      <p className="mt-2 text-sm text-slate-700">No events recorded yet.</p>
                    ) : (
                      <ul className="mt-2 space-y-2">
                        {(eventsByCheck[check.id] || []).map((item) => (
                          <li key={item.id} className="rounded-md border border-slate-200 bg-white px-3 py-2">
                            <p className="text-sm font-medium text-slate-800">{item.event_type}</p>
                            <p className="text-xs text-slate-700">
                              {item.status_before || "-"} {"->"} {item.status_after || "-"} at{" "}
                              {formatDate(item.created_at)}
                            </p>
                            {item.message ? <p className="mt-1 text-xs text-slate-700">{item.message}</p> : null}
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                ) : null}
              </article>
            ))}
          </div>
        )}
      </section>
    </main>
  );
};

export default BackgroundChecksPage;
