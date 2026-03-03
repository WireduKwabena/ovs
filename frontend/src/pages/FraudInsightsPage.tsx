import React, { useCallback, useEffect, useMemo, useState } from "react";
import { AlertTriangle, RefreshCw, ShieldAlert, ShieldCheck, Users } from "lucide-react";
import { toast } from "react-toastify";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { fraudService } from "@/services/fraud.service";
import type {
  ConsistencyCheckApiResult,
  ConsistencyStatistics,
  FraudDetectionApiResult,
  FraudStatistics,
  SocialProfileCheckApiResult,
  SocialProfileStatistics,
} from "@/types";
import { formatDate } from "@/utils/helper";

type RiskFilter = "all" | "high" | "medium" | "low";
type ConsistencyFilter = "all" | "true" | "false";

const defaultFraudStats: FraudStatistics = {
  total_scans: 0,
  fraud_detected: 0,
  fraud_rate: 0,
  risk_distribution: {
    HIGH: 0,
    MEDIUM: 0,
    LOW: 0,
  },
};

const defaultConsistencyStats: ConsistencyStatistics = {
  total_checks: 0,
  consistent_count: 0,
  consistency_rate: 0,
  average_score: 0,
  median_score: 0,
};

const defaultSocialStats: SocialProfileStatistics = {
  total_checks: 0,
  manual_review_count: 0,
  manual_review_rate: 0,
  average_score: 0,
  risk_distribution: {
    HIGH: 0,
    MEDIUM: 0,
    LOW: 0,
  },
};

const riskPillClass: Record<"LOW" | "MEDIUM" | "HIGH", string> = {
  LOW: "bg-emerald-100 text-emerald-700",
  MEDIUM: "bg-amber-100 text-amber-700",
  HIGH: "bg-rose-100 text-rose-700",
};

const FraudInsightsPage: React.FC = () => {
  const [caseFilter, setCaseFilter] = useState("");
  const [riskFilter, setRiskFilter] = useState<RiskFilter>("all");
  const [consistencyFilter, setConsistencyFilter] = useState<ConsistencyFilter>("all");

  const [fraudResults, setFraudResults] = useState<FraudDetectionApiResult[]>([]);
  const [consistencyResults, setConsistencyResults] = useState<ConsistencyCheckApiResult[]>([]);
  const [socialProfileResults, setSocialProfileResults] = useState<SocialProfileCheckApiResult[]>([]);

  const [fraudStats, setFraudStats] = useState<FraudStatistics>(defaultFraudStats);
  const [consistencyStats, setConsistencyStats] = useState<ConsistencyStatistics>(defaultConsistencyStats);
  const [socialStats, setSocialStats] = useState<SocialProfileStatistics>(defaultSocialStats);

  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const loadInsights = useCallback(async () => {
    setErrorMessage(null);
    try {
      const [fraud, fraudStatistics, consistency, consistencyStatistics, social, socialStatistics] =
        await Promise.all([
          fraudService.listFraudResults({
            case_id: caseFilter.trim() || undefined,
            risk_level: riskFilter,
          }),
          fraudService.getFraudStatistics(),
          fraudService.listConsistencyResults({
            case_id: caseFilter.trim() || undefined,
            consistent: consistencyFilter,
          }),
          fraudService.getConsistencyStatistics(),
          fraudService.listSocialProfileResults({
            case_id: caseFilter.trim() || undefined,
            risk_level: riskFilter,
          }),
          fraudService.getSocialProfileStatistics(),
        ]);

      setFraudResults(fraud);
      setFraudStats(fraudStatistics);
      setConsistencyResults(consistency);
      setConsistencyStats(consistencyStatistics);
      setSocialProfileResults(social);
      setSocialStats(socialStatistics);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to fetch fraud insights.";
      setErrorMessage(message);
      toast.error(message);
    }
  }, [caseFilter, consistencyFilter, riskFilter]);

  useEffect(() => {
    const run = async () => {
      setLoading(true);
      await loadInsights();
      setLoading(false);
    };
    void run();
  }, [loadInsights]);

  const handleRefresh = async () => {
    setRefreshing(true);
    await loadInsights();
    setRefreshing(false);
  };

  const fraudRows = useMemo(() => fraudResults.slice(0, 12), [fraudResults]);
  const consistencyRows = useMemo(() => consistencyResults.slice(0, 12), [consistencyResults]);
  const socialRows = useMemo(() => socialProfileResults.slice(0, 12), [socialProfileResults]);

  return (
    <main className="mx-auto max-w-7xl px-4 py-8 space-y-6">
      <header className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-3xl font-black tracking-tight text-slate-900">Fraud & Consistency Insights</h1>
            <p className="mt-1 text-sm text-slate-600">
              Monitor fraud detection, cross-document consistency, and social profile risk signals.
            </p>
          </div>
          <Button type="button" variant="outline" onClick={() => void handleRefresh()} disabled={refreshing}>
            <RefreshCw className={`mr-2 h-4 w-4 ${refreshing ? "animate-spin" : ""}`} />
            Refresh
          </Button>
        </div>
      </header>

      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="text-lg font-bold text-slate-900">Filters</h2>
        <div className="mt-4 grid gap-3 md:grid-cols-3">
          <div>
            <label htmlFor="fraud-case-filter" className="mb-1 block text-xs font-semibold uppercase text-slate-500">
              Case ID
            </label>
            <Input
              id="fraud-case-filter"
              value={caseFilter}
              onChange={(event) => setCaseFilter(event.target.value)}
              placeholder="VET-2026..."
            />
          </div>
          <div>
            <label htmlFor="fraud-risk-filter" className="mb-1 block text-xs font-semibold uppercase text-slate-500">
              Risk Level
            </label>
            <Select value={riskFilter} onValueChange={(value) => setRiskFilter(value as RiskFilter)}>
              <SelectTrigger id="fraud-risk-filter" className="w-full">
                <SelectValue placeholder="All risk levels" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All risk levels</SelectItem>
                <SelectItem value="high">High</SelectItem>
                <SelectItem value="medium">Medium</SelectItem>
                <SelectItem value="low">Low</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div>
            <label htmlFor="fraud-consistency-filter" className="mb-1 block text-xs font-semibold uppercase text-slate-500">
              Consistency
            </label>
            <Select value={consistencyFilter} onValueChange={(value) => setConsistencyFilter(value as ConsistencyFilter)}>
              <SelectTrigger id="fraud-consistency-filter" className="w-full">
                <SelectValue placeholder="All" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All</SelectItem>
                <SelectItem value="true">Consistent only</SelectItem>
                <SelectItem value="false">Inconsistent only</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-3">
        <article className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <p className="text-sm text-slate-500">Fraud Detection</p>
            <AlertTriangle className="h-5 w-5 text-rose-500" />
          </div>
          <p className="mt-2 text-3xl font-black text-slate-900">{fraudStats.total_scans}</p>
          <p className="text-sm text-slate-600">
            {fraudStats.fraud_detected} flagged ({fraudStats.fraud_rate.toFixed(1)}%)
          </p>
        </article>

        <article className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <p className="text-sm text-slate-500">Consistency Checks</p>
            <ShieldCheck className="h-5 w-5 text-emerald-500" />
          </div>
          <p className="mt-2 text-3xl font-black text-slate-900">{consistencyStats.total_checks}</p>
          <p className="text-sm text-slate-600">
            {consistencyStats.consistent_count} consistent ({consistencyStats.consistency_rate.toFixed(1)}%)
          </p>
        </article>

        <article className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <p className="text-sm text-slate-500">Social Profile Checks</p>
            <Users className="h-5 w-5 text-indigo-500" />
          </div>
          <p className="mt-2 text-3xl font-black text-slate-900">{socialStats.total_checks}</p>
          <p className="text-sm text-slate-600">
            Manual review: {socialStats.manual_review_count} ({socialStats.manual_review_rate.toFixed(1)}%)
          </p>
        </article>
      </section>

      {loading ? (
        <section className="rounded-xl border border-slate-200 bg-white px-4 py-10 text-center text-slate-500 shadow-sm">
          Loading insights...
        </section>
      ) : errorMessage ? (
        <section className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-4 text-sm text-rose-700">
          {errorMessage}
        </section>
      ) : (
        <>
          <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <h2 className="text-lg font-bold text-slate-900">Fraud Results</h2>
            {fraudRows.length === 0 ? (
              <p className="mt-3 text-sm text-slate-500">No fraud results available for current filters.</p>
            ) : (
              <div className="mt-3 overflow-x-auto">
                <table className="min-w-full text-sm">
                  <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
                    <tr>
                      <th className="px-3 py-2">Case</th>
                      <th className="px-3 py-2">Risk</th>
                      <th className="px-3 py-2">Fraud Probability</th>
                      <th className="px-3 py-2">Recommendation</th>
                      <th className="px-3 py-2">Detected</th>
                    </tr>
                  </thead>
                  <tbody>
                    {fraudRows.map((row) => (
                      <tr key={row.id} className="border-t border-slate-100">
                        <td className="px-3 py-2 font-semibold text-slate-800">{row.application_case_id}</td>
                        <td className="px-3 py-2">
                          <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${riskPillClass[row.risk_level]}`}>
                            {row.risk_level}
                          </span>
                        </td>
                        <td className="px-3 py-2 text-slate-700">{(row.fraud_probability * 100).toFixed(1)}%</td>
                        <td className="px-3 py-2 text-slate-700">{row.recommendation}</td>
                        <td className="px-3 py-2 text-slate-500">{formatDate(row.detected_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <h2 className="text-lg font-bold text-slate-900">Consistency Results</h2>
            {consistencyRows.length === 0 ? (
              <p className="mt-3 text-sm text-slate-500">No consistency results available for current filters.</p>
            ) : (
              <div className="mt-3 overflow-x-auto">
                <table className="min-w-full text-sm">
                  <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
                    <tr>
                      <th className="px-3 py-2">Case</th>
                      <th className="px-3 py-2">Consistent</th>
                      <th className="px-3 py-2">Score</th>
                      <th className="px-3 py-2">Recommendation</th>
                      <th className="px-3 py-2">Checked</th>
                    </tr>
                  </thead>
                  <tbody>
                    {consistencyRows.map((row) => (
                      <tr key={row.id} className="border-t border-slate-100">
                        <td className="px-3 py-2 font-semibold text-slate-800">{row.application_case_id}</td>
                        <td className="px-3 py-2">
                          {row.overall_consistent ? (
                            <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-semibold text-emerald-700">
                              Yes
                            </span>
                          ) : (
                            <span className="rounded-full bg-rose-100 px-2 py-0.5 text-xs font-semibold text-rose-700">
                              No
                            </span>
                          )}
                        </td>
                        <td className="px-3 py-2 text-slate-700">{row.overall_score.toFixed(1)}</td>
                        <td className="px-3 py-2 text-slate-700">{row.recommendation}</td>
                        <td className="px-3 py-2 text-slate-500">{formatDate(row.checked_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <h2 className="text-lg font-bold text-slate-900">Social Profile Results</h2>
            {socialRows.length === 0 ? (
              <p className="mt-3 text-sm text-slate-500">No social profile results available for current filters.</p>
            ) : (
              <div className="mt-3 overflow-x-auto">
                <table className="min-w-full text-sm">
                  <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
                    <tr>
                      <th className="px-3 py-2">Case</th>
                      <th className="px-3 py-2">Risk</th>
                      <th className="px-3 py-2">Profiles Checked</th>
                      <th className="px-3 py-2">Recommendation</th>
                      <th className="px-3 py-2">Checked</th>
                    </tr>
                  </thead>
                  <tbody>
                    {socialRows.map((row) => (
                      <tr key={row.id} className="border-t border-slate-100">
                        <td className="px-3 py-2 font-semibold text-slate-800">{row.application_case_id}</td>
                        <td className="px-3 py-2">
                          <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${riskPillClass[row.risk_level]}`}>
                            {row.risk_level}
                          </span>
                        </td>
                        <td className="px-3 py-2 text-slate-700">{row.profiles_checked}</td>
                        <td className="px-3 py-2 text-slate-700">{row.recommendation}</td>
                        <td className="px-3 py-2 text-slate-500">{formatDate(row.checked_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <h2 className="text-lg font-bold text-slate-900">Distribution Snapshot</h2>
            <div className="mt-3 grid gap-4 md:grid-cols-3">
              <div className="rounded-lg border border-slate-200 p-3">
                <p className="text-xs uppercase text-slate-500">Fraud Risk Distribution</p>
                <p className="mt-2 text-sm text-slate-700">
                  High: {fraudStats.risk_distribution.HIGH} | Medium: {fraudStats.risk_distribution.MEDIUM} | Low:{" "}
                  {fraudStats.risk_distribution.LOW}
                </p>
              </div>
              <div className="rounded-lg border border-slate-200 p-3">
                <p className="text-xs uppercase text-slate-500">Consistency Scores</p>
                <p className="mt-2 text-sm text-slate-700">
                  Avg: {consistencyStats.average_score.toFixed(1)} | Median: {consistencyStats.median_score.toFixed(1)}
                </p>
              </div>
              <div className="rounded-lg border border-slate-200 p-3">
                <p className="text-xs uppercase text-slate-500">Social Risk Distribution</p>
                <p className="mt-2 text-sm text-slate-700">
                  High: {socialStats.risk_distribution.HIGH} | Medium: {socialStats.risk_distribution.MEDIUM} | Low:{" "}
                  {socialStats.risk_distribution.LOW}
                </p>
              </div>
            </div>
            <p className="mt-4 inline-flex items-center gap-2 text-xs text-slate-500">
              <ShieldAlert className="h-4 w-4" />
              Social profile checks are advisory and should not be used for automated final decisions.
            </p>
          </section>
        </>
      )}
    </main>
  );
};

export default FraudInsightsPage;
