// src/pages/ApplicationsPage.tsx
import React, { useEffect, useState } from "react";
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

export const ApplicationsPage: React.FC = () => {
  const location = useLocation();
  const [searchParams, setSearchParams] = useSearchParams();
  const { applications, loading, refetch } = useApplications();
  const { isAdmin } = useAuth();

  const isAdminView = location.pathname.startsWith("/admin");
  const isCaseManagerView = true;
  const isValidStatusParam = (value: string | null): value is "pending" | "under_review" | "approved" | "rejected" =>
    value === "pending" || value === "under_review" || value === "approved" || value === "rejected";
  const isValidScopeParam = (value: string | null): value is "all" | "assigned" =>
    value === "all" || value === "assigned";

  const [searchTerm, setSearchTerm] = useState("");
  const statusFromQuery = searchParams.get("status");
  const statusFilter = isValidStatusParam(statusFromQuery) ? statusFromQuery : "all";
  const scopeFromQuery = searchParams.get("scope");
  const canChooseScope = !isAdminView && !isAdmin;
  const scopeFilter = canChooseScope && isValidScopeParam(scopeFromQuery) ? scopeFromQuery : "assigned";

  useEffect(() => {
    if (isAdmin || isAdminView) {
      refetch({ scope: "all" });
      return;
    }
    refetch({ scope: scopeFilter });
  }, [refetch, isAdmin, isAdminView, scopeFilter]);

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

  const detailPathPrefix = isAdminView ? "/admin/cases" : "/applications";

  const filteredApplications = applications.filter((app) => {
    const matchesSearch =
      app.case_id.toLowerCase().includes(searchTerm.toLowerCase()) ||
      app.applicant.full_name?.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesStatus = statusFilter === "all" || app.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <div className="flex justify-between items-center mb-8">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">
              {isCaseManagerView ? "Vetting Cases" : "Applications"}
            </h1>
            <p className="mt-1 text-slate-700">
              {isCaseManagerView
                ? "Review and manage submitted vetting cases"
                : "Review and manage submitted applications"}
            </p>
          </div>
        </div>

        {/* Filters */}
        <div className="bg-white rounded-lg shadow-sm p-6 mb-6">
          <div className="mb-4 rounded-lg border border-indigo-200 bg-indigo-50 px-4 py-3 text-sm text-indigo-900">
            Hover or focus the <Info className="mx-1 inline h-4 w-4 align-text-bottom" /> icons to understand each filter.
          </div>
          <div className={`grid grid-cols-1 gap-4 ${canChooseScope ? "md:grid-cols-3" : "md:grid-cols-2"}`}>
            <div>
              <FieldLabel
                htmlFor="applications-search"
                label="Search"
                help="Find applications by case ID or applicant name."
                className="mb-2 flex items-center gap-1.5"
                textClassName="block text-sm font-medium text-slate-800"
              />
              <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-slate-700 w-5 h-5" />
                <Input
                  id="applications-search"
                  type="text"
                  placeholder="Search by case ID or name..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="w-full rounded-lg border border-slate-700 py-2 pl-10 pr-4 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>
            </div>

            <div>
              <FieldLabel
                label="Status"
                help="Filter the list by current application state."
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
                    <SelectItem value="under_review">Under Review</SelectItem>
                    <SelectItem value="approved">Approved</SelectItem>
                    <SelectItem value="rejected">Rejected</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            {canChooseScope && (
              <div>
                <FieldLabel
                  label="Scope"
                  help="Choose whether to show assigned cases only or every case available to your role."
                  className="mb-2 flex items-center gap-1.5"
                  textClassName="block text-sm font-medium text-slate-800"
                />
                <div className="relative">
                  <Filter className="absolute left-3 top-1/2 transform -translate-y-1/2 text-slate-700 w-5 h-5 z-10" />
                  <Select value={scopeFilter} onValueChange={handleScopeChange}>
                    <SelectTrigger className="w-full rounded-lg border border-slate-700 py-2 pl-10 pr-4 focus:outline-none focus:ring-2 focus:ring-indigo-500">
                      <SelectValue placeholder="Case scope" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="assigned">Assigned to me</SelectItem>
                      <SelectItem value="all">All cases</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Applications List */}
        {loading ? (
          <div className="flex justify-center items-center py-20">
            <Loader size="lg" />
          </div>
        ) : filteredApplications.length === 0 ? (
          <div className="bg-white rounded-lg shadow-sm p-12 text-center">
            <div className="text-6xl mb-4">📋</div>
            <h3 className="text-xl font-semibold text-gray-900 mb-2">
              No applications found
            </h3>
            <p className="mb-6 text-slate-700">
              {searchTerm || statusFilter !== "all"
                ? "Try adjusting your filters"
                : "No cases match the current scope."}
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
                      {application.application_type}
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


