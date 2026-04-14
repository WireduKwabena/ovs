import React, { useEffect, useState, useCallback } from 'react';
import {
  RefreshCw,
  AlertCircle,
  Clock,
} from 'lucide-react';
import { toast } from 'react-toastify';
import { videoCallService } from '@/services/videoCall.service';
import type { VideoMeetingReminderHealth } from '@/types';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';


export const SystemHealthPage: React.FC = () => {
  const [reminderHealth, setReminderHealth] = useState<VideoMeetingReminderHealth | null>(null);
  const [, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [lastCheck, setLastCheck] = useState<Date>(new Date());

  const fetchHealth = useCallback(async (isSilent = false) => {
    if (!isSilent) setLoading(true);
    else setRefreshing(true);
    
    try {
      const data = await videoCallService.getReminderHealth();
      setReminderHealth(data);
      setLastCheck(new Date());
    } catch {
      toast.error('Failed to sync system health data');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void fetchHealth();
    const interval = setInterval(() => void fetchHealth(true), 30000);
    return () => clearInterval(interval);
  }, [fetchHealth]);


  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">System Health</h1>
          <p className="text-muted-foreground mt-1 text-sm md:text-base">
            Real-time telemetry and infrastructure status for the OVS Redo platform.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="text-right mr-2 hidden sm:block">
            <p className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">Last Telemetry Sync</p>
            <p className="text-xs font-mono">{lastCheck.toLocaleTimeString()}</p>
          </div>
          <Button 
            variant="outline" 
            className="rounded-xl gap-2"
            onClick={() => void fetchHealth(true)}
            disabled={refreshing}
          >
            <RefreshCw className={`h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} />
            Sync Now
          </Button>
        </div>
      </div>

      {/* Observability Note */}
      <Card className="p-5 rounded-2xl border-border/70 bg-muted/30 shadow-sm">
        <div className="flex items-start gap-3">
          <AlertCircle className="h-5 w-5 text-muted-foreground mt-0.5 shrink-0" />
          <p className="text-sm text-muted-foreground leading-relaxed">
            Per-service latency metrics and traffic telemetry require an observability backend
            (e.g. Prometheus + Grafana). Connect one to populate real-time service status here.
            The Celery worker pool health below is live.
          </p>
        </div>
      </Card>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-8">

        {/* Reminder Runtime Health */}
        <Card className="p-6 rounded-4xl border-border/70 bg-card/50 shadow-sm backdrop-blur-sm">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-lg font-bold flex items-center gap-2">
              <Clock className="h-5 w-5 text-indigo-500" />
              Celery Worker Pools (Reminder Runtime)
            </h2>
            <Badge className="bg-emerald-500/10 text-emerald-500 hover:bg-emerald-500/10 rounded-full border-emerald-500/20">Operational</Badge>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="rounded-2xl bg-muted/30 p-4 border border-border/50">
              <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-muted-foreground mb-1">Soon Retry Pending</p>
              <p className="text-3xl font-bold">{reminderHealth?.soon_retry_pending ?? 0}</p>
            </div>
            <div className="rounded-2xl bg-muted/30 p-4 border border-border/50">
              <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-muted-foreground mb-1">Start Now Pending</p>
              <p className="text-3xl font-bold">{reminderHealth?.start_now_retry_pending ?? 0}</p>
            </div>
            <div className="rounded-2xl bg-muted/30 p-4 border border-border/50">
              <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-muted-foreground mb-1">Time Up Pending</p>
              <p className="text-3xl font-bold">{reminderHealth?.time_up_retry_pending ?? 0}</p>
            </div>
            <div className="rounded-2xl bg-rose-500/5 p-4 border border-rose-500/20">
              <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-rose-500 mb-1">Retries Exhausted</p>
              <p className="text-3xl font-bold text-rose-500">
                {(reminderHealth?.soon_retry_exhausted ?? 0) + (reminderHealth?.start_now_retry_exhausted ?? 0) + (reminderHealth?.time_up_retry_exhausted ?? 0)}
              </p>
            </div>
          </div>

          <div className="mt-6 p-4 rounded-2xl bg-primary/5 border border-primary/10">
            <div className="flex items-center gap-3">
              <AlertCircle className="h-5 w-5 text-primary" />
              <p className="text-xs leading-relaxed text-muted-foreground">
                <strong className="text-foreground">Administrator Note:</strong> High exhausted retry counts usually indicate an issue with the third-party notification gateway or SMTP pool congestion.
              </p>
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
};

export default SystemHealthPage;
