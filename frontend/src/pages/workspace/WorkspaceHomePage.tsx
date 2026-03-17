import React, { useCallback, useEffect, useState } from "react";
import {
  FolderOpen,
  Users,
  Workflow,
  ShieldCheck,
  RefreshCw,
  ChevronRight,
  AlertCircle,
  Clock,
} from "lucide-react";
import { useNavigate } from "react-router-dom";
import { toast } from "react-toastify";

import { useAuth } from "@/hooks/useAuth";
import { governanceService } from "@/services/governance.service";
import type { GovernanceOrganizationSummaryResponse } from "@/types";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { getWorkspacePath } from "@/utils/appPaths";

const WorkspaceHomePage: React.FC = () => {
  const navigate = useNavigate();
  const { activeOrganization } = useAuth();
  const [summary, setSummary] = useState<GovernanceOrganizationSummaryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const loadData = useCallback(async (isSilent = false) => {
    if (!isSilent) setLoading(true);
    else setRefreshing(true);

    try {
      const data = await governanceService.getOrganizationSummary();
      setSummary(data);
    } catch {
      toast.error("Failed to load workspace data");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-primary mb-1">
            {activeOrganization?.name || "Organization"}
          </p>
          <h1 className="text-3xl font-bold tracking-tight">Workspace</h1>
          <p className="text-muted-foreground mt-1 text-sm">
            Your vetting operations hub — cases, campaigns, interviews, and documents.
          </p>
        </div>
        <Button
          variant="outline"
          className="rounded-xl gap-2 bg-card/50"
          onClick={() => void loadData(true)}
          disabled={refreshing}
        >
          <RefreshCw className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`} />
          Refresh
        </Button>
      </div>

      {/* Pulse Metrics */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="p-5 rounded-2xl border-border/70 bg-card/50 shadow-sm backdrop-blur-sm">
          <div className="flex items-center gap-4">
            <div className="h-10 w-10 rounded-xl bg-primary/10 text-primary flex items-center justify-center">
              <FolderOpen className="h-5 w-5" />
            </div>
            <div>
              <p className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">Active Members</p>
              <p className="text-2xl font-bold">
                {loading ? "—" : (summary?.stats.members_active ?? 0)}
              </p>
            </div>
          </div>
        </Card>
        <Card className="p-5 rounded-2xl border-border/70 bg-card/50 shadow-sm backdrop-blur-sm">
          <div className="flex items-center gap-4">
            <div className="h-10 w-10 rounded-xl bg-indigo-500/10 text-indigo-500 flex items-center justify-center">
              <Workflow className="h-5 w-5" />
            </div>
            <div>
              <p className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">Committees</p>
              <p className="text-2xl font-bold">
                {loading ? "—" : (summary?.stats.committees_active ?? 0)}
              </p>
            </div>
          </div>
        </Card>
        <Card className="p-5 rounded-2xl border-border/70 bg-card/50 shadow-sm backdrop-blur-sm">
          <div className="flex items-center gap-4">
            <div className="h-10 w-10 rounded-xl bg-emerald-500/10 text-emerald-500 flex items-center justify-center">
              <Users className="h-5 w-5" />
            </div>
            <div>
              <p className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">Active Staff</p>
              <p className="text-2xl font-bold">
                {loading ? "—" : (summary?.stats.members_active ?? 0)}
              </p>
            </div>
          </div>
        </Card>
        <Card className="p-5 rounded-2xl border-border/70 bg-card/50 shadow-sm backdrop-blur-sm">
          <div className="flex items-center gap-4">
            <div className="h-10 w-10 rounded-xl bg-amber-500/10 text-amber-500 flex items-center justify-center">
              <ShieldCheck className="h-5 w-5" />
            </div>
            <div>
              <p className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">Chairs</p>
              <p className="text-2xl font-bold">
                {loading ? "—" : (summary?.stats.active_chairs ?? 0)}
              </p>
            </div>
          </div>
        </Card>
      </div>

      {/* Quick Navigation */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {[
          {
            label: "Applications",
            description: "Review and process vetting applications",
            path: getWorkspacePath("applications"),
            icon: FolderOpen,
            color: "text-primary bg-primary/10",
          },
          {
            label: "Campaigns",
            description: "Manage active vetting campaigns",
            path: getWorkspacePath("campaigns"),
            icon: Workflow,
            color: "text-indigo-500 bg-indigo-500/10",
          },
          {
            label: "Audit Logs",
            description: "Review activity and compliance trail",
            path: getWorkspacePath("audit-logs"),
            icon: Clock,
            color: "text-amber-500 bg-amber-500/10",
          },
          {
            label: "Fraud Insights",
            description: "AI-flagged risk indicators and patterns",
            path: getWorkspacePath("fraud-insights"),
            icon: AlertCircle,
            color: "text-rose-500 bg-rose-500/10",
          },
          {
            label: "Background Checks",
            description: "Track background verification status",
            path: getWorkspacePath("background-checks"),
            icon: ShieldCheck,
            color: "text-emerald-500 bg-emerald-500/10",
          },
          {
            label: "Video Calls",
            description: "Scheduled interview and review sessions",
            path: getWorkspacePath("video-calls"),
            icon: Users,
            color: "text-blue-500 bg-blue-500/10",
          },
        ].map((item) => (
          <Card
            key={item.path}
            className="p-5 rounded-2xl border-border/70 bg-card/50 hover:bg-card/80 transition-all shadow-sm cursor-pointer group"
            onClick={() => navigate(item.path)}
          >
            <div className="flex items-start justify-between">
              <div className="flex items-start gap-4">
                <div className={`h-10 w-10 rounded-xl flex items-center justify-center shrink-0 ${item.color}`}>
                  <item.icon className="h-5 w-5" />
                </div>
                <div>
                  <p className="text-sm font-bold">{item.label}</p>
                  <p className="text-xs text-muted-foreground mt-0.5">{item.description}</p>
                </div>
              </div>
              <ChevronRight className="h-4 w-4 text-muted-foreground/40 group-hover:text-primary transition-colors mt-1 shrink-0" />
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
};

export default WorkspaceHomePage;
