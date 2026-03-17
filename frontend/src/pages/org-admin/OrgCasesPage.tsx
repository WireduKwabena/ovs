import React, { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import {
  FolderOpen,
  Filter,
  RefreshCw,
  ChevronRight,
  XCircle,
} from "lucide-react";
import { toast } from "react-toastify";

import { adminService } from "@/services/admin.service";
import type { AdminCase } from "@/types";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";

const STATUS_OPTIONS = ["pending", "under_review", "approved", "rejected", "flagged"];
const PRIORITY_OPTIONS = ["low", "medium", "high", "critical"];
const APPLICATION_TYPE_OPTIONS = ["employment", "appointment", "contract", "volunteer"];

const statusColor = (status: string) => {
  switch (status) {
    case "approved": return "bg-emerald-500/10 text-emerald-600 border-emerald-500/20";
    case "rejected": return "bg-rose-500/10 text-rose-600 border-rose-500/20";
    case "under_review": return "bg-amber-500/10 text-amber-600 border-amber-500/20";
    case "flagged": return "bg-orange-500/10 text-orange-600 border-orange-500/20";
    default: return "bg-primary/10 text-primary border-primary/20";
  }
};

const priorityColor = (priority: string) => {
  switch (priority) {
    case "critical": return "bg-rose-500/10 text-rose-600";
    case "high": return "bg-amber-500/10 text-amber-600";
    case "medium": return "bg-blue-500/10 text-blue-600";
    default: return "bg-muted/50 text-muted-foreground";
  }
};

const OrgCasesPage: React.FC = () => {
  const navigate = useNavigate();
  const { orgId } = useParams<{ orgId: string }>();
  const organizationId = String(orgId || "").trim();
  const [searchParams, setSearchParams] = useSearchParams();

  const [cases, setCases] = useState<AdminCase[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const [statusFilter, setStatusFilter] = useState(() => searchParams.get("status") || "");
  const [priorityFilter, setPriorityFilter] = useState(() => searchParams.get("priority") || "");
  const [applicationTypeFilter, setApplicationTypeFilter] = useState(
    () => searchParams.get("application_type") || "",
  );

  const hasActiveFilters = Boolean(statusFilter || priorityFilter || applicationTypeFilter);

  const fetchCases = useCallback(
    async (isSilent = false) => {
      if (!organizationId) return;
      if (!isSilent) setLoading(true);
      else setRefreshing(true);

      try {
        const response = await adminService.getOrgCases(organizationId, {
          status: statusFilter || undefined,
          priority: priorityFilter || undefined,
          application_type: applicationTypeFilter || undefined,
        });
        setCases(response.results);
      } catch {
        toast.error("Failed to load organization cases");
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [organizationId, statusFilter, priorityFilter, applicationTypeFilter],
  );

  useEffect(() => {
    void fetchCases();
  }, [fetchCases]);

  const applyFilters = () => {
    const params: Record<string, string> = {};
    if (statusFilter) params.status = statusFilter;
    if (priorityFilter) params.priority = priorityFilter;
    if (applicationTypeFilter) params.application_type = applicationTypeFilter;
    setSearchParams(params);
  };

  const clearFilters = () => {
    setStatusFilter("");
    setPriorityFilter("");
    setApplicationTypeFilter("");
    setSearchParams({});
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Vetting Cases</h1>
          <p className="text-muted-foreground mt-1 text-sm md:text-base">
            Review vetting cases within the currently selected organization.
          </p>
        </div>
        <Button
          variant="outline"
          className="rounded-xl gap-2"
          onClick={() => void fetchCases(true)}
          disabled={refreshing}
        >
          <RefreshCw className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`} />
          Refresh
        </Button>
      </div>

      {/* Filters */}
      <Card className="p-4 rounded-2xl border-border/70 bg-card/50 shadow-sm backdrop-blur-sm">
        <div className="flex flex-col gap-4">
          <div className="flex flex-wrap gap-4">
            <div className="flex-1 min-w-[160px]">
              <label htmlFor="status-filter" className="block text-xs font-bold uppercase tracking-widest text-muted-foreground mb-1">
                Status
              </label>
              <select
                id="status-filter"
                className="w-full bg-background/50 border border-border/70 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/20"
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
              >
                <option value="">All Statuses</option>
                {STATUS_OPTIONS.map((s) => (
                  <option key={s} value={s}>{s.replace(/_/g, " ")}</option>
                ))}
              </select>
            </div>

            <div className="flex-1 min-w-[160px]">
              <label htmlFor="priority-filter" className="block text-xs font-bold uppercase tracking-widest text-muted-foreground mb-1">
                Priority
              </label>
              <select
                id="priority-filter"
                className="w-full bg-background/50 border border-border/70 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/20"
                value={priorityFilter}
                onChange={(e) => setPriorityFilter(e.target.value)}
              >
                <option value="">All Priorities</option>
                {PRIORITY_OPTIONS.map((p) => (
                  <option key={p} value={p}>{p}</option>
                ))}
              </select>
            </div>

            <div className="flex-1 min-w-[160px]">
              <label htmlFor="app-type-filter" className="block text-xs font-bold uppercase tracking-widest text-muted-foreground mb-1">
                Application Type
              </label>
              <select
                id="app-type-filter"
                aria-label="application type"
                className="w-full bg-background/50 border border-border/70 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/20"
                value={applicationTypeFilter}
                onChange={(e) => setApplicationTypeFilter(e.target.value)}
              >
                <option value="">All Types</option>
                {APPLICATION_TYPE_OPTIONS.map((t) => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </select>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <Button className="rounded-xl gap-2" onClick={applyFilters}>
              <Filter className="h-4 w-4" />
              Apply Filters
            </Button>
            {hasActiveFilters && (
              <>
                <span className="text-xs font-bold uppercase tracking-widest text-primary">
                  Active Filters
                </span>
                <Button
                  variant="outline"
                  className="rounded-xl gap-2 text-destructive border-destructive/30"
                  aria-label="clear case filters"
                  onClick={clearFilters}
                >
                  <XCircle className="h-4 w-4" />
                  Clear Case Filters
                </Button>
              </>
            )}
          </div>
        </div>
      </Card>

      {/* Cases List */}
      <div className="space-y-4">
        {loading ? (
          <div className="flex justify-center p-12">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
          </div>
        ) : cases.length === 0 ? (
          <Card className="p-12 text-center rounded-2xl border-dashed border-border/70 bg-muted/20">
            <FolderOpen className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
            <p className="text-muted-foreground">No cases found for the selected filters.</p>
          </Card>
        ) : (
          cases.map((c) => (
            <Card
              key={c.id}
              className="p-5 rounded-2xl border-border/70 bg-card/50 hover:bg-card/80 transition-all shadow-sm cursor-pointer group"
              onClick={() =>
                navigate(`/admin/org/${encodeURIComponent(organizationId)}/cases/${encodeURIComponent(c.id)}`)
              }
            >
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div className="flex items-start gap-4">
                  <div className="h-10 w-10 rounded-xl bg-primary/10 flex items-center justify-center shrink-0">
                    <FolderOpen className="h-5 w-5 text-primary" />
                  </div>
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2 mb-1">
                      <span className="text-sm font-bold font-mono">{c.case_id}</span>
                      <Badge
                        variant="outline"
                        className={`rounded-full text-[10px] font-bold uppercase tracking-widest ${statusColor(c.status)}`}
                      >
                        {c.status.replace(/_/g, " ")}
                      </Badge>
                      <Badge className={`rounded-full text-[10px] font-bold uppercase ${priorityColor(c.priority)}`}>
                        {c.priority}
                      </Badge>
                    </div>
                    <p className="text-sm font-semibold">{c.applicant_name}</p>
                    <p className="text-xs text-muted-foreground">{c.applicant_email}</p>
                    <p className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground mt-1">
                      {c.application_type.replace(/_/g, " ")}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-4 text-xs text-muted-foreground ml-14 md:ml-0">
                  {c.fraud_risk_score != null && (
                    <div className="text-right hidden xl:block">
                      <p className="text-[10px] font-bold uppercase tracking-widest mb-0.5">Risk Score</p>
                      <p className={`font-bold text-sm ${c.fraud_risk_score > 60 ? "text-rose-600" : "text-emerald-600"}`}>
                        {c.fraud_risk_score.toFixed(1)}%
                      </p>
                    </div>
                  )}
                  <ChevronRight className="h-4 w-4 text-muted-foreground/40 group-hover:text-primary transition-colors" />
                </div>
              </div>
            </Card>
          ))
        )}
      </div>
    </div>
  );
};

export default OrgCasesPage;
