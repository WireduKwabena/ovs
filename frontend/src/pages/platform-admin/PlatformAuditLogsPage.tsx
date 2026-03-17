import React, { useEffect, useState, useCallback } from 'react';
import {
  Search,
  Download,
  Calendar,
  ShieldAlert,
  Info,
  ChevronRight,
  RefreshCw,
  Building2,
  Clock
} from 'lucide-react';
import { toast } from 'react-toastify';
import { auditService } from '@/services/audit.service';
import type { AuditLog, AuditEventCatalogItem } from '@/types';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

export const PlatformAuditLogsPage: React.FC = () => {
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [catalog, setCatalog] = useState<AuditEventCatalogItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedAction, setSelectedAction] = useState<string>('all');

  const fetchAuditData = useCallback(async (isSilent = false) => {
    if (!isSilent) setLoading(true);
    else setRefreshing(true);

    try {
      const [logsData, catalogData] = await Promise.all([
        auditService.list({ ordering: '-timestamp' }),
        auditService.getEventCatalog()
      ]);
      
      // Filter logs to only show platform-level events if necessary, 
      // but usually the backend list endpoint for a platform_admin 
      // already handles this scope.
      setLogs(logsData);
      setCatalog(catalogData);
    } catch {
      toast.error('Failed to sync platform audit logs');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void fetchAuditData();
  }, [fetchAuditData]);

  const getActionColor = (action: string) => {
    if (action.includes('create')) return 'bg-emerald-500/10 text-emerald-500 border-emerald-500/20';
    if (action.includes('delete')) return 'bg-rose-500/10 text-rose-500 border-rose-500/20';
    if (action.includes('update')) return 'bg-amber-500/10 text-amber-500 border-amber-500/20';
    return 'bg-primary/10 text-primary border-primary/20';
  };

  const filteredLogs = logs.filter(log => {
    const matchesSearch = log.user_name?.toLowerCase().includes(searchTerm.toLowerCase()) || 
                         log.action.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         log.entity_type?.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesAction = selectedAction === 'all' || log.action === selectedAction;
    return matchesSearch && matchesAction;
  });

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Platform Audit Logs</h1>
          <p className="text-muted-foreground mt-1 text-sm md:text-base">
            Traceability and compliance for all system-level administrative actions.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Button 
            variant="outline" 
            className="rounded-xl gap-2"
            onClick={() => void fetchAuditData(true)}
            disabled={refreshing}
          >
            <RefreshCw className={`h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} />
            Refresh Logs
          </Button>
          <Button variant="outline" className="rounded-xl gap-2">
            <Download className="h-4 w-4" />
            Export CSV
          </Button>
        </div>
      </div>

      {/* Filter Bar */}
      <Card className="p-4 rounded-2xl border-border/70 bg-card/50 shadow-sm backdrop-blur-sm">
        <div className="flex flex-col md:flex-row gap-4">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
            <input 
              type="text" 
              placeholder="Search by actor, action, or entity..." 
              className="w-full bg-background/50 border border-border/70 rounded-xl pl-10 pr-4 py-2 text-sm focus:outline-hidden focus:ring-2 focus:ring-primary/20"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </div>
          <select 
            title='select'
            className="bg-background/50 border border-border/70 rounded-xl px-4 py-2 text-sm focus:outline-hidden focus:ring-2 focus:ring-primary/20"
            value={selectedAction}
            onChange={(e) => setSelectedAction(e.target.value)}
          >
            <option value="all">All Actions</option>
            {catalog.map(item => (
              <option key={item.action} value={item.action}>{item.description}</option>
            ))}
          </select>
        </div>
      </Card>

      {/* Logs Timeline */}
      <div className="space-y-4">
        {loading ? (
          <div className="flex justify-center p-12">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
          </div>
        ) : filteredLogs.length === 0 ? (
          <Card className="p-12 text-center rounded-2xl border-dashed border-border/70 bg-muted/20">
            <p className="text-muted-foreground">No audit logs found for the selected criteria.</p>
          </Card>
        ) : (
          filteredLogs.map((log) => (
            <Card key={log.id} className="p-5 rounded-2xl border-border/70 bg-card/50 hover:bg-card/80 transition-all shadow-sm group">
              <div className="flex items-start gap-4">
                <div className="h-10 w-10 rounded-xl bg-muted flex items-center justify-center shrink-0 group-hover:bg-primary/10 transition-colors">
                  <ShieldAlert className="h-5 w-5 text-muted-foreground group-hover:text-primary transition-colors" />
                </div>
                
                <div className="flex-1 min-w-0">
                  <div className="flex flex-col md:flex-row md:items-center justify-between gap-2">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-sm font-bold text-foreground">{log.user_name || 'System'}</span>
                      <ChevronRight className="h-3 w-3 text-muted-foreground" />
                      <Badge variant="outline" className={`rounded-full font-bold uppercase tracking-widest text-[9px] ${getActionColor(log.action)}`}>
                        {log.action.replace(/_/g, ' ')}
                      </Badge>
                      <span className="text-sm font-medium text-foreground">
                        {log.entity_type?.replace(/_/g, ' ')}
                      </span>
                    </div>
                    <div className="flex items-center gap-4 text-[11px] font-bold uppercase tracking-widest text-muted-foreground">
                      <span className="flex items-center gap-1.5"><Clock className="h-3.5 w-3.5" /> {new Date(log.created_at).toLocaleTimeString()}</span>
                      <span className="flex items-center gap-1.5"><Calendar className="h-3.5 w-3.5" /> {new Date(log.created_at).toLocaleDateString()}</span>
                    </div>
                  </div>

                  <p className="mt-2 text-sm text-muted-foreground leading-relaxed">
                    {log.changes?.event || `Administrative ${log.action} performed on platform entity.`}
                  </p>

                  <div className="mt-3 flex items-center gap-3">
                    <div className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-widest text-muted-foreground/60">
                      <Building2 className="h-3 w-3" />
                      ID: {log.entity_id?.substring(0, 8)}...
                    </div>
                    <div className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-widest text-muted-foreground/60">
                      <Info className="h-3 w-3" />
                      IP: {log.ip_address || 'Internal'}
                    </div>
                    <Button variant="link" className="h-auto p-0 text-[10px] font-bold uppercase tracking-widest ml-auto">
                      View Payload Details
                    </Button>
                  </div>
                </div>
              </div>
            </Card>
          ))
        )}
      </div>
    </div>
  );
};

export default PlatformAuditLogsPage;
