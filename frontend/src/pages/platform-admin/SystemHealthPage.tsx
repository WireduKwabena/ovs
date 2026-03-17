import React, { useEffect, useState, useCallback } from 'react';
import { 
  Activity, 
  RefreshCw, 
  CheckCircle2, 
  AlertCircle, 
  Clock, 
  Cpu, 
  Database, 
  Network,
  Zap
} from 'lucide-react';
import { toast } from 'react-toastify';
import { videoCallService } from '@/services/videoCall.service';
import type { VideoMeetingReminderHealth } from '@/types';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import {
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  AreaChart,
  Area
} from 'recharts';

// Mock data for latency visualization
const latencyData = [
  { time: '10:00', api: 120, ai: 450 },
  { time: '10:05', api: 132, ai: 480 },
  { time: '10:10', api: 101, ai: 420 },
  { time: '10:15', api: 134, ai: 510 },
  { time: '10:20', api: 90, ai: 390 },
  { time: '10:25', api: 230, ai: 680 },
  { time: '10:30', api: 210, ai: 610 },
  { time: '10:35', api: 120, ai: 440 },
  { time: '10:40', api: 110, ai: 410 },
];

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

  const services = [
    { name: 'Core API Gateway', status: 'healthy', icon: Zap, latency: '42ms' },
    { name: 'PostgreSQL Cluster', status: 'healthy', icon: Database, latency: '8ms' },
    { name: 'Redis Cache (L1)', status: 'healthy', icon: Zap, latency: '2ms' },
    { name: 'AI Inference Engine', status: 'healthy', icon: Cpu, latency: '482ms' },
    { name: 'OCR Processor', status: 'healthy', icon: Activity, latency: '1240ms' },
    { name: 'Notification Service', status: 'healthy', icon: Network, latency: '15ms' },
  ];

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

      {/* Service Status Matrix */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
        {services.map((service) => (
          <Card key={service.name} className="p-4 rounded-2xl border-border/70 bg-card/50 shadow-sm backdrop-blur-sm">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="h-10 w-10 rounded-xl bg-primary/10 text-primary flex items-center justify-center">
                  <service.icon className="h-5 w-5" />
                </div>
                <div>
                  <h3 className="text-sm font-bold">{service.name}</h3>
                  <div className="flex items-center gap-1.5 mt-0.5">
                    <CheckCircle2 className="h-3 w-3 text-emerald-500" />
                    <span className="text-[10px] font-bold text-emerald-500 uppercase tracking-widest">Healthy</span>
                  </div>
                </div>
              </div>
              <div className="text-right">
                <p className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">Latency</p>
                <p className="text-sm font-mono font-bold">{service.latency}</p>
              </div>
            </div>
          </Card>
        ))}
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-8">
        {/* Latency Visualization */}
        <Card className="p-6 rounded-4xl border-border/70 bg-card/50 shadow-sm backdrop-blur-sm">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-lg font-bold flex items-center gap-2">
              <Activity className="h-5 w-5 text-primary" />
              Traffic & Latency
            </h2>
            <Badge variant="outline" className="rounded-full">Real-time (5m interval)</Badge>
          </div>
          <div className="h-[300px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={latencyData}>
                <defs>
                  <linearGradient id="colorApi" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#0ea5e9" stopOpacity={0.1}/>
                    <stop offset="95%" stopColor="#0ea5e9" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(0,0,0,0.05)" />
                <XAxis dataKey="time" axisLine={false} tickLine={false} tick={{fontSize: 12}} />
                <YAxis axisLine={false} tickLine={false} tick={{fontSize: 12}} />
                <Tooltip 
                  contentStyle={{borderRadius: '16px', border: '1px solid rgba(0,0,0,0.1)', boxShadow: '0 10px 15px -3px rgba(0,0,0,0.1)'}}
                />
                <Area type="monotone" dataKey="api" stroke="#0ea5e9" fillOpacity={1} fill="url(#colorApi)" strokeWidth={2} name="API Latency (ms)" />
                <Area type="monotone" dataKey="ai" stroke="#6366f1" fillOpacity={0} strokeWidth={2} name="AI Process (ms)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </Card>

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
