import React, { useEffect, useState, useCallback } from 'react';
import {
  Brain,
  RefreshCw,
  ShieldCheck,
  AlertTriangle,
  Server,
  Zap,
  ChevronRight,
  Monitor
} from 'lucide-react';
import { toast } from 'react-toastify';
import { aiMonitorService } from '@/services/aiMonitor.service';
import type { AiMonitorHealthResponse } from '@/types';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { 
  BarChart, 
  Bar, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer,
  Cell
} from 'recharts';

const mockInferenceData = [
  { model: 'Face-CNN', latency: 420, status: 'stable' },
  { model: 'OCR-Engine', latency: 1240, status: 'load' },
  { model: 'Non-Verbal', latency: 310, status: 'stable' },
  { model: 'Auth-Checker', latency: 180, status: 'stable' },
  { model: 'Social-Advisory', latency: 2100, status: 'high' },
];

export const AiInfrastructurePage: React.FC = () => {
  const [health, setHealth] = useState<AiMonitorHealthResponse | null>(null);
  const [, setLoading] = useState(true);
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

  const getStatusColor = (latency: number) => {
    if (latency < 500) return '#10b981';
    if (latency < 1500) return '#f59e0b';
    return '#f43f5e';
  };

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
        {/* Model Availability Matrix */}
        <div className="xl:col-span-2 space-y-6">
          <h2 className="text-lg font-bold flex items-center gap-2">
            <Server className="h-5 w-5 text-muted-foreground" />
            Global Inference Telemetry
          </h2>
          
          <Card className="p-6 rounded-4xl border-border/70 bg-card/50 shadow-sm backdrop-blur-sm">
            <div className="h-[350px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={mockInferenceData} layout="vertical" margin={{ left: 40, right: 40 }}>
                  <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="rgba(0,0,0,0.05)" />
                  <XAxis type="number" hide />
                  <YAxis 
                    dataKey="model" 
                    type="category" 
                    axisLine={false} 
                    tickLine={false} 
                    tick={{fontSize: 12, fontWeight: 'bold'}} 
                  />
                  <Tooltip 
                    cursor={{fill: 'rgba(0,0,0,0.02)'}}
                    contentStyle={{borderRadius: '16px', border: '1px solid rgba(0,0,0,0.1)'}}
                  />
                  <Bar dataKey="latency" radius={[0, 8, 8, 0]} barSize={32}>
                    {mockInferenceData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={getStatusColor(entry.latency)} fillOpacity={0.8} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
            <div className="mt-4 flex justify-center gap-6 text-[10px] font-bold uppercase tracking-widest text-muted-foreground">
               <span className="flex items-center gap-1.5"><div className="h-2 w-2 rounded-full bg-emerald-500" /> Optimized (&lt;500ms)</span>
               <span className="flex items-center gap-1.5"><div className="h-2 w-2 rounded-full bg-amber-500" /> Moderate Load</span>
               <span className="flex items-center gap-1.5"><div className="h-2 w-2 rounded-full bg-rose-500" /> High Latency</span>
            </div>
          </Card>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
             {health && (
               <Card className="p-5 rounded-2xl border-border/70 bg-card/50 shadow-sm backdrop-blur-sm">
                  <div className="flex items-center gap-3 mb-4">
                     <div className="h-10 w-10 rounded-xl bg-indigo-500/10 text-indigo-500 flex items-center justify-center">
                        <Brain className="h-5 w-5" />
                     </div>
                     <div>
                        <h3 className="text-sm font-bold">Default Router</h3>
                        <p className="text-[10px] font-bold text-muted-foreground uppercase">{health.model_name}</p>
                     </div>
                     <Badge className="ml-auto bg-emerald-500/10 text-emerald-500 rounded-full border-emerald-500/20">Active</Badge>
                  </div>
                  <div className="space-y-2">
                     <div className="flex items-center justify-between text-xs">
                        <span className="text-muted-foreground">Backend Engine</span>
                        <span className="font-mono">{health.monitor.backend}</span>
                     </div>
                     <div className="flex items-center justify-between text-xs">
                        <span className="text-muted-foreground">Redis Cache</span>
                        <span className="text-emerald-500 font-bold">{health.monitor.redis_configured ? 'ENABLED' : 'DISABLED'}</span>
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
                      <h3 className="text-sm font-bold">Scaling Policy</h3>
                      <p className="text-[10px] font-bold text-muted-foreground uppercase">Autoscale (Aggressive)</p>
                   </div>
                </div>
                <div className="space-y-2">
                   <div className="flex items-center justify-between text-xs">
                      <span className="text-muted-foreground">Worker Nodes</span>
                      <span className="font-bold">12 Active</span>
                   </div>
                   <div className="flex items-center justify-between text-xs">
                      <span className="text-muted-foreground">Queue Depth</span>
                      <span className="text-emerald-500 font-bold">LOW</span>
                   </div>
                </div>
             </Card>
          </div>
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
                      <p className="text-xs text-muted-foreground mt-1 mb-3">Minimum score for automated approval across all organizations.</p>
                      <div className="flex items-center gap-3">
                         <input title='range' type="range" className="flex-1 accent-primary" defaultValue="85" />
                         <span className="text-sm font-mono font-bold">85%</span>
                      </div>
                   </div>
                </div>

                <div className="pt-6 border-t border-border/50">
                   <h4 className="text-sm font-bold mb-3">Feature Flags (Inference)</h4>
                   <div className="space-y-3">
                      {[
                        { name: 'Strict Document Type Check', enabled: true },
                        { name: 'Deepfake Probability Scan', enabled: true },
                        { name: 'Social Advisory Engine', enabled: false },
                        { name: 'Cross-Tenant Similarity Detect', enabled: true },
                      ].map(flag => (
                        <div key={flag.name} className="flex items-center justify-between p-3 rounded-xl bg-background/50 border border-border/50 hover:bg-background transition-colors">
                           <span className="text-xs font-medium">{flag.name}</span>
                           <div className={`h-4 w-8 rounded-full relative transition-colors ${flag.enabled ? 'bg-primary' : 'bg-muted'}`}>
                              <div className={`absolute top-0.5 h-3 w-3 rounded-full bg-white transition-all ${flag.enabled ? 'right-0.5' : 'left-0.5'}`} />
                           </div>
                        </div>
                      ))}
                   </div>
                </div>

                <div className="pt-6 border-t border-border/50">
                   <Button className="w-full rounded-xl gap-2 py-6">
                      Update Platform AI Policy
                      <ChevronRight className="h-4 w-4" />
                   </Button>
                </div>
             </div>
          </Card>
        </div>
      </div>
    </div>
  );
};

export default AiInfrastructurePage;
