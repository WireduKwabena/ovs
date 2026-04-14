import React, { useEffect, useState, useCallback } from 'react';
import {
  ShieldCheck,
  ExternalLink,
  Zap,
  Globe,
  Settings,
  RefreshCw,
  Info,
  Package,
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
    { name: 'Starter', price: '$149/mo', description: 'Up to 150 candidates/month, 10 seats', icon: Package },
    { name: 'Growth', price: '$399/mo', description: 'Up to 600 candidates/month, 30 seats', icon: Zap },
    { name: 'Enterprise', price: '$999/mo', description: 'Unlimited candidates, custom seats', icon: ShieldCheck },
    { name: 'Government', price: 'Custom', description: 'Subsidized tier for public institutions', icon: Globe },
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
        </div>
      </div>

      {/* Revenue Metrics Note */}
      <Card className="p-5 rounded-2xl border-blue-500/20 bg-blue-500/5 shadow-sm">
        <div className="flex items-start gap-4">
          <Info className="h-5 w-5 text-blue-500 mt-0.5 shrink-0" />
          <div>
            <h3 className="text-sm font-bold text-blue-700">Revenue Metrics via Stripe Dashboard</h3>
            <p className="text-xs text-blue-600 mt-1">
              Platform-wide MRR, subscription counts, failed payments, and ARPU are available directly in the Stripe Dashboard.
              Per-tenant subscription health is visible in each organization&apos;s workspace.
            </p>
            <a
              href="https://dashboard.stripe.com"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 mt-2 text-xs font-bold text-blue-700 underline hover:text-blue-900"
            >
              <ExternalLink className="h-3 w-3" />
              Open Stripe Dashboard
            </a>
          </div>
        </div>
      </Card>

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
                  <Settings className="h-4 w-4 text-muted-foreground mt-1" />
                </div>
                <div className="mt-6">
                  <h3 className="text-xl font-bold">{plan.name}</h3>
                  <p className="text-2xl font-bold mt-1 text-primary">{plan.price}</p>
                  <p className="text-xs text-muted-foreground mt-2 font-medium">{plan.description}</p>
                </div>
                <div className="mt-6 pt-6 border-t border-border/50">
                  <Badge className="bg-emerald-500/10 text-emerald-500 rounded-full border-emerald-500/20">Active</Badge>
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
