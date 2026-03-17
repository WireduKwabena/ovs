import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  ShieldCheck,
  Activity,
  Brain,
  CreditCard,
  RefreshCw,
  ChevronRight,
  Zap,
  Lock,
  Globe,
  TrendingUp,
  AlertCircle,
  Building2,
  Power,
} from "lucide-react";
import { Link } from "react-router-dom";
import { toast } from "react-toastify";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { governanceService } from "@/services/governance.service";
import type { GovernancePlatformOrganizationOversight } from "@/types";
import BillingHealthCard from "@/components/admin/BillingHealthCard";

const growthData = [
  { month: "Oct", orgs: 120, revenue: 85000 },
  { month: "Nov", orgs: 132, revenue: 92000 },
  { month: "Dec", orgs: 145, revenue: 105000 },
  { month: "Jan", orgs: 168, revenue: 118000 },
  { month: "Feb", orgs: 186, revenue: 124500 },
];

const PlatformDashboardPage: React.FC = () => {
  const [organizations, setOrganizations] = useState<GovernancePlatformOrganizationOversight[]>([]);
  const [, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [updatingId, setUpdatingId] = useState<string | null>(null);

  const loadDashboardData = useCallback(async (isSilent = false) => {
    if (!isSilent) setLoading(true);
    else setRefreshing(true);

    try {
      const orgPayload = await governanceService.listPlatformOrganizations();
      setOrganizations(Array.isArray(orgPayload.results) ? orgPayload.results : []);
    } catch {
      toast.error("Failed to sync platform metrics.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void loadDashboardData();
  }, [loadDashboardData]);

  const handleToggleOrgStatus = async (org: GovernancePlatformOrganizationOversight) => {
    setUpdatingId(org.id);
    try {
      const updated = await governanceService.updatePlatformOrganizationStatus(org.id, {
        is_active: !org.is_active,
      });
      setOrganizations((prev) => prev.map((o) => (o.id === org.id ? updated : o)));
      toast.success(`${org.name} ${updated.is_active ? "activated" : "deactivated"}`);
    } catch {
      toast.error("Failed to update organization status");
    } finally {
      setUpdatingId(null);
    }
  };

  const stats = useMemo(() => {
    return {
      totalOrgs: organizations.length,
      activeOrgs: organizations.filter((o) => o.is_active).length,
      premiumOrgs: organizations.filter((o) => o.subscription?.source === "active").length,
      totalStaff: organizations.reduce((acc, o) => acc + (o.active_member_count || 0), 0),
      needsAttention: organizations.filter((o) => !o.is_active || !o.subscription).length,
    };
  }, [organizations]);

  return (
    <div className="space-y-8">
      {/* Platform Header */}
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Command Center</h1>
          <p className="text-muted-foreground mt-1 text-sm md:text-base">
            Macro-oversight of the OVS Redo multi-tenant ecosystem and infrastructure health.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Button
            variant="outline"
            className="rounded-xl gap-2 bg-card/50 backdrop-blur-sm"
            onClick={() => void loadDashboardData(true)}
            disabled={refreshing}
          >
            <RefreshCw className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`} />
            Sync Platform
          </Button>
        </div>
      </div>

      {/* High-Level Pulse Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="p-5 rounded-2xl border-border/70 bg-card/50 shadow-sm backdrop-blur-sm">
          <div className="flex items-center gap-4">
            <div className="h-10 w-10 rounded-xl bg-primary/10 text-primary flex items-center justify-center">
              <Globe className="h-5 w-5" />
            </div>
            <div>
              <p className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">
                Registered Tenants
              </p>
              <p className="text-2xl font-bold">{stats.totalOrgs}</p>
            </div>
          </div>
        </Card>
        <Card className="p-5 rounded-2xl border-border/70 bg-card/50 shadow-sm backdrop-blur-sm">
          <div className="flex items-center gap-4">
            <div className="h-10 w-10 rounded-xl bg-emerald-500/10 text-emerald-500 flex items-center justify-center">
              <ShieldCheck className="h-5 w-5" />
            </div>
            <div>
              <p className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">
                Active Nodes
              </p>
              <p className="text-2xl font-bold">{stats.activeOrgs}</p>
            </div>
          </div>
        </Card>
        <Card className="p-5 rounded-2xl border-border/70 bg-card/50 shadow-sm backdrop-blur-sm">
          <div className="flex items-center gap-4">
            <div className="h-10 w-10 rounded-xl bg-indigo-500/10 text-indigo-500 flex items-center justify-center">
              <Brain className="h-5 w-5" />
            </div>
            <div>
              <p className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">
                Global Staff Capacity
              </p>
              <p className="text-2xl font-bold">{stats.totalStaff}</p>
            </div>
          </div>
        </Card>
        <Card className="p-5 rounded-2xl border-border/70 bg-card/50 shadow-sm backdrop-blur-sm">
          <div className="flex items-center gap-4">
            <div className="h-10 w-10 rounded-xl bg-amber-500/10 text-amber-500 flex items-center justify-center">
              <TrendingUp className="h-5 w-5" />
            </div>
            <div>
              <p className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">
                Growth Index
              </p>
              <p className="text-2xl font-bold">+12.4%</p>
            </div>
          </div>
        </Card>
      </div>

      {/* Billing Health */}
      <BillingHealthCard />

      {/* Organization Subscription Oversight */}
      <Card className="p-6 rounded-2xl border-border/70 bg-card/50 shadow-sm backdrop-blur-sm">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-lg font-bold">Organization Subscription Oversight</h2>
            <p className="text-xs text-muted-foreground mt-0.5">
              Monitor and manage the lifecycle of all registered organizations.
            </p>
          </div>
          <div className="flex items-center gap-4 text-xs text-muted-foreground">
            <span>
              <span className="font-bold text-emerald-600">{stats.premiumOrgs}</span>
              {" "}Active Subscriptions
            </span>
            <span>
              <span className="font-bold text-amber-600">{stats.needsAttention}</span>
              {" "}Needs Attention
            </span>
          </div>
        </div>

        <div className="space-y-3">
          {organizations.map((org) => (
            <div
              key={org.id}
              className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-4 rounded-xl border border-border/50 bg-background/30 hover:bg-background/60 transition-all"
            >
              <div className="flex items-center gap-4">
                <div className="h-10 w-10 rounded-xl bg-primary/10 flex items-center justify-center shrink-0">
                  <Building2 className="h-5 w-5 text-primary" />
                </div>
                <div>
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm font-bold">{org.name}</span>
                    <Badge
                      variant="outline"
                      className="rounded-full text-[10px] font-bold uppercase tracking-widest"
                    >
                      {org.organization_type}
                    </Badge>
                    {org.is_active ? (
                      <Badge className="bg-emerald-500/10 text-emerald-500 hover:bg-emerald-500/10 rounded-full border-emerald-500/20 text-[10px]">
                        Active
                      </Badge>
                    ) : (
                      <Badge className="bg-rose-500/10 text-rose-500 hover:bg-rose-500/10 rounded-full border-rose-500/20 text-[10px]">
                        Deactivated
                      </Badge>
                    )}
                  </div>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    {org.active_member_count} staff · {org.subscription?.plan_name || "Free Tier"}
                  </p>
                </div>
              </div>
              <Button
                variant={org.is_active ? "outline" : "default"}
                className="rounded-xl gap-2 h-9 text-xs font-bold self-end md:self-auto"
                disabled={updatingId === org.id}
                aria-label={org.is_active ? "Deactivate Organization" : "Reactivate Organization"}
                onClick={() => handleToggleOrgStatus(org)}
              >
                <Power className="h-3.5 w-3.5" />
                {updatingId === org.id
                  ? "Updating..."
                  : org.is_active
                    ? "Deactivate"
                    : "Reactivate"}
              </Button>
            </div>
          ))}
        </div>
      </Card>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-8">
        {/* Growth & Revenue Trends */}
        <div className="xl:col-span-2 space-y-6">
          <Card className="p-6 rounded-[2rem] border-border/70 bg-card/50 shadow-sm backdrop-blur-sm">
            <div className="flex items-center justify-between mb-8">
              <div>
                <h2 className="text-lg font-bold">Ecosystem Expansion</h2>
                <p className="text-xs text-muted-foreground">
                  Tenant acquisition and revenue trajectory.
                </p>
              </div>
              <Badge variant="outline" className="rounded-full">
                L5M Overview
              </Badge>
            </div>
            <div className="space-y-2">
              {growthData.map((item) => (
                <div key={item.month} className="flex items-center justify-between p-2 rounded-lg bg-background/50 border border-border/30">
                  <span className="text-xs font-medium">{item.month}</span>
                  <span className="text-xs font-bold">{item.orgs} orgs</span>
                </div>
              ))}
            </div>
          </Card>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <Card className="p-6 rounded-[2rem] border-border/70 bg-card/50 shadow-sm">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-bold flex items-center gap-2">
                  <Activity className="h-4 w-4 text-primary" />
                  Infrastructure Health
                </h3>
                <Link
                  to="/admin/platform/health"
                  className="text-[10px] font-bold uppercase tracking-widest text-primary hover:underline"
                >
                  Full Telemetry
                </Link>
              </div>
              <div className="space-y-3">
                <div className="flex items-center justify-between p-3 rounded-xl bg-emerald-500/5 border border-emerald-500/10">
                  <span className="text-xs font-medium">Core API Gateway</span>
                  <Badge className="bg-emerald-500/10 text-emerald-500 border-emerald-500/20 text-[9px]">
                    Operational
                  </Badge>
                </div>
                <div className="flex items-center justify-between p-3 rounded-xl bg-emerald-500/5 border border-emerald-500/10">
                  <span className="text-xs font-medium">AI Inference Mesh</span>
                  <Badge className="bg-emerald-500/10 text-emerald-500 border-emerald-500/20 text-[9px]">
                    Operational
                  </Badge>
                </div>
                <div className="flex items-center justify-between p-3 rounded-xl bg-amber-500/5 border border-amber-500/10">
                  <span className="text-xs font-medium">Background Task Queue</span>
                  <Badge className="bg-amber-500/10 text-amber-500 border-amber-500/20 text-[9px]">
                    Load: Moderate
                  </Badge>
                </div>
              </div>
            </Card>

            <Card className="p-6 rounded-[2rem] border-border/70 bg-card/50 shadow-sm">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-bold flex items-center gap-2">
                  <Lock className="h-4 w-4 text-indigo-500" />
                  Recent Platform Audit
                </h3>
                <Link
                  to="/admin/platform/logs"
                  className="text-[10px] font-bold uppercase tracking-widest text-primary hover:underline"
                >
                  View Logs
                </Link>
              </div>
              <div className="space-y-4">
                {[
                  { action: "Org Provisioned", target: "Ministry of Health", time: "2h ago" },
                  { action: "Billing Updated", target: "Standard Plan", time: "5h ago" },
                  { action: "AI Policy Changed", target: "Confidence Floor", time: "1d ago" },
                ].map((log, i) => (
                  <div key={i} className="flex items-start gap-3">
                    <div className="h-1.5 w-1.5 rounded-full bg-primary mt-1.5 shrink-0" />
                    <div>
                      <p className="text-xs font-bold">{log.action}</p>
                      <p className="text-[10px] text-muted-foreground">
                        {log.target} · {log.time}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          </div>
        </div>

        {/* Action Center Sidebar */}
        <div className="xl:col-span-1 space-y-6">
          <Card className="p-6 rounded-[2.5rem] border-border/70 bg-indigo-600 text-white shadow-xl relative overflow-hidden group">
            <div className="absolute top-[-20%] right-[-20%] h-[60%] w-[60%] rounded-full bg-white/10 blur-[60px] group-hover:bg-white/20 transition-all duration-500" />
            <div className="relative z-10">
              <Zap className="h-8 w-8 mb-4 text-indigo-200" />
              <h2 className="text-xl font-bold mb-2">Platform Actions</h2>
              <p className="text-sm text-indigo-100 mb-6 leading-relaxed">
                Quick access to high-impact administrative utilities and provisioning tools.
              </p>
              <div className="space-y-2">
                <Link
                  to="/admin/platform/registry"
                  className="flex items-center justify-between w-full p-4 rounded-2xl bg-white/10 hover:bg-white/20 transition-all group/btn border border-white/5"
                >
                  <span className="text-sm font-bold">Provision New Tenant</span>
                  <ChevronRight className="h-4 w-4 transition-transform group-hover/btn:translate-x-1" />
                </Link>
                <Link
                  to="/admin/platform/billing"
                  className="flex items-center justify-between w-full p-4 rounded-2xl bg-white/10 hover:bg-white/20 transition-all group/btn border border-white/5"
                >
                  <span className="text-sm font-bold">Manage Billing Plans</span>
                  <ChevronRight className="h-4 w-4 transition-transform group-hover/btn:translate-x-1" />
                </Link>
                <Link
                  to="/admin/platform/ai-engine"
                  className="flex items-center justify-between w-full p-4 rounded-2xl bg-white/10 hover:bg-white/20 transition-all group/btn border border-white/5"
                >
                  <span className="text-sm font-bold">Global AI Safety Policy</span>
                  <ChevronRight className="h-4 w-4 transition-transform group-hover/btn:translate-x-1" />
                </Link>
              </div>
            </div>
          </Card>

          <Card className="p-6 rounded-[2rem] border-border/70 bg-card/50 shadow-sm backdrop-blur-sm">
            <h3 className="text-sm font-bold flex items-center gap-2 mb-4">
              <AlertCircle className="h-4 w-4 text-amber-500" />
              System Alerts
            </h3>
            <div className="p-4 rounded-2xl bg-emerald-500/5 border border-emerald-500/10 flex items-center gap-3">
              <ShieldCheck className="h-5 w-5 text-emerald-500" />
              <p className="text-xs font-medium text-emerald-600">No active system alerts.</p>
            </div>
          </Card>

          <Card className="p-6 rounded-[2rem] border-border/70 bg-card/50 shadow-sm backdrop-blur-sm">
            <div className="flex items-center gap-3 mb-2">
              <CreditCard className="h-5 w-5 text-muted-foreground" />
              <h3 className="text-sm font-bold">Billing Posture</h3>
            </div>
            <div className="space-y-3 mt-4">
              <div className="flex items-center justify-between text-xs">
                <span className="text-muted-foreground">Premium Plans</span>
                <span className="font-bold">{stats.premiumOrgs}</span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-muted-foreground">Trialing Tenants</span>
                <span className="font-bold">{stats.totalOrgs - stats.premiumOrgs}</span>
              </div>
              <div className="pt-3 border-t border-border/50">
                <p className="text-[10px] font-bold text-muted-foreground uppercase mb-1">
                  Global ARPU
                </p>
                <p className="text-xl font-bold text-primary">$669.35</p>
              </div>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
};

export default PlatformDashboardPage;
