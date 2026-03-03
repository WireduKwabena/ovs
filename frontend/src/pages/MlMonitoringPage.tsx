import React, { useCallback, useEffect, useMemo, useState } from "react";
import { BarChart3, Brain, Download, RefreshCw } from "lucide-react";
import { toast } from "react-toastify";

import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { mlMonitoringService } from "@/services/mlMonitoring.service";
import type { MLModelMetrics, MLPerformanceSummary } from "@/types";
import { downloadCsvFile, isoDateStamp } from "@/utils/csv";
import { formatDate } from "@/utils/helper";

const defaultSummary: MLPerformanceSummary = {
  models: {},
  total_models: 0,
};

const percentage = (value: number): string => `${(value * 100).toFixed(2)}%`;

const MlMonitoringPage: React.FC = () => {
  const [latestMetrics, setLatestMetrics] = useState<MLModelMetrics[]>([]);
  const [history, setHistory] = useState<MLModelMetrics[]>([]);
  const [summary, setSummary] = useState<MLPerformanceSummary>(defaultSummary);

  const [selectedModel, setSelectedModel] = useState("all");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const modelOptions = useMemo(() => {
    return Array.from(new Set(latestMetrics.map((metric) => metric.model_name))).sort();
  }, [latestMetrics]);

  const activeModel = selectedModel === "all" ? modelOptions[0] : selectedModel;

  const loadMetrics = useCallback(async () => {
    setErrorMessage(null);
    try {
      const [latest, perfSummary] = await Promise.all([
        mlMonitoringService.latest(),
        mlMonitoringService.performanceSummary(),
      ]);
      setLatestMetrics(latest);
      setSummary(perfSummary);

      const candidateModel = selectedModel === "all" ? latest[0]?.model_name : selectedModel;
      if (candidateModel) {
        const modelHistory = await mlMonitoringService.history(candidateModel, 20);
        setHistory(modelHistory);
      } else {
        setHistory([]);
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to load ML monitoring metrics.";
      setErrorMessage(message);
      toast.error(message);
    }
  }, [selectedModel]);

  useEffect(() => {
    const run = async () => {
      setLoading(true);
      await loadMetrics();
      setLoading(false);
    };
    void run();
  }, [loadMetrics]);

  const handleModelChange = async (value: string) => {
    setSelectedModel(value);
    if (value === "all") {
      if (latestMetrics[0]?.model_name) {
        try {
          const data = await mlMonitoringService.history(latestMetrics[0].model_name, 20);
          setHistory(data);
        } catch (error) {
          const message = error instanceof Error ? error.message : "Failed to fetch model history.";
          toast.error(message);
        }
      } else {
        setHistory([]);
      }
      return;
    }

    try {
      const data = await mlMonitoringService.history(value, 20);
      setHistory(data);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to fetch model history.";
      toast.error(message);
    }
  };

  const handleRefresh = async () => {
    setRefreshing(true);
    await loadMetrics();
    setRefreshing(false);
  };

  const displayedLatest = useMemo(() => {
    if (selectedModel === "all") {
      return latestMetrics;
    }
    return latestMetrics.filter((metric) => metric.model_name === selectedModel);
  }, [latestMetrics, selectedModel]);

  const exportLatestCsv = () => {
    if (displayedLatest.length === 0) {
      toast.info("No latest metrics rows to export.");
      return;
    }
    const header = [
      "model_name",
      "model_version",
      "accuracy",
      "precision",
      "recall",
      "f1_score",
      "trained_at",
      "evaluated_at",
    ];
    const rows = displayedLatest.map((metric) => [
      metric.model_name,
      metric.model_version,
      metric.accuracy,
      metric.precision,
      metric.recall,
      metric.f1_score,
      metric.trained_at,
      metric.evaluated_at,
    ]);
    downloadCsvFile(header, rows, `ml-latest-metrics-${isoDateStamp()}.csv`);
    toast.success(`Exported ${displayedLatest.length} latest metric row(s).`);
  };

  const exportHistoryCsv = () => {
    if (history.length === 0) {
      toast.info("No history rows to export.");
      return;
    }
    const header = [
      "model_name",
      "model_version",
      "accuracy",
      "precision",
      "recall",
      "f1_score",
      "trained_at",
      "evaluated_at",
    ];
    const rows = history.map((metric) => [
      metric.model_name,
      metric.model_version,
      metric.accuracy,
      metric.precision,
      metric.recall,
      metric.f1_score,
      metric.trained_at,
      metric.evaluated_at,
    ]);
    downloadCsvFile(header, rows, `ml-history-${activeModel || "model"}-${isoDateStamp()}.csv`);
    toast.success(`Exported ${history.length} history row(s).`);
  };

  return (
    <main className="mx-auto max-w-7xl px-4 py-8 space-y-6">
      <header className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-3xl font-black tracking-tight text-slate-900">ML Monitoring</h1>
            <p className="mt-1 text-sm text-slate-600">
              Track model performance metrics, latest versions, and trend history.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button type="button" variant="outline" onClick={exportLatestCsv} disabled={loading || displayedLatest.length === 0}>
              <Download className="mr-2 h-4 w-4" />
              Export Latest CSV
            </Button>
            <Button type="button" variant="outline" onClick={() => void handleRefresh()} disabled={refreshing}>
              <RefreshCw className={`mr-2 h-4 w-4 ${refreshing ? "animate-spin" : ""}`} />
              Refresh
            </Button>
          </div>
        </div>
      </header>

      <section className="grid gap-4 md:grid-cols-3">
        <article className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <p className="text-sm text-slate-500">Models Tracked</p>
            <Brain className="h-5 w-5 text-indigo-600" />
          </div>
          <p className="mt-2 text-3xl font-black text-slate-900">{summary.total_models}</p>
        </article>
        <article className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <p className="text-sm text-slate-500">Active Filter</p>
            <BarChart3 className="h-5 w-5 text-cyan-600" />
          </div>
          <p className="mt-2 text-lg font-semibold text-slate-900">{activeModel || "None"}</p>
        </article>
        <article className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <p className="text-sm text-slate-500">Latest Metrics Entries</p>
          <p className="mt-2 text-3xl font-black text-slate-900">{latestMetrics.length}</p>
        </article>
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="grid gap-3 md:grid-cols-3">
          <div>
            <label htmlFor="ml-model-filter" className="mb-1 block text-xs font-semibold uppercase text-slate-500">
              Model
            </label>
            <Select value={selectedModel} onValueChange={(value) => void handleModelChange(value)}>
              <SelectTrigger id="ml-model-filter" className="w-full">
                <SelectValue placeholder="All models" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All models</SelectItem>
                {modelOptions.map((modelName) => (
                  <SelectItem key={modelName} value={modelName}>
                    {modelName}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
      </section>

      {loading ? (
        <section className="rounded-xl border border-slate-200 bg-white px-4 py-10 text-center text-slate-500 shadow-sm">
          Loading model metrics...
        </section>
      ) : errorMessage ? (
        <section className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-4 text-sm text-rose-700">
          {errorMessage}
        </section>
      ) : (
        <>
          <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <h2 className="text-lg font-bold text-slate-900">Latest Model Metrics</h2>
            {displayedLatest.length === 0 ? (
              <p className="mt-3 text-sm text-slate-500">No latest metrics available.</p>
            ) : (
              <div className="mt-3 overflow-x-auto">
                <table className="min-w-full text-sm">
                  <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
                    <tr>
                      <th className="px-3 py-2">Model</th>
                      <th className="px-3 py-2">Version</th>
                      <th className="px-3 py-2">Accuracy</th>
                      <th className="px-3 py-2">Precision</th>
                      <th className="px-3 py-2">Recall</th>
                      <th className="px-3 py-2">F1</th>
                      <th className="px-3 py-2">Evaluated</th>
                    </tr>
                  </thead>
                  <tbody>
                    {displayedLatest.map((metric) => (
                      <tr key={metric.id} className="border-t border-slate-100">
                        <td className="px-3 py-2 font-semibold text-slate-800">{metric.model_name}</td>
                        <td className="px-3 py-2 text-slate-700">{metric.model_version}</td>
                        <td className="px-3 py-2 text-slate-700">{percentage(metric.accuracy)}</td>
                        <td className="px-3 py-2 text-slate-700">{percentage(metric.precision)}</td>
                        <td className="px-3 py-2 text-slate-700">{percentage(metric.recall)}</td>
                        <td className="px-3 py-2 text-slate-700">{percentage(metric.f1_score)}</td>
                        <td className="px-3 py-2 text-slate-500">{formatDate(metric.evaluated_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <h2 className="text-lg font-bold text-slate-900">Performance Summary</h2>
            {Object.keys(summary.models).length === 0 ? (
              <p className="mt-3 text-sm text-slate-500">No performance summary available.</p>
            ) : (
              <div className="mt-3 grid gap-3 md:grid-cols-2 lg:grid-cols-3">
                {Object.entries(summary.models).map(([modelName, model]) => (
                  <article key={modelName} className="rounded-xl border border-slate-200 p-4">
                    <p className="text-sm font-semibold text-slate-800">{modelName}</p>
                    <p className="text-xs text-slate-500">Version: {model.version}</p>
                    <div className="mt-2 grid grid-cols-2 gap-2 text-xs text-slate-600">
                      <span>Acc: {percentage(model.accuracy)}</span>
                      <span>Prec: {percentage(model.precision)}</span>
                      <span>Rec: {percentage(model.recall)}</span>
                      <span>F1: {percentage(model.f1_score)}</span>
                    </div>
                    <p className="mt-2 text-xs text-slate-500">Evaluated: {formatDate(model.last_evaluated)}</p>
                  </article>
                ))}
              </div>
            )}
          </section>

          <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 className="text-lg font-bold text-slate-900">Model History</h2>
              <Button type="button" variant="outline" onClick={exportHistoryCsv} disabled={history.length === 0}>
                <Download className="mr-2 h-4 w-4" />
                Export History CSV
              </Button>
            </div>
            {history.length === 0 ? (
              <p className="mt-3 text-sm text-slate-500">No history available for selected model.</p>
            ) : (
              <div className="mt-3 overflow-x-auto">
                <table className="min-w-full text-sm">
                  <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
                    <tr>
                      <th className="px-3 py-2">Version</th>
                      <th className="px-3 py-2">Accuracy</th>
                      <th className="px-3 py-2">Precision</th>
                      <th className="px-3 py-2">Recall</th>
                      <th className="px-3 py-2">F1</th>
                      <th className="px-3 py-2">Trained</th>
                      <th className="px-3 py-2">Evaluated</th>
                    </tr>
                  </thead>
                  <tbody>
                    {history.map((metric) => (
                      <tr key={metric.id} className="border-t border-slate-100">
                        <td className="px-3 py-2 text-slate-700">{metric.model_version}</td>
                        <td className="px-3 py-2 text-slate-700">{percentage(metric.accuracy)}</td>
                        <td className="px-3 py-2 text-slate-700">{percentage(metric.precision)}</td>
                        <td className="px-3 py-2 text-slate-700">{percentage(metric.recall)}</td>
                        <td className="px-3 py-2 text-slate-700">{percentage(metric.f1_score)}</td>
                        <td className="px-3 py-2 text-slate-500">{formatDate(metric.trained_at)}</td>
                        <td className="px-3 py-2 text-slate-500">{formatDate(metric.evaluated_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </>
      )}
    </main>
  );
};

export default MlMonitoringPage;
