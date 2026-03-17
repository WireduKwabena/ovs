import React, { useEffect, useState, useCallback } from 'react';
import {
  CreditCard,
  ShieldCheck,
  AlertTriangle,
  ExternalLink,
  BarChart3,
  Zap,
  Globe,
  Settings,
  RefreshCw,
  TrendingUp,
  Package,
  Plus
} from 'lucide-react';
import { toast } from 'react-toastify';
import { billingService, type BillingHealthResponse } from '@/services/billing.service';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

export const BillingManagementPage: React.FC = () => {
  const [health, setHealth] = useState<BillingHealthResponse | null>(null);
  const [, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const fetchBillingHealth = useCallback(async (isSilent = false) => {
    if (!isSilent) setLoading(true);
    else setRefreshing(true);

    try {
      const data = await billingService.getHealth();
      setHealth(data);
    } catch {
      toast.error('Failed to sync billing infrastructure status');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void fetchBillingHealth();
  }, [fetchBillingHealth]);

  const plans = [
    { name: 'Standard', price: '$49/mo', organizations: 124, status: 'Active', icon: Package },
    { name: 'Professional', price: '$199/mo', organizations: 42, status: 'Active', icon: Zap },
    { name: 'Enterprise', price: 'Custom', organizations: 12, status: 'Active', icon: ShieldCheck },
    { name: 'Government (Tier 1)', price: 'Subsidized', organizations: 8, status: 'Active', icon: Globe },
  ];

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Billing & Plans</h1>
          <p className="text-muted-foreground mt-1 text-sm md:text-base">
            Platform-wide revenue operations, subscription plans, and gateway health.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Button 
            variant="outline" 
            className="rounded-xl gap-2"
            onClick={() => void fetchBillingHealth(true)}
            disabled={refreshing}
          >
            <RefreshCw className={`h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} />
            Refresh Gateway
          </Button>
          <Button className="rounded-xl gap-2 shadow-lg">
            <Plus className="h-4 w-4" />
            Create Plan
          </Button>
        </div>
      </div>

      {/* Financial Metrics Summary */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <Card className="p-6 rounded-2xl border-border/70 bg-card/50 shadow-sm backdrop-blur-sm">
          <div className="flex items-center gap-4">
            <div className="h-10 w-10 rounded-xl bg-emerald-500/10 text-emerald-500 flex items-center justify-center">
              <TrendingUp className="h-5 w-5" />
            </div>
            <div>
              <p className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">Monthly Revenue</p>
              <p className="text-xl font-bold">$124,500.00</p>
            </div>
          </div>
        </Card>
        <Card className="p-6 rounded-2xl border-border/70 bg-card/50 shadow-sm backdrop-blur-sm">
          <div className="flex items-center gap-4">
            <div className="h-10 w-10 rounded-xl bg-blue-500/10 text-blue-500 flex items-center justify-center">
              <CreditCard className="h-5 w-5" />
            </div>
            <div>
              <p className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">Active Subscriptions</p>
              <p className="text-xl font-bold">186</p>
            </div>
          </div>
        </Card>
        <Card className="p-6 rounded-2xl border-border/70 bg-card/50 shadow-sm backdrop-blur-sm">
          <div className="flex items-center gap-4">
            <div className="h-10 w-10 rounded-xl bg-amber-500/10 text-amber-500 flex items-center justify-center">
              <AlertTriangle className="h-5 w-5" />
            </div>
            <div>
              <p className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">Failed Payments</p>
              <p className="text-xl font-bold">4</p>
            </div>
          </div>
        </Card>
        <Card className="p-6 rounded-2xl border-border/70 bg-card/50 shadow-sm backdrop-blur-sm">
          <div className="flex items-center gap-4">
            <div className="h-10 w-10 rounded-xl bg-primary/10 text-primary flex items-center justify-center">
              <BarChart3 className="h-5 w-5" />
            </div>
            <div>
              <p className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">ARPU</p>
              <p className="text-xl font-bold">$669.35</p>
            </div>
          </div>
        </Card>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-8">
        {/* Gateway Health Status */}
        <div className="xl:col-span-1 space-y-6">
          <h2 className="text-lg font-bold flex items-center gap-2">
            <Settings className="h-5 w-5 text-muted-foreground" />
            Infrastructure Gateway
          </h2>
          
          <Card className="p-6 rounded-4xl border-border/70 bg-card/50 shadow-sm backdrop-blur-sm">
            <div className="space-y-4">
              <div className="flex items-center justify-between pb-4 border-b border-border/50">
                <span className="text-sm font-medium">Stripe Connectivity</span>
                {health?.stripe.sdk_installed ? (
                  <Badge className="bg-emerald-500/10 text-emerald-500 rounded-full border-emerald-500/20">Operational</Badge>
                ) : (
                  <Badge variant="destructive">Disconnected</Badge>
                )}
              </div>
              
              <div className="space-y-3">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-muted-foreground">SDK Initialized</span>
                  <span className={health?.stripe.sdk_installed ? 'text-emerald-500' : 'text-rose-500'}>
                    {health?.stripe.sdk_installed ? 'SUCCESS' : 'FAILURE'}
                  </span>
                </div>
                <div className="flex items-center justify-between text-xs">
                  <span className="text-muted-foreground">Secret Key Configuration</span>
                  <span className={health?.stripe.secret_key_configured ? 'text-emerald-500' : 'text-rose-500'}>
                    {health?.stripe.secret_key_configured ? 'VALID' : 'MISSING'}
                  </span>
                </div>
                <div className="flex items-center justify-between text-xs">
                  <span className="text-muted-foreground">Webhook Security</span>
                  <span className={health?.stripe.webhook_secret_configured ? 'text-emerald-500' : 'text-rose-500'}>
                    {health?.stripe.webhook_secret_configured ? 'ACTIVE' : 'INSECURE'}
                  </span>
                </div>
              </div>

              {health?.paystack && (
                <div className="pt-4 mt-4 border-t border-border/50 space-y-3">
                  <div className="flex items-center justify-between text-sm font-medium mb-1">
                    <span>Paystack (Secondary)</span>
                    <Badge variant="outline" className="rounded-full">Nigeria/Africa</Badge>
                  </div>
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-muted-foreground">Key Configuration</span>
                    <span className={health.paystack.secret_key_configured ? 'text-emerald-500' : 'text-rose-500'}>
                      {health.paystack.secret_key_configured ? 'VALID' : 'MISSING'}
                    </span>
                  </div>
                </div>
              )}
            </div>
          </Card>

          <Card className="p-6 rounded-4xl border-border/70 bg-card/50 shadow-sm backdrop-blur-sm">
             <div className="flex items-start gap-3">
                <Globe className="h-5 w-5 text-primary mt-1" />
                <div>
                   <h3 className="text-sm font-bold">Exchange Rates</h3>
                   <p className="text-[11px] text-muted-foreground mt-1">
                     Fallback rate: {health?.exchange_rate?.fallback_rate ?? 1.0}
                   </p>
                   <p className="text-[11px] text-muted-foreground">
                     Cache TTL: {health?.exchange_rate?.cache_ttl_seconds ?? 0}s
                   </p>
                </div>
             </div>
          </Card>
        </div>

        {/* Plan Orchestration */}
        <div className="xl:col-span-2 space-y-6">
          <h2 className="text-lg font-bold flex items-center gap-2">
            <Package className="h-5 w-5 text-muted-foreground" />
            Plan Management
          </h2>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {plans.map((plan) => (
              <Card key={plan.name} className="p-6 rounded-4xl border-border/70 bg-card/50 hover:bg-card/80 transition-all shadow-sm">
                <div className="flex items-start justify-between">
                  <div className="h-12 w-12 rounded-2xl bg-primary/10 text-primary flex items-center justify-center">
                    <plan.icon className="h-6 w-6" />
                  </div>
                  <Button variant="ghost" size="icon" className="rounded-full">
                    <Settings className="h-4 w-4" />
                  </Button>
                </div>
                
                <div className="mt-6">
                  <h3 className="text-xl font-bold">{plan.name}</h3>
                  <p className="text-2xl font-bold mt-1 text-primary">{plan.price}</p>
                  <p className="text-xs text-muted-foreground mt-2 font-medium">
                    Currently powering <span className="text-foreground">{plan.organizations}</span> organizations
                  </p>
                </div>

                <div className="mt-6 pt-6 border-t border-border/50 flex items-center justify-between">
                  <Badge className="bg-emerald-500/10 text-emerald-500 rounded-full border-emerald-500/20">{plan.status}</Badge>
                  <Button variant="link" className="h-auto p-0 text-xs font-bold uppercase tracking-widest gap-1">
                    Manage Limits <ExternalLink className="h-3 w-3" />
                  </Button>
                </div>
              </Card>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

export default BillingManagementPage;
