import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useSelector } from "react-redux";
import { toast } from "react-toastify";
import { Bug, Loader2, Send } from "lucide-react";
import { useSearchParams } from "react-router-dom";

import type { RootState } from "@/app/store";
import { adminService } from "@/services/admin.service";
import type {
  PlatformIssueCategory,
  PlatformIssueCreatePayload,
  PlatformIssueReport,
  PlatformIssueSeverity,
  PlatformIssueStatus,
} from "@/types";

const STATUS_OPTIONS: PlatformIssueStatus[] = [
  "open",
  "in_progress",
  "resolved",
];
const CATEGORY_OPTIONS: PlatformIssueCategory[] = [
  "bug",
  "issue",
  "improvement",
];
const SEVERITY_OPTIONS: PlatformIssueSeverity[] = [
  "low",
  "medium",
  "high",
  "critical",
];

const toTitle = (value: string): string =>
  value.replace(/_/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());

type IssueReportsTab = "report" | "submitted";

const PlatformIssueReportsPage: React.FC = () => {
  const { user } = useSelector((state: RootState) => state.auth);
  const [searchParams, setSearchParams] = useSearchParams();
  const isSuperuser = Boolean(user?.is_superuser);
  const requestedTab = searchParams.get("tab");
  const activeTab: IssueReportsTab = isSuperuser
    ? "submitted"
    : requestedTab === "submitted"
      ? "report"
      : "report";
  const isSubmittedIssuesView = isSuperuser && activeTab === "submitted";
  const pageTitle = isSubmittedIssuesView
    ? "View Submitted Issues"
    : "Issue Reports";
  const pageDescription = isSubmittedIssuesView
    ? "Review and triage issue reports submitted by platform users."
    : "Report bugs and issues to help us improve the platform.";

  const tabOptions = useMemo(
    () =>
      [
        !isSuperuser
          ? ({
              value: "report",
              label: "Issues Report",
            } as const)
          : null,
        isSuperuser
          ? ({
              value: "submitted",
              label: "View Submitted Issues",
            } as const)
          : null,
      ].filter(Boolean),
    [isSuperuser],
  );

  const [issues, setIssues] = useState<PlatformIssueReport[]>([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [updatingIssueId, setUpdatingIssueId] = useState<string | null>(null);

  const [form, setForm] = useState<PlatformIssueCreatePayload>({
    title: "",
    description: "",
    steps_to_reproduce: "",
    category: "issue",
    severity: "medium",
    page_url: "",
    browser_info: "",
  });

  const loadIssues = useCallback(async () => {
    if (!isSuperuser) {
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const response = await adminService.listIssues({
        page: 1,
        page_size: 100,
      });
      setIssues(response.results);
    } catch (error) {
      toast.error(
        error instanceof Error
          ? error.message
          : "Failed to fetch issue reports.",
      );
    } finally {
      setLoading(false);
    }
  }, [isSuperuser]);

  useEffect(() => {
    if (!isSuperuser && requestedTab === "submitted") {
      const nextParams = new URLSearchParams(searchParams);
      nextParams.delete("tab");
      setSearchParams(nextParams, { replace: true });
    }
  }, [isSuperuser, requestedTab, searchParams, setSearchParams]);

  useEffect(() => {
    if (isSubmittedIssuesView) {
      void loadIssues();
    } else {
      setLoading(false);
    }
  }, [isSubmittedIssuesView, loadIssues]);

  const handleTabChange = (nextTab: IssueReportsTab) => {
    const nextParams = new URLSearchParams(searchParams);
    if (nextTab === "submitted") {
      nextParams.set("tab", "submitted");
    } else {
      nextParams.delete("tab");
    }
    setSearchParams(nextParams);
  };

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!form.title.trim() || !form.description.trim()) {
      toast.error("Title and description are required.");
      return;
    }

    setSubmitting(true);
    try {
      const payload: PlatformIssueCreatePayload = {
        ...form,
        title: form.title.trim(),
        description: form.description.trim(),
        steps_to_reproduce: form.steps_to_reproduce?.trim() || "",
        page_url: form.page_url?.trim() || window.location.href,
        browser_info: form.browser_info?.trim() || window.navigator.userAgent,
      };
      const created = await adminService.reportIssue(payload);
      setIssues((current) => [created, ...current]);
      toast.success("Issue reported successfully.");
      setForm({
        title: "",
        description: "",
        steps_to_reproduce: "",
        category: "issue",
        severity: "medium",
        page_url: "",
        browser_info: "",
      });
    } catch (error) {
      toast.error(
        error instanceof Error
          ? error.message
          : "Failed to submit issue report.",
      );
    } finally {
      setSubmitting(false);
    }
  };

  const updateStatus = async (
    issue: PlatformIssueReport,
    status: PlatformIssueStatus,
  ) => {
    setUpdatingIssueId(issue.id);
    try {
      const updated = await adminService.updateIssue(issue.id, { status });
      setIssues((current) =>
        current.map((item) => (item.id === issue.id ? updated : item)),
      );
      toast.success("Issue status updated.");
    } catch (error) {
      toast.error(
        error instanceof Error
          ? error.message
          : "Failed to update issue status.",
      );
    } finally {
      setUpdatingIssueId(null);
    }
  };

  return (
    <div className="space-y-8">
      <div className="flex items-center gap-3">
        <span className="inline-flex h-10 w-10 items-center justify-center rounded-xl bg-rose-100 text-rose-700">
          <Bug className="h-5 w-5" />
        </span>
        <div>
          <h1 className="text-3xl font-bold tracking-tight">{pageTitle}</h1>
          <p className="text-sm text-muted-foreground">{pageDescription}</p>
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        {tabOptions.map((tab) => {
          if (!tab) {
            return null;
          }
          const isActive = activeTab === tab.value;
          return (
            <button
              key={tab.value}
              type="button"
              onClick={() => handleTabChange(tab.value)}
              className={[
                "rounded-full border px-4 py-2 text-sm font-semibold transition",
                isActive
                  ? "border-indigo-600 bg-indigo-600 text-white"
                  : "border-slate-300 bg-white text-slate-700 hover:bg-slate-100",
              ].join(" ")}
            >
              {tab.label}
            </button>
          );
        })}
      </div>

      {!isSuperuser ? (
        <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="text-lg font-semibold text-slate-900">
            Report New Issue
          </h2>
          <form
            className="mt-4 grid gap-4 md:grid-cols-2"
            onSubmit={handleSubmit}
          >
            <label className="space-y-1 text-sm text-slate-700 md:col-span-2">
              <span>Title</span>
              <input
                required
                value={form.title}
                onChange={(event) =>
                  setForm((prev) => ({ ...prev, title: event.target.value }))
                }
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-200"
              />
            </label>

            <label className="space-y-1 text-sm text-slate-700">
              <span>Category</span>
              <select
                value={form.category}
                onChange={(event) =>
                  setForm((prev) => ({
                    ...prev,
                    category: event.target.value as PlatformIssueCategory,
                  }))
                }
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-200"
              >
                {CATEGORY_OPTIONS.map((option) => (
                  <option key={option} value={option}>
                    {toTitle(option)}
                  </option>
                ))}
              </select>
            </label>

            <label className="space-y-1 text-sm text-slate-700">
              <span>Severity</span>
              <select
                value={form.severity}
                onChange={(event) =>
                  setForm((prev) => ({
                    ...prev,
                    severity: event.target.value as PlatformIssueSeverity,
                  }))
                }
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-200"
              >
                {SEVERITY_OPTIONS.map((option) => (
                  <option key={option} value={option}>
                    {toTitle(option)}
                  </option>
                ))}
              </select>
            </label>

            <label className="space-y-1 text-sm text-slate-700 md:col-span-2">
              <span>Description</span>
              <textarea
                required
                rows={4}
                value={form.description}
                onChange={(event) =>
                  setForm((prev) => ({
                    ...prev,
                    description: event.target.value,
                  }))
                }
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-200"
              />
            </label>

            <label className="space-y-1 text-sm text-slate-700 md:col-span-2">
              <span>Steps to Reproduce</span>
              <textarea
                rows={3}
                value={form.steps_to_reproduce}
                onChange={(event) =>
                  setForm((prev) => ({
                    ...prev,
                    steps_to_reproduce: event.target.value,
                  }))
                }
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-200"
              />
            </label>

            <label className="space-y-1 text-sm text-slate-700">
              <span>Page URL</span>
              <input
                value={form.page_url}
                onChange={(event) =>
                  setForm((prev) => ({ ...prev, page_url: event.target.value }))
                }
                placeholder={window.location.href}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-200"
              />
            </label>

            <label className="space-y-1 text-sm text-slate-700">
              <span>Browser / Device</span>
              <input
                value={form.browser_info}
                onChange={(event) =>
                  setForm((prev) => ({
                    ...prev,
                    browser_info: event.target.value,
                  }))
                }
                placeholder={window.navigator.userAgent}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-200"
              />
            </label>

            <div className="md:col-span-2">
              <button
                type="submit"
                disabled={submitting}
                className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {submitting ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Send className="h-4 w-4" />
                )}
                {submitting ? "Submitting..." : "Submit Issue"}
              </button>
            </div>
          </form>
        </section>
      ) : null}

      {isSuperuser ? (
        <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="mb-4 flex items-center justify-between gap-3">
            <h2 className="text-lg font-semibold text-slate-900">
              Submitted Issues
              {isSuperuser ? " (Admin view)" : null}
            </h2>
            {isSuperuser ? (
              <button
                type="button"
                onClick={() => void loadIssues()}
                className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-100"
              >
                Refresh
              </button>
            ) : null}
          </div>

          {!isSuperuser ? (
            <p className="text-sm text-slate-600">
              Only superusers can review submitted issue reports here.
            </p>
          ) : loading ? (
            <div className="flex items-center gap-2 text-sm text-slate-600">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading issue reports...
            </div>
          ) : issues.length === 0 ? (
            <p className="text-sm text-slate-600">
              No issues have been reported yet.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-200 text-left text-xs uppercase tracking-wider text-slate-500">
                    <th className="px-3 py-2">Title</th>
                    <th className="px-3 py-2">Reporter</th>
                    <th className="px-3 py-2">Severity</th>
                    <th className="px-3 py-2">Status</th>
                    <th className="px-3 py-2">Created</th>
                  </tr>
                </thead>
                <tbody>
                  {issues.map((issue) => (
                    <tr
                      key={issue.id}
                      className="border-b border-slate-100 align-top"
                    >
                      <td className="px-3 py-3">
                        <p className="font-medium text-slate-900">
                          {issue.title}
                        </p>
                        <p className="mt-1 text-xs text-slate-600">
                          {issue.description}
                        </p>
                      </td>
                      <td className="px-3 py-3 text-slate-700">
                        {issue.reporter_email}
                      </td>
                      <td className="px-3 py-3 text-slate-700">
                        {toTitle(issue.severity)}
                      </td>
                      <td className="px-3 py-3">
                        <select
                          title={`Status for ${issue.title}`}
                          aria-label={`Status for ${issue.title}`}
                          value={issue.status}
                          disabled={updatingIssueId === issue.id}
                          onChange={(event) =>
                            void updateStatus(
                              issue,
                              event.target.value as PlatformIssueStatus,
                            )
                          }
                          className="rounded-md border border-slate-300 px-2 py-1 text-xs text-slate-800 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-200"
                        >
                          {STATUS_OPTIONS.map((statusOption) => (
                            <option key={statusOption} value={statusOption}>
                              {toTitle(statusOption)}
                            </option>
                          ))}
                        </select>
                      </td>
                      <td className="px-3 py-3 text-slate-700">
                        {new Date(issue.created_at).toLocaleString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      ) : null}
    </div>
  );
};

export default PlatformIssueReportsPage;
