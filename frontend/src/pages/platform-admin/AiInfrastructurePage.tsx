import React, { useEffect, useState, useCallback } from 'react';
import {
  Brain,
  RefreshCw,
  ShieldCheck,
  AlertTriangle,
  Server,
  Zap,
  Info,
  Monitor,
  CheckCircle2,
  XCircle,
} from 'lucide-react';
import { toast } from 'react-toastify';
import { aiMonitorService } from '@/services/aiMonitor.service';
import type { AiMonitorHealthResponse } from '@/types';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

const MODEL_REGISTRY = [
  { name: 'Authenticity Detector', key: 'authenticity', description: 'Face + document liveness scoring' },
  { name: 'Fraud Classifier', key: 'fraud', description: 'Behavioral anomaly detection' },
  { name: 'Signature Verifier', key: 'signature', description: 'Handwriting authenticity' },
  { name: 'Document Classifier', key: 'document', description: 'RVL-CDIP / MIDV-500 document type' },
  { name: 'Non-Verbal Analyzer', key: 'nonverbal', description: 'Facial expression & sentiment' },
];

const AI_SAFETY_FLAGS = [
  { name: 'Strict Document Type Check', enabled: true },
  { name: 'Deepfake Probability Scan', enabled: true },
  { name: 'Social Advisory Engine', enabled: false },
  { name: 'Cross-Tenant Similarity Detect', enabled: true },
];

export const AiInfrastructurePage: React.FC = () => {
  const [health, setHealth] = useState<AiMonitorHealthResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const fetchAiHealth = useCallback(async (isSilent = false) => {
    if (!isSilent) setLoading(true);
    else setRefreshing(true);

    try {
      const data = await aiMonitorService.health({ model_name: 'default' });
      setHealth(data);
    } catch {
      toast.error('Failed to sync AI infrastructure status');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void fetchAiHealth();
  }, [fetchAiHealth]);

  const isHealthy = health?.monitor?.enabled ?? false;

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Monitor className="h-4 w-4 text-primary" />
            <span className="text-[10px] font-bold uppercase tracking-[0.2em] text-muted-foreground">Platform Engine</span>
          </div>
          <h1 className="text-3xl font-bold tracking-tight">AI Infrastructure</h1>
          <p className="text-muted-foreground mt-1 text-sm md:text-base">
            Macro-oversight of inference runtimes, model availability, and global AI safety controls.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Button
            variant="outline"
            className="rounded-xl gap-2"
            onClick={() => void fetchAiHealth(true)}
            disabled={refreshing}
          >
            <RefreshCw className={`h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} />
            Sync Models
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-8">
        {/* Model Registry + Health */}
        <div className="xl:col-span-2 space-y-6">
          <h2 className="text-lg font-bold flex items-center gap-2">
            <Server className="h-5 w-5 text-muted-foreground" />
            Model Registry
          </h2>

          <Card className="p-6 rounded-4xl border-border/70 bg-card/50 shadow-sm backdrop-blur-sm">
            {loading ? (
              <div className="flex items-center justify-center h-32">
                <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
              </div>
            ) : (
              <div className="divide-y divide-border/50">
                {MODEL_REGISTRY.map((model) => (
                  <div key={model.key} className="flex items-center justify-between py-3 first:pt-0 last:pb-0">
                    <div className="flex items-center gap-3">
                      <div className="h-8 w-8 rounded-lg bg-primary/10 text-primary flex items-center justify-center shrink-0">
                        <Brain className="h-4 w-4" />
                      </div>
                      <div>
                        <p className="text-sm font-semibold">{model.name}</p>
                        <p className="text-xs text-muted-foreground">{model.description}</p>
                      </div>
                    </div>
                    <Badge className="bg-emerald-500/10 text-emerald-500 rounded-full border-emerald-500/20 shrink-0">
                      Loaded
                    </Badge>
                  </div>
                ))}
              </div>
            )}
          </Card>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {health && (
              <Card className="p-5 rounded-2xl border-border/70 bg-card/50 shadow-sm backdrop-blur-sm">
                <div className="flex items-center gap-3 mb-4">
                  <div className="h-10 w-10 rounded-xl bg-indigo-500/10 text-indigo-500 flex items-center justify-center">
                    <Brain className="h-5 w-5" />
                  </div>
                  <div>
                    <h3 className="text-sm font-bold">Monitor Router</h3>
                    <p className="text-[10px] font-bold text-muted-foreground uppercase">{health.model_name}</p>
                  </div>
                  {isHealthy ? (
                    <Badge className="ml-auto bg-emerald-500/10 text-emerald-500 rounded-full border-emerald-500/20">Active</Badge>
                  ) : (
                    <Badge variant="destructive" className="ml-auto rounded-full">Offline</Badge>
                  )}
                </div>
                <div className="space-y-2">
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-muted-foreground">Backend Engine</span>
                    <span className="font-mono">{health.monitor.backend}</span>
                  </div>
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-muted-foreground">Redis Cache</span>
                    <span className={health.monitor.redis_configured ? 'text-emerald-500 font-bold' : 'text-amber-500 font-bold'}>
                      {health.monitor.redis_configured ? 'ENABLED' : 'DISABLED'}
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-muted-foreground">Total Models</span>
                    <span className="font-bold">{MODEL_REGISTRY.length}</span>
                  </div>
                </div>
              </Card>
            )}

            <Card className="p-5 rounded-2xl border-border/70 bg-card/50 shadow-sm backdrop-blur-sm">
              <div className="flex items-center gap-3 mb-4">
                <div className="h-10 w-10 rounded-xl bg-primary/10 text-primary flex items-center justify-center">
                  <Zap className="h-5 w-5" />
                </div>
                <div>
                  <h3 className="text-sm font-bold">AI Advisory Mode</h3>
                  <p className="text-[10px] font-bold text-muted-foreground uppercase">Human-in-the-loop</p>
                </div>
              </div>
              <div className="space-y-2">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-muted-foreground">Auto-finalize decisions</span>
                  <span className="text-rose-500 font-bold">DISABLED</span>
                </div>
                <div className="flex items-center justify-between text-xs">
                  <span className="text-muted-foreground">Override logging</span>
                  <span className="text-emerald-500 font-bold">ACTIVE</span>
                </div>
                <div className="flex items-center justify-between text-xs">
                  <span className="text-muted-foreground">Audit trail</span>
                  <span className="text-emerald-500 font-bold">ENFORCED</span>
                </div>
              </div>
            </Card>
          </div>

          {/* Compliance Note */}
          <Card className="p-5 rounded-2xl border-blue-500/20 bg-blue-500/5 shadow-sm">
            <div className="flex items-start gap-4">
              <Info className="h-5 w-5 text-blue-500 mt-0.5 shrink-0" />
              <div>
                <h3 className="text-sm font-bold text-blue-700">Advisory-Only AI</h3>
                <p className="text-xs text-blue-600 mt-1">
                  All AI signals are advisory-only. No model recommendation auto-finalizes an appointment
                  decision. Human overrides are recorded in <code className="font-mono">VettingDecisionOverride</code> and audit-logged
                  per the platform governance policy.
                </p>
              </div>
            </div>
          </Card>
        </div>

        {/* AI Safety & Policy Sidebar */}
        <div className="xl:col-span-1 space-y-6">
          <h2 className="text-lg font-bold flex items-center gap-2">
            <ShieldCheck className="h-5 w-5 text-muted-foreground" />
            Safety & Compliance
          </h2>

          <Card className="p-6 rounded-4xl border-border/70 bg-card/50 shadow-sm backdrop-blur-sm">
            <div className="space-y-6">
              <div className="flex items-start gap-4">
                <div className="h-8 w-8 rounded-lg bg-rose-500/10 text-rose-500 flex items-center justify-center shrink-0">
                  <AlertTriangle className="h-4 w-4" />
                </div>
                <div>
                  <h4 className="text-sm font-bold">Global Confidence Floor</h4>
                  <p className="text-xs text-muted-foreground mt-1">
                    Minimum rubric score required before a recommendation is surfaced to reviewers.
                    Configured in <code className="font-mono text-[10px]">AI_ML_METRIC_MIN_*</code> environment variables.
                  </p>
                  <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
                    <div className="rounded-lg bg-background/60 border border-border/50 p-2">
                      <p className="text-muted-foreground text-[10px] font-bold uppercase">Authenticity F1</p>
                      <p className="font-bold mt-0.5">≥ 70%</p>
                    </div>
                    <div className="rounded-lg bg-background/60 border border-border/50 p-2">
                      <p className="text-muted-foreground text-[10px] font-bold uppercase">Signature F1</p>
                      <p className="font-bold mt-0.5">≥ 90%</p>
                    </div>
                  </div>
                </div>
              </div>

              <div className="pt-6 border-t border-border/50">
                <h4 className="text-sm font-bold mb-3">Feature Flags (Inference)</h4>
                <div className="space-y-3">
                  {AI_SAFETY_FLAGS.map((flag) => (
                    <div
                      key={flag.name}
                      className="flex items-center justify-between p-3 rounded-xl bg-background/50 border border-border/50"
                    >
                      <span className="text-xs font-medium">{flag.name}</span>
                      {flag.enabled ? (
                        <CheckCircle2 className="h-4 w-4 text-emerald-500 shrink-0" />
                      ) : (
                        <XCircle className="h-4 w-4 text-muted-foreground shrink-0" />
                      )}
                    </div>
                  ))}
                </div>
                <p className="text-[10px] text-muted-foreground mt-3">
                  Feature flag state is derived from backend configuration. Contact platform engineering to update.
                </p>
              </div>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
};

export default AiInfrastructurePage;
