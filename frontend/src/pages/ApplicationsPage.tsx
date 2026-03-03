// src/pages/ApplicationsPage.tsx
import React, { useEffect, useState } from "react";
import { Link, useLocation, useSearchParams } from "react-router-dom";
import { Plus, Search, Filter } from "lucide-react";
import { useApplications } from "@/hooks/useApplications";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Loader } from "@/components/common/Loader";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { formatDate } from "@/utils/helper";

export const ApplicationsPage: React.FC = () => {
  const location = useLocation();
  const [searchParams, setSearchParams] = useSearchParams();
  const { applications, loading, refetch } = useApplications();

  const isAdminView = location.pathname.startsWith("/admin");
  const isValidStatusParam = (value: string | null): value is "pending" | "under_review" | "approved" | "rejected" =>
    value === "pending" || value === "under_review" || value === "approved" || value === "rejected";

  const [searchTerm, setSearchTerm] = useState("");
  const statusFromQuery = searchParams.get("status");
  const statusFilter = isValidStatusParam(statusFromQuery) ? statusFromQuery : "all";

  useEffect(() => {
    refetch();
  }, [refetch]);

  const handleStatusChange = (value: string) => {
    const nextParams = new URLSearchParams(searchParams);
    if (value === "all") {
      nextParams.delete("status");
    } else {
      nextParams.set("status", value);
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
              {isAdminView ? "Application Cases" : "My Applications"}
            </h1>
            <p className="mt-1 text-slate-700">
              {isAdminView
                ? "Review and manage submitted vetting cases"
                : "Track and manage your vetting applications"}
            </p>
          </div>
          {!isAdminView && (
            <Button asChild>
              <Link
                to="/applications/new"
                className="inline-flex items-center gap-2 px-6 py-3 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors"
              >
                <Plus className="w-5 h-5" />
                New Application
              </Link>
            </Button>
          )}
        </div>

        {/* Filters */}
        <div className="bg-white rounded-lg shadow-sm p-6 mb-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-slate-700 w-5 h-5" />
              <Input
                type="text"
                placeholder="Search by case ID or name..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full rounded-lg border border-slate-700 py-2 pl-10 pr-4 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>

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
                : "Get started by creating your first application"}
            </p>
            {!isAdminView && !searchTerm && statusFilter === "all" && (
              <Button asChild>
                <Link
                  to="/applications/new"
                  className="inline-flex items-center gap-2 px-6 py-3 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700"
                >
                  <Plus className="w-5 h-5" />
                  Create Application
                </Link>
              </Button>
            )}
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


