import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Activity, Eye, RefreshCw, Search } from "lucide-react";
import { toast } from "react-toastify";
import { useSearchParams } from "react-router-dom";

import ExportActions from "@/components/common/ExportActions";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { auditService } from "@/services/audit.service";
import type { AuditEventCatalogItem, AuditLog, AuditStatistics } from "@/types";
import { downloadCsvFile, isoDateStamp } from "@/utils/csv";
import { downloadJsonFile } from "@/utils/json";
import { formatDate } from "@/utils/helper";
import { applyQueryUpdates, normalizeQueryValue } from "@/utils/queryParams";

type AuditActionFilter = "all" | "create" | "update" | "delete" | "login" | "logout" | "other";

const ACTION_OPTIONS: Array<{ value: AuditActionFilter; label: string }> = [
  { value: "all", label: "All actions" },
  { value: "create", label: "Create" },
  { value: "update", label: "Update" },
  { value: "delete", label: "Delete" },
  { value: "login", label: "Login" },
  { value: "logout", label: "Logout" },
  { value: "other", label: "Other" },
];

const defaultStats: AuditStatistics = {
  total_logs: 0,
  action_distribution: [],
  entity_distribution: [],
};

const actionPillClass: Record<string, string> = {
  create: "bg-emerald-100 text-emerald-700",
  update: "bg-cyan-100 text-cyan-700",
  delete: "bg-rose-100 text-rose-700",
  login: "bg-indigo-100 text-indigo-700",
  logout: "bg-zinc-100 text-zinc-700",
  other: "bg-slate-200 text-slate-800",
};

const parseActionFilter = (value: string | null): AuditActionFilter => {
  const normalized = normalizeQueryValue(value);
  return ACTION_OPTIONS.some((option) => option.value === normalized)
    ? (normalized as AuditActionFilter)
    : "all";
};

const buildAuditStatsFromLogs = (items: AuditLog[]): AuditStatistics => {
  const actionCounts = new Map<string, number>();
  const entityCounts = new Map<string, number>();

  items.forEach((item) => {
    const action = item.action || "other";
    const entity = item.entity_type || "Unknown";
    actionCounts.set(action, (actionCounts.get(action) || 0) + 1);
    entityCounts.set(entity, (entityCounts.get(entity) || 0) + 1);
  });

  return {
    total_logs: items.length,
    action_distribution: Array.from(actionCounts.entries())
      .map(([action, count]) => ({ action, count }))
      .sort((a, b) => b.count - a.count),
    entity_distribution: Array.from(entityCounts.entries())
      .map(([entity_type, count]) => ({ entity_type, count }))
      .sort((a, b) => b.count - a.count),
  };
};

const AuditLogsPage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [recentLogs, setRecentLogs] = useState<AuditLog[]>([]);
  const [stats, setStats] = useState<AuditStatistics>(defaultStats);
  const [selectedLog, setSelectedLog] = useState<AuditLog | null>(null);
  const [loadingLogId, setLoadingLogId] = useState<string | null>(null);

  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const [actionFilter, setActionFilter] = useState<AuditActionFilter>(() => parseActionFilter(searchParams.get("action")));
  const [actorUserIdFilter, setActorUserIdFilter] = useState(() => normalizeQueryValue(searchParams.get("actor_user_id")));
  const [entityTypeFilter, setEntityTypeFilter] = useState(() => normalizeQueryValue(searchParams.get("entity_type")));
  const [eventKeyFilter, setEventKeyFilter] = useState(() => normalizeQueryValue(searchParams.get("event_key")));
  const [entityIdFilter, setEntityIdFilter] = useState(() => normalizeQueryValue(searchParams.get("entity_id")));
  const [searchFilter, setSearchFilter] = useState(() => normalizeQueryValue(searchParams.get("search")));
  const [eventCatalog, setEventCatalog] = useState<AuditEventCatalogItem[]>([]);

  useEffect(() => {
    const currentAction = parseActionFilter(searchParams.get("action"));
    const currentActor = normalizeQueryValue(searchParams.get("actor_user_id"));
    const currentEntityType = normalizeQueryValue(searchParams.get("entity_type"));
    const currentEventKey = normalizeQueryValue(searchParams.get("event_key"));
    const currentEntityId = normalizeQueryValue(searchParams.get("entity_id"));
    const currentSearch = normalizeQueryValue(searchParams.get("search"));
    if (
      currentAction === actionFilter &&
      currentActor === actorUserIdFilter &&
      currentEntityType === entityTypeFilter &&
      currentEventKey === eventKeyFilter &&
      currentEntityId === entityIdFilter &&
      currentSearch === searchFilter
    ) {
      return;
    }
    const nextParams = applyQueryUpdates(
      searchParams,
      {
        action: actionFilter,
        actor_user_id: actorUserIdFilter || null,
        entity_type: entityTypeFilter || null,
        event_key: eventKeyFilter || null,
        entity_id: entityIdFilter || null,
        search: searchFilter || null,
      },
      { keepPage: true },
    );
    setSearchParams(nextParams, { replace: true });
  }, [
    actionFilter,
    actorUserIdFilter,
    entityIdFilter,
    entityTypeFilter,
    eventKeyFilter,
    searchFilter,
    searchParams,
    setSearchParams,
  ]);

  useEffect(() => {
    let isMounted = true;
    void auditService
      .getEventCatalog()
      .then((catalog) => {
        if (isMounted && Array.isArray(catalog)) {
          setEventCatalog(catalog);
        }
      })
      .catch(() => {
        if (isMounted) {
          setEventCatalog([]);
        }
      });
    return () => {
      isMounted = false;
    };
  }, []);

  const applyClientFilters = useCallback(
    (items: AuditLog[]): AuditLog[] => {
      const normalizedEntityType = entityTypeFilter.trim();
      const normalizedEventKey = eventKeyFilter.trim();
      const normalizedEntityId = entityIdFilter.trim();
      const normalizedSearch = searchFilter.trim().toLowerCase();

      return items.filter((item) => {
        if (actionFilter !== "all" && item.action !== actionFilter) {
          return false;
        }
        if (normalizedEntityType && (item.entity_type || "") !== normalizedEntityType) {
          return false;
        }
        if (normalizedEventKey && String(item.changes?.event || "") !== normalizedEventKey) {
          return false;
        }
        if (normalizedEntityId && String(item.entity_id || "") !== normalizedEntityId) {
          return false;
        }
        if (normalizedSearch) {
          const searchable = `${item.entity_type || ""} ${JSON.stringify(item.changes || {})}`.toLowerCase();
          if (!searchable.includes(normalizedSearch)) {
            return false;
          }
        }
        return true;
      });
    },
    [actionFilter, entityIdFilter, entityTypeFilter, eventKeyFilter, searchFilter],
  );

  const loadAuditLogs = useCallback(async () => {
    setErrorMessage(null);
    try {
      const normalizedActorUserId = actorUserIdFilter.trim();
      if (normalizedActorUserId) {
        const actorLogs = await auditService.getByUser(normalizedActorUserId);
        const filteredActorLogs = applyClientFilters(actorLogs);
        setLogs(filteredActorLogs);
        setStats(buildAuditStatsFromLogs(filteredActorLogs));
        setRecentLogs(filteredActorLogs.slice(0, 10));
        return;
      }

      const [list, statistics, recent] = await Promise.all([
        auditService.list({
          action: actionFilter !== "all" ? actionFilter : undefined,
          entity_type: entityTypeFilter.trim() || undefined,
          changes__event: eventKeyFilter.trim() || undefined,
          entity_id: entityIdFilter.trim() || undefined,
          search: searchFilter.trim() || undefined,
          ordering: "-created_at",
        }),
        auditService.getStatistics(),
        auditService.getRecentActivity(),
      ]);

      setLogs(list);
      setStats(statistics);
      setRecentLogs(recent.slice(0, 10));
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to load audit logs.";
      setErrorMessage(message);
      toast.error(message);
    }
  }, [actionFilter, actorUserIdFilter, applyClientFilters, entityIdFilter, entityTypeFilter, eventKeyFilter, searchFilter]);

  useEffect(() => {
    const run = async () => {
      setLoading(true);
      await loadAuditLogs();
      setLoading(false);
    };
    void run();
  }, [loadAuditLogs]);

  const handleRefresh = async () => {
    setRefreshing(true);
    await loadAuditLogs();
    setRefreshing(false);
  };

  const handleSelectLog = async (logId: string) => {
    setLoadingLogId(logId);
    try {
      const log = await auditService.getById(logId);
      setSelectedLog(log);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to fetch audit log detail.";
      toast.error(message);
    } finally {
      setLoadingLogId(null);
    }
  };

  const topActions = useMemo(() => stats.action_distribution.slice(0, 5), [stats.action_distribution]);
  const topEntities = useMemo(() => stats.entity_distribution.slice(0, 5), [stats.entity_distribution]);
  const normalizedActorUserIdFilter = actorUserIdFilter.trim();
  const normalizedEntityTypeFilter = entityTypeFilter.trim();
  const normalizedEventKeyFilter = eventKeyFilter.trim();
  const isActorFilterActive = normalizedActorUserIdFilter.length > 0;
  const isEntityTypeFilterActive = normalizedEntityTypeFilter.length > 0;
  const isEventKeyFilterActive = normalizedEventKeyFilter.length > 0;
  const hasContextFilters = isActorFilterActive || isEntityTypeFilterActive || isEventKeyFilterActive;
  const entityTypeOptions = useMemo(
    () => Array.from(new Set(eventCatalog.map((item) => item.entity_type))).sort(),
    [eventCatalog],
  );
  const eventKeyOptions = useMemo(
    () => Array.from(new Set(eventCatalog.map((item) => item.key))).sort(),
    [eventCatalog],
  );

  const exportAuditCsv = () => {
    if (logs.length === 0) {
      toast.info("No audit rows to export.");
      return;
    }

    const header = [
      "timestamp",
      "action",
      "actor",
      "entity_type",
      "entity_id",
      "ip_address",
      "user_agent",
      "changes_json",
    ];
    const rows = logs.map((log) => [
      new Date(log.created_at).toISOString(),
      log.action_display || log.action,
      log.admin_user_name || log.user_name || "system",
      log.entity_type || "",
      log.entity_id || "",
      log.ip_address || "",
      log.user_agent || "",
      JSON.stringify(log.changes || {}),
    ]);
    downloadCsvFile(header, rows, `audit-logs-${isoDateStamp()}.csv`);
    toast.success(`Exported ${logs.length} audit row(s).`);
  };

  const exportAuditJson = () => {
    if (logs.length === 0) {
      toast.info("No audit rows to export.");
      return;
    }

    downloadJsonFile(
      {
        exported_at: new Date().toISOString(),
        filters: {
          action: actionFilter,
          actor_user_id: actorUserIdFilter,
          entity_type: entityTypeFilter,
          event_key: eventKeyFilter,
          entity_id: entityIdFilter,
          search: searchFilter,
        },
        statistics: stats,
        total_rows: logs.length,
        logs,
      },
      `audit-logs-${isoDateStamp()}.json`,
    );
    toast.success(`Exported ${logs.length} audit row(s) as JSON.`);
  };

  return (
    <main className="mx-auto max-w-7xl px-4 py-8 space-y-6">
      <header className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-3xl font-black tracking-tight text-slate-900">Audit Logs</h1>
            <p className="mt-1 text-sm text-slate-700">
              Track security and workflow actions across user and admin activity.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <ExportActions
              onCsv={exportAuditCsv}
              onJson={exportAuditJson}
              csvDisabled={loading || logs.length === 0}
              jsonDisabled={loading || logs.length === 0}
            />
            <Button type="button" variant="outline" onClick={() => void handleRefresh()} disabled={refreshing}>
              <RefreshCw className={`mr-2 h-4 w-4 ${refreshing ? "animate-spin" : ""}`} />
              Refresh
            </Button>
          </div>
        </div>
      </header>

      <section className="grid gap-4 md:grid-cols-3">
        <article className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <p className="text-sm text-slate-700">Total Logs</p>
          <p className="mt-2 text-3xl font-black text-slate-900">{stats.total_logs}</p>
        </article>
        <article className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm md:col-span-2">
          <p className="text-sm text-slate-700">Top Actions</p>
          <div className="mt-3 flex flex-wrap gap-2">
            {topActions.length === 0 ? (
              <span className="text-sm text-slate-700">No action statistics available.</span>
            ) : (
              topActions.map((item) => (
                <span
                  key={item.action}
                  className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${
                    actionPillClass[item.action] || "bg-slate-200 text-slate-800"
                  }`}
                >
                  {item.action}: {item.count}
                </span>
              ))
            )}
          </div>
        </article>
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="text-lg font-bold text-slate-900">Filters</h2>
        <div className="mt-4 grid gap-3 md:grid-cols-6">
          <div>
            <label htmlFor="audit-action-filter" className="mb-1 block text-xs font-semibold uppercase text-slate-700">
              Action
            </label>
            <Select value={actionFilter} onValueChange={(value) => setActionFilter(value as AuditActionFilter)}>
              <SelectTrigger id="audit-action-filter" className="w-full">
                <SelectValue placeholder="All actions" />
              </SelectTrigger>
              <SelectContent>
                {ACTION_OPTIONS.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <label htmlFor="audit-actor-user-id" className="mb-1 block text-xs font-semibold uppercase text-slate-700">
              Actor User ID
            </label>
            <Input
              id="audit-actor-user-id"
              value={actorUserIdFilter}
              onChange={(event) => setActorUserIdFilter(event.target.value)}
              placeholder="actor uuid"
            />
          </div>
          <div>
            <label htmlFor="audit-entity-type" className="mb-1 block text-xs font-semibold uppercase text-slate-700">
              Entity Type
            </label>
            <Input
              id="audit-entity-type"
              value={entityTypeFilter}
              onChange={(event) => setEntityTypeFilter(event.target.value)}
              placeholder="e.g. GovernmentPosition"
              list="audit-entity-type-options"
            />
            <datalist id="audit-entity-type-options">
              {entityTypeOptions.map((entityType) => (
                <option key={entityType} value={entityType} />
              ))}
            </datalist>
          </div>
          <div>
            <label htmlFor="audit-event-key" className="mb-1 block text-xs font-semibold uppercase text-slate-700">
              Event Key
            </label>
            <Input
              id="audit-event-key"
              value={eventKeyFilter}
              onChange={(event) => setEventKeyFilter(event.target.value)}
              placeholder="e.g. personnel_record_deleted"
              list="audit-event-key-options"
            />
            <datalist id="audit-event-key-options">
              {eventKeyOptions.map((eventKey) => (
                <option key={eventKey} value={eventKey} />
              ))}
            </datalist>
          </div>
          <div>
            <label htmlFor="audit-entity-id" className="mb-1 block text-xs font-semibold uppercase text-slate-700">
              Entity ID
            </label>
            <Input
              id="audit-entity-id"
              value={entityIdFilter}
              onChange={(event) => setEntityIdFilter(event.target.value)}
              placeholder="case id / uuid"
            />
          </div>
          <div>
            <label htmlFor="audit-search" className="mb-1 block text-xs font-semibold uppercase text-slate-700">
              Search
            </label>
            <div className="relative">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-700" />
              <Input
                id="audit-search"
                value={searchFilter}
                onChange={(event) => setSearchFilter(event.target.value)}
                placeholder="entity/changes"
                className="pl-9"
              />
            </div>
          </div>
        </div>
      </section>

      {isActorFilterActive ? (
        <section className="rounded-xl border border-cyan-200 bg-cyan-50 px-4 py-3 text-sm text-cyan-900">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p>
              Actor filter active: <span className="font-semibold">{normalizedActorUserIdFilter}</span>
            </p>
            <Button
              type="button"
              variant="outline"
              className="border-cyan-300 bg-white text-cyan-900 hover:bg-cyan-100"
              onClick={() => setActorUserIdFilter("")}
            >
              Clear actor filter
            </Button>
          </div>
        </section>
      ) : null}

      {hasContextFilters ? (
        <section className="rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-800">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs font-semibold uppercase tracking-wide text-slate-700">Active filters</span>
            {isEntityTypeFilterActive ? (
              <button
                type="button"
                onClick={() => setEntityTypeFilter("")}
                className="inline-flex items-center rounded-full border border-slate-300 bg-slate-100 px-3 py-1 text-xs font-medium text-slate-800 hover:bg-slate-200"
              >
                Entity: {normalizedEntityTypeFilter} x
              </button>
            ) : null}
            {isEventKeyFilterActive ? (
              <button
                type="button"
                onClick={() => setEventKeyFilter("")}
                className="inline-flex items-center rounded-full border border-slate-300 bg-slate-100 px-3 py-1 text-xs font-medium text-slate-800 hover:bg-slate-200"
              >
                Event: {normalizedEventKeyFilter} x
              </button>
            ) : null}
            {isActorFilterActive ? (
              <button
                type="button"
                onClick={() => setActorUserIdFilter("")}
                className="inline-flex items-center rounded-full border border-cyan-300 bg-cyan-100 px-3 py-1 text-xs font-medium text-cyan-900 hover:bg-cyan-200"
              >
                Actor: {normalizedActorUserIdFilter} x
              </button>
            ) : null}
            <Button
              type="button"
              variant="outline"
              className="ml-auto border-slate-300 bg-white text-slate-800 hover:bg-slate-100"
              onClick={() => {
                setActorUserIdFilter("");
                setEntityTypeFilter("");
                setEventKeyFilter("");
              }}
            >
              Clear key filters
            </Button>
          </div>
        </section>
      ) : null}

      {loading ? (
        <section className="rounded-xl border border-slate-200 bg-white px-4 py-10 text-center text-slate-700 shadow-sm">
          Loading audit logs...
        </section>
      ) : errorMessage ? (
        <section className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-4 text-sm text-rose-700">
          {errorMessage}
        </section>
      ) : (
        <>
          <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <h2 className="text-lg font-bold text-slate-900">Audit Entries</h2>
            {logs.length === 0 ? (
              <p className="mt-3 text-sm text-slate-700">No audit logs found for current filters.</p>
            ) : (
              <>
                <p className="mt-3 text-xs text-slate-700 md:hidden">Swipe horizontally to view all audit columns.</p>
                <div className="mt-2 overflow-x-auto rounded-lg border border-slate-200">
                <table className="min-w-[980px] w-full text-sm">
                  <thead className="bg-slate-50 text-left text-xs uppercase text-slate-700">
                    <tr>
                      <th className="sticky left-0 z-10 bg-slate-50 px-3 py-2">Action</th>
                      <th className="px-3 py-2">Actor</th>
                      <th className="px-3 py-2">Entity</th>
                      <th className="px-3 py-2">IP</th>
                      <th className="px-3 py-2">Time</th>
                      <th className="px-3 py-2">Detail</th>
                    </tr>
                  </thead>
                  <tbody>
                    {logs.map((log) => (
                      <tr key={log.id} className="border-t border-slate-100 hover:bg-slate-50/70">
                        <td className="sticky left-0 bg-white px-3 py-2">
                          <span
                            className={`inline-flex rounded-full px-2 py-0.5 text-xs font-semibold ${
                              actionPillClass[log.action] || "bg-slate-200 text-slate-800"
                            }`}
                          >
                            {log.action_display || log.action}
                          </span>
                        </td>
                        <td className="px-3 py-2 text-slate-700">
                          <div className="flex flex-col gap-1">
                            <span>{log.admin_user_name || log.user_name || "system"}</span>
                            {log.admin_user || log.user ? (
                              <button
                                type="button"
                                onClick={() => setActorUserIdFilter(String(log.admin_user || log.user))}
                                className="w-fit text-xs font-medium text-cyan-700 hover:text-cyan-800"
                              >
                                Filter actor
                              </button>
                            ) : null}
                          </div>
                        </td>
                        <td className="px-3 py-2 text-slate-700">
                          {log.entity_type || "-"}
                          {log.entity_id ? ` #${log.entity_id}` : ""}
                        </td>
                        <td className="px-3 py-2 text-slate-700">{log.ip_address || "-"}</td>
                        <td className="px-3 py-2 text-slate-700">{formatDate(log.created_at)}</td>
                        <td className="px-3 py-2">
                          <button
                            type="button"
                            onClick={() => void handleSelectLog(log.id)}
                            disabled={loadingLogId === log.id}
                            className="inline-flex items-center gap-1 rounded border border-slate-700 px-2 py-1 text-xs font-medium text-slate-800 hover:bg-slate-100 disabled:opacity-60"
                          >
                            <Eye className="h-3.5 w-3.5" />
                            {loadingLogId === log.id ? "Loading..." : "View"}
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              </>
            )}
          </section>

          <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <h2 className="text-lg font-bold text-slate-900">Selected Audit Detail</h2>
            {!selectedLog ? (
              <p className="mt-3 text-sm text-slate-700">Select a row to inspect full event details.</p>
            ) : (
              <div className="mt-3 grid gap-4 md:grid-cols-2">
                <div>
                  <p className="text-xs uppercase text-slate-700">Action</p>
                  <p className="text-sm text-slate-800">{selectedLog.action_display || selectedLog.action}</p>
                </div>
                <div>
                  <p className="text-xs uppercase text-slate-700">Entity</p>
                  <p className="text-sm text-slate-800">
                    {selectedLog.entity_type} {selectedLog.entity_id ? `#${selectedLog.entity_id}` : ""}
                  </p>
                </div>
                <div>
                  <p className="text-xs uppercase text-slate-700">Actor</p>
                  <p className="text-sm text-slate-800">
                    {selectedLog.admin_user_name || selectedLog.user_name || "system"}
                  </p>
                </div>
                <div>
                  <p className="text-xs uppercase text-slate-700">Timestamp</p>
                  <p className="text-sm text-slate-800">{formatDate(selectedLog.created_at)}</p>
                </div>
                <div className="md:col-span-2">
                  <p className="text-xs uppercase text-slate-700">User Agent</p>
                  <p className="text-sm text-slate-700 break-all">{selectedLog.user_agent || "-"}</p>
                </div>
                <div className="md:col-span-2">
                  <p className="text-xs uppercase text-slate-700">Changes</p>
                  <pre className="mt-1 rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs text-slate-700 overflow-auto">
                    {JSON.stringify(selectedLog.changes || {}, null, 2)}
                  </pre>
                </div>
              </div>
            )}
          </section>

          <section className="grid gap-4 md:grid-cols-2">
            <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
              <h2 className="text-lg font-bold text-slate-900">Entity Distribution</h2>
              {topEntities.length === 0 ? (
                <p className="mt-3 text-sm text-slate-700">No entity distribution data available.</p>
              ) : (
                <ul className="mt-3 space-y-2">
                  {topEntities.map((item) => (
                    <li key={item.entity_type} className="flex items-center justify-between rounded-lg border border-slate-200 px-3 py-2">
                      <span className="text-sm text-slate-700">{item.entity_type}</span>
                      <span className="text-sm font-semibold text-slate-900">{item.count}</span>
                    </li>
                  ))}
                </ul>
              )}
            </article>

            <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
              <h2 className="text-lg font-bold text-slate-900">Recent Activity</h2>
              {recentLogs.length === 0 ? (
                <p className="mt-3 text-sm text-slate-700">No recent activity available.</p>
              ) : (
                <ul className="mt-3 space-y-2">
                  {recentLogs.map((log) => (
                    <li key={log.id} className="flex items-start gap-3 rounded-lg border border-slate-200 px-3 py-2">
                      <Activity className="mt-0.5 h-4 w-4 text-slate-700" />
                      <div>
                        <p className="text-sm font-medium text-slate-800">
                          {log.action_display || log.action} on {log.entity_type || "N/A"}
                        </p>
                        <p className="text-xs text-slate-700">
                          {log.admin_user_name || log.user_name || "system"} at {formatDate(log.created_at)}
                        </p>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </article>
          </section>
        </>
      )}
    </main>
  );
};

export default AuditLogsPage;

