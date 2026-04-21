// src/pages/ApplicationsPage.tsx
import React, { useEffect, useMemo, useState } from "react";
import { Link, useLocation, useSearchParams } from "react-router-dom";
import { Search, Filter, Info } from "lucide-react";
import { useApplications } from "@/hooks/useApplications";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Loader } from "@/components/common/Loader";
import { Input } from "@/components/ui/input";
import { FieldLabel } from "@/components/common/FieldHelp";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useAuth } from "@/hooks/useAuth";
import { formatDate } from "@/utils/helper";

const PRIORITY_OPTIONS = ["low", "medium", "high", "critical"] as const;
const APPLICATION_TYPE_OPTIONS = [
  "employment",
  "appointment",
  "contract",
  "volunteer",
] as const;

export const ApplicationsPage: React.FC = () => {
  const location = useLocation();
  const [searchParams, setSearchParams] = useSearchParams();
  const { applications, loading, refetch } = useApplications();
  const { isAdmin, canManageActiveOrganizationGovernance } = useAuth();

  const isAdminView = location.pathname.startsWith("/admin");
  const isValidStatusParam = (
    value: string | null,
  ): value is
    | "pending"
    | "document_upload"
    | "document_analysis"
    | "interview_scheduled"
    | "interview_in_progress"
    | "under_review"
    | "approved"
    | "rejected"
    | "on_hold" =>
    value === "pending" ||
    value === "document_upload" ||
    value === "document_analysis" ||
    value === "interview_scheduled" ||
    value === "interview_in_progress" ||
    value === "under_review" ||
    value === "approved" ||
    value === "rejected" ||
    value === "on_hold";
  const isValidScopeParam = (
    value: string | null,
  ): value is "all" | "assigned" => value === "all" || value === "assigned";

  const querySearch = (searchParams.get("q") || "").trim();
  const queryExercise = (searchParams.get("exercise") || "").trim();
  const queryOffice = (searchParams.get("office") || "").trim();
  const [priorityFilter, setPriorityFilter] = useState(
    () => searchParams.get("priority") || "",
  );
  const [applicationTypeFilter, setApplicationTypeFilter] = useState(
    () => searchParams.get("application_type") || "",
  );
  const statusFromQuery = searchParams.get("status");
  const statusFilter = isValidStatusParam(statusFromQuery)
    ? statusFromQuery
    : "all";
  const scopeFromQuery = searchParams.get("scope");
  const canChooseScope =
    !isAdminView && !isAdmin && !canManageActiveOrganizationGovernance;
  const scopeFilter =
    canChooseScope && isValidScopeParam(scopeFromQuery)
      ? scopeFromQuery
      : "assigned";

  useEffect(() => {
    if (isAdmin || isAdminView || canManageActiveOrganizationGovernance) {
      refetch({ scope: "all" });
      return;
    }
    refetch({ scope: scopeFilter });
  }, [
    refetch,
    isAdmin,
    isAdminView,
    canManageActiveOrganizationGovernance,
    scopeFilter,
  ]);

  const handleStatusChange = (value: string) => {
    const nextParams = new URLSearchParams(searchParams);
    if (value === "all") {
      nextParams.delete("status");
    } else {
      nextParams.set("status", value);
    }
    setSearchParams(nextParams, { replace: true });
  };

  const handleScopeChange = (value: string) => {
    const nextParams = new URLSearchParams(searchParams);
    if (value === "assigned") {
      nextParams.delete("scope");
    } else {
      nextParams.set("scope", "all");
    }
    setSearchParams(nextParams, { replace: true });
  };

  const handleSearchChange = (value: string) => {
    const nextParams = new URLSearchParams(searchParams);
    if (!value.trim()) {
      nextParams.delete("q");
    } else {
      nextParams.set("q", value);
    }
    setSearchParams(nextParams, { replace: true });
  };

  const clearWorkflowContext = () => {
    const nextParams = new URLSearchParams(searchParams);
    nextParams.delete("q");
    nextParams.delete("exercise");
    nextParams.delete("office");
    setSearchParams(nextParams, { replace: true });
  };

  const detailPathPrefix = isAdminView ? "/admin/cases" : "/applications";
  const resolveApplicantDisplay = (app: (typeof applications)[number]) => {
    if (app.applicant && typeof app.applicant === "object") {
      return app.applicant.full_name || app.applicant.email || "";
    }
    return app.applicant_email || String(app.applicant || "");
  };
  const resolveCaseLabel = (app: (typeof applications)[number]) =>
    app.office_title ||
    app.position_applied ||
    app.application_type ||
    "vetting dossier";
  const workflowContextLabel = useMemo(() => {
    const labels: string[] = [];
    if (queryOffice) {
      labels.push(`Office: ${queryOffice}`);
    }
    if (queryExercise) {
      labels.push("Appointment exercise context active");
    }
    return labels;
  }, [queryExercise, queryOffice]);

  const filteredApplications = applications.filter((app) => {
    const applicantDisplay = resolveApplicantDisplay(app).toLowerCase();
    const officeDisplay = String(
      app.office_title || app.position_applied || "",
    ).toLowerCase();
    const normalizedSearchTerm = querySearch.toLowerCase();
    const matchesSearch =
      app.case_id.toLowerCase().includes(normalizedSearchTerm) ||
      applicantDisplay.includes(normalizedSearchTerm) ||
      (app.applicant_email || "")
        .toLowerCase()
        .includes(normalizedSearchTerm) ||
      officeDisplay.includes(normalizedSearchTerm);
    const matchesStatus = statusFilter === "all" || app.status === statusFilter;
    const matchesPriority = !priorityFilter || app.priority === priorityFilter;
    const matchesAppType =
      !applicationTypeFilter || app.application_type === applicationTypeFilter;
    const matchesExercise =
      !queryExercise || app.appointment_exercise_id === queryExercise;
    const matchesOffice =
      !queryOffice || officeDisplay.includes(queryOffice.toLowerCase());
    return (
      matchesSearch &&
      matchesStatus &&
      matchesPriority &&
      matchesAppType &&
      matchesExercise &&
      matchesOffice
    );
  });

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-6 xl:px-8">
        {/* Header */}
        <div className="flex justify-between items-center mb-8">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">
              Vetting Dossiers
            </h1>
            <p className="mt-1 text-slate-700">
              Review and manage vetting dossiers and nomination files.
            </p>
          </div>
        </div>

        <section className="mb-6 rounded-xl border border-cyan-200 bg-cyan-50 p-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-cyan-900">
            Office-Centered Sequence
          </p>
          <p className="mt-2 text-sm text-cyan-900">
            Office -&gt; Appointment Exercise -&gt; Nominee / Nomination File
            -&gt; Vetting Dossier -&gt; Review -&gt; Approval -&gt; Appointment
            -&gt; Publication
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            <Link
              to="/government/positions"
              className="inline-flex rounded-md border border-cyan-300 bg-white px-3 py-1.5 text-xs font-semibold text-cyan-900 hover:bg-cyan-100"
            >
              Offices
            </Link>
            <Link
              to="/campaigns"
              className="inline-flex rounded-md border border-cyan-300 bg-white px-3 py-1.5 text-xs font-semibold text-cyan-900 hover:bg-cyan-100"
            >
              Appointment Exercises
            </Link>
            <Link
              to="/government/appointments"
              className="inline-flex rounded-md border border-cyan-300 bg-white px-3 py-1.5 text-xs font-semibold text-cyan-900 hover:bg-cyan-100"
            >
              Nomination Files
            </Link>
          </div>
          {workflowContextLabel.length > 0 || querySearch ? (
            <div className="mt-3 flex flex-wrap items-center gap-2">
              {workflowContextLabel.map((label) => (
                <span
                  key={label}
                  className="inline-flex rounded-full bg-white px-2.5 py-1 text-xs font-semibold text-cyan-900"
                >
                  {label}
                </span>
              ))}
              {querySearch ? (
                <span className="inline-flex rounded-full bg-white px-2.5 py-1 text-xs font-semibold text-cyan-900">
                  Search: {querySearch}
                </span>
              ) : null}
              <button
                type="button"
                onClick={clearWorkflowContext}
                className="inline-flex rounded-md border border-cyan-300 bg-white px-2.5 py-1 text-xs font-semibold text-cyan-900 hover:bg-cyan-100"
              >
                Clear Context
              </button>
            </div>
          ) : null}
        </section>

        {/* Filters */}
        <div className="bg-white rounded-lg shadow-sm p-6 mb-6">
          <div className="mb-4 rounded-lg border border-indigo-200 bg-indigo-50 px-4 py-3 text-sm text-indigo-900">
            Hover or focus the{" "}
            <Info className="mx-1 inline h-4 w-4 align-text-bottom" /> icons to
            understand each filter.
          </div>
          <div
            className={`grid grid-cols-1 gap-4 ${canChooseScope ? "md:grid-cols-4" : "md:grid-cols-3"}`}
          >
            <div>
              <FieldLabel
                htmlFor="applications-search"
                label="Search"
                help="Find dossiers by case ID, nominee name, or office."
                className="mb-2 flex items-center gap-1.5"
                textClassName="block text-sm font-medium text-slate-800"
              />
              <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-slate-700 w-5 h-5" />
                <Input
                  id="applications-search"
                  type="text"
                  placeholder="Search by dossier ID, nominee, or office..."
                  value={querySearch}
                  onChange={(e) => handleSearchChange(e.target.value)}
                  className="w-full rounded-lg border border-slate-700 py-2 pl-10 pr-4 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>
            </div>

            <div>
              <FieldLabel
                label="Status"
                help="Filter the list by current dossier state."
                className="mb-2 flex items-center gap-1.5"
                textClassName="block text-sm font-medium text-slate-800"
              />
              <div className="relative">
                <Filter className="absolute left-3 top-1/2 transform -translate-y-1/2 text-slate-700 w-5 h-5 z-10" />
                <Select value={statusFilter} onValueChange={handleStatusChange}>
                  <SelectTrigger className="w-full rounded-lg border border-slate-700 py-2 pl-10 pr-4 focus:outline-none focus:ring-2 focus:ring-indigo-500">
                    <SelectValue placeholder="Filter by status" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Statuses</SelectItem>
                    <SelectItem value="pending">Pending</SelectItem>
                    <SelectItem value="document_upload">
                      Document Upload
                    </SelectItem>
                    <SelectItem value="document_analysis">
                      Document Analysis
                    </SelectItem>
                    <SelectItem value="interview_scheduled">
                      Interview Scheduled
                    </SelectItem>
                    <SelectItem value="interview_in_progress">
                      Interview In Progress
                    </SelectItem>
                    <SelectItem value="under_review">Under Review</SelectItem>
                    <SelectItem value="approved">Approved</SelectItem>
                    <SelectItem value="rejected">Rejected</SelectItem>
                    <SelectItem value="on_hold">On Hold</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div>
              <FieldLabel
                label="Priority"
                help="Filter by case urgency level."
                className="mb-2 flex items-center gap-1.5"
                textClassName="block text-sm font-medium text-slate-800"
              />
              <div className="relative">
                <Filter className="absolute left-3 top-1/2 transform -translate-y-1/2 text-slate-700 w-5 h-5 z-10" />
                <Select
                  value={priorityFilter || "all"}
                  onValueChange={(v) => setPriorityFilter(v === "all" ? "" : v)}
                >
                  <SelectTrigger className="w-full rounded-lg border border-slate-700 py-2 pl-10 pr-4 focus:outline-none focus:ring-2 focus:ring-indigo-500">
                    <SelectValue placeholder="All priorities" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Priorities</SelectItem>
                    {PRIORITY_OPTIONS.map((p) => (
                      <SelectItem key={p} value={p} className="capitalize">
                        {p}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div>
              <FieldLabel
                label="Type"
                help="Filter by application type."
                className="mb-2 flex items-center gap-1.5"
                textClassName="block text-sm font-medium text-slate-800"
              />
              <div className="relative">
                <Filter className="absolute left-3 top-1/2 transform -translate-y-1/2 text-slate-700 w-5 h-5 z-10" />
                <Select
                  value={applicationTypeFilter || "all"}
                  onValueChange={(v) =>
                    setApplicationTypeFilter(v === "all" ? "" : v)
                  }
                >
                  <SelectTrigger className="w-full rounded-lg border border-slate-700 py-2 pl-10 pr-4 focus:outline-none focus:ring-2 focus:ring-indigo-500">
                    <SelectValue placeholder="All types" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Types</SelectItem>
                    {APPLICATION_TYPE_OPTIONS.map((t) => (
                      <SelectItem key={t} value={t} className="capitalize">
                        {t}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            {canChooseScope && (
              <div>
                <FieldLabel
                  label="Scope"
                  help="Choose whether to show assigned dossiers only or every dossier available to your role."
                  className="mb-2 flex items-center gap-1.5"
                  textClassName="block text-sm font-medium text-slate-800"
                />
                <div className="relative">
                  <Filter className="absolute left-3 top-1/2 transform -translate-y-1/2 text-slate-700 w-5 h-5 z-10" />
                  <Select value={scopeFilter} onValueChange={handleScopeChange}>
                    <SelectTrigger className="w-full rounded-lg border border-slate-700 py-2 pl-10 pr-4 focus:outline-none focus:ring-2 focus:ring-indigo-500">
                      <SelectValue placeholder="Dossier scope" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="assigned">Assigned to me</SelectItem>
                      <SelectItem value="all">All dossiers</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Dossier List */}
        {loading ? (
          <div className="flex justify-center items-center py-20">
            <Loader size="lg" />
          </div>
        ) : filteredApplications.length === 0 ? (
          <div className="bg-white rounded-lg shadow-sm p-12 text-center">
            <div className="text-6xl mb-4">📋</div>
            <h3 className="text-xl font-semibold text-gray-900 mb-2">
              No vetting dossiers found
            </h3>
            <p className="mb-6 text-slate-700">
              {querySearch || statusFilter !== "all"
                ? "Try adjusting your filters"
                : "No dossiers match the current scope."}
            </p>
          </div>
        ) : (
          <div className="grid gap-6">
            {filteredApplications.map((application) => (
              <Link
                key={application.id}
                to={`${detailPathPrefix}/${application.case_id}`}
                className="bg-white rounded-lg shadow-sm p-6 hover:shadow-md transition-shadow"
              >
                <div className="flex justify-between items-start mb-4">
                  <div>
                    <h3 className="text-xl font-semibold text-gray-900 mb-1">
                      {application.case_id}
                    </h3>
                    <p className="text-slate-700">
                      {resolveCaseLabel(application)}
                    </p>
                  </div>
                  <StatusBadge status={application.status} />
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
                  <div>
                    <span className="text-slate-700">Priority:</span>
                    <span className="ml-2 font-medium capitalize">
                      {application.priority}
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-700">Submitted:</span>
                    <span className="ml-2 font-medium">
                      {formatDate(application.created_at)}
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-700">Updated:</span>
                    <span className="ml-2 font-medium">
                      {formatDate(application.updated_at)}
                    </span>
                  </div>
                </div>

                {application.notes && (
                  <p className="mt-4 line-clamp-2 text-sm text-slate-800">
                    {application.notes}
                  </p>
                )}
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
