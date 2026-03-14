import React, { useCallback, useEffect, useMemo, useState } from "react";
import { AlertTriangle, Brain, FileSearch, Plus, RefreshCw, ScanFace, Trash2 } from "lucide-react";
import { Link } from "react-router-dom";
import { toast } from "react-toastify";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { aiMonitorService } from "@/services/aiMonitor.service";
import type {
  AiMonitorClassifierModelResult,
  AiMonitorDocumentClassificationResponse,
  AiMonitorHealthResponse,
  AiMonitorSocialProfileItem,
  AiMonitorSocialProfileResponse,
} from "@/types";
import { formatDate } from "@/utils/helper";
import { buildProcessingErrorNotificationTraceHref } from "@/utils/notificationTrace";

type SocialProfileRow = AiMonitorSocialProfileItem & { id: string };

const createProfileRow = (): SocialProfileRow => ({
  id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
  platform: "linkedin",
  url: "",
  username: "",
  display_name: "",
});

const scoreToPercent = (score?: number): string => {
  if (typeof score !== "number") {
    return "-";
  }
  return `${(score * 100).toFixed(2)}%`;
};

const riskPillClass = (riskLevel: string): string => {
  const normalized = riskLevel.toLowerCase();
  if (normalized === "low") return "bg-emerald-100 text-emerald-700";
  if (normalized === "medium") return "bg-amber-100 text-amber-700";
  if (normalized === "high") return "bg-rose-100 text-rose-700";
  return "bg-slate-200 text-slate-800";
};

const ProcessingErrorTraceCallout: React.FC<{
  message: string;
  className?: string;
}> = ({ message, className = "mt-4" }) => (
  <div className={`${className} rounded-lg border border-rose-200 bg-rose-50 px-3 py-3 text-sm text-rose-800`}>
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div className="inline-flex items-start gap-2">
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
        <div>
          <p>{message}</p>
          <p className="mt-1 text-xs text-rose-700">
            Review operational processing error notifications for related backend failures.
          </p>
        </div>
      </div>
      <Link
        to={buildProcessingErrorNotificationTraceHref()}
        className="inline-flex items-center justify-center rounded-md border border-rose-300 bg-white px-3 py-1.5 text-xs font-medium text-rose-800 hover:bg-rose-100"
      >
        Open processing errors
      </Link>
    </div>
  </div>
);

const AiMonitorPage: React.FC = () => {
  const [modelName, setModelName] = useState("default");
  const [healthLoading, setHealthLoading] = useState(false);
  const [health, setHealth] = useState<AiMonitorHealthResponse | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);

  const [documentFile, setDocumentFile] = useState<File | null>(null);
  const [documentType, setDocumentType] = useState("");
  const [topK, setTopK] = useState("3");
  const [classifyLoading, setClassifyLoading] = useState(false);
  const [classification, setClassification] = useState<AiMonitorDocumentClassificationResponse | null>(null);
  const [classificationError, setClassificationError] = useState<string | null>(null);

  const [socialCaseId, setSocialCaseId] = useState("");
  const [socialConsent, setSocialConsent] = useState(true);
  const [socialProfiles, setSocialProfiles] = useState<SocialProfileRow[]>([createProfileRow()]);
  const [socialLoading, setSocialLoading] = useState(false);
  const [socialResult, setSocialResult] = useState<AiMonitorSocialProfileResponse | null>(null);
  const [socialError, setSocialError] = useState<string | null>(null);

  const fetchHealth = useCallback(async (name: string) => {
    setHealthLoading(true);
    setHealthError(null);
    try {
      const response = await aiMonitorService.health({ model_name: name });
      setHealth(response);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to fetch AI monitor health.";
      setHealthError(message);
      toast.error(message);
    } finally {
      setHealthLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchHealth("default");
  }, [fetchHealth]);

  const handleHealthRefresh = async () => {
    const target = modelName.trim() || "default";
    await fetchHealth(target);
  };

  const handleClassifyDocument = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setClassificationError(null);
    if (!documentFile) {
      toast.error("Select a document image or PDF to classify.");
      return;
    }

    const parsedTopK = Number(topK);
    if (!Number.isFinite(parsedTopK) || parsedTopK < 1 || parsedTopK > 5) {
      toast.error("Top-K must be between 1 and 5.");
      return;
    }

    setClassifyLoading(true);
    try {
      const response = await aiMonitorService.classifyDocument({
        file: documentFile,
        document_type: documentType.trim() || undefined,
        top_k: parsedTopK,
      });
      setClassification(response);
      setClassificationError(null);
      toast.success("Document classified successfully.");
    } catch (error) {
      const message = error instanceof Error ? error.message : "Document classification failed.";
      setClassificationError(message);
      toast.error(message);
    } finally {
      setClassifyLoading(false);
    }
  };

  const addSocialProfileRow = () => {
    setSocialProfiles((current) => [...current, createProfileRow()]);
  };

  const removeSocialProfileRow = (id: string) => {
    setSocialProfiles((current) => {
      if (current.length === 1) {
        return current;
      }
      return current.filter((item) => item.id !== id);
    });
  };

  const updateSocialProfileRow = (id: string, key: keyof AiMonitorSocialProfileItem, value: string) => {
    setSocialProfiles((current) =>
      current.map((item) => (item.id === id ? { ...item, [key]: value } : item)),
    );
  };

  const normalizedProfiles = useMemo(
    () =>
      socialProfiles
        .map(({ platform, url, username, display_name }) => ({
          platform: (platform || "").trim(),
          url: (url || "").trim(),
          username: (username || "").trim(),
          display_name: (display_name || "").trim(),
        }))
        .filter((item) => item.platform || item.url || item.username || item.display_name),
    [socialProfiles],
  );

  const handleSocialCheck = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSocialError(null);
    if (normalizedProfiles.length === 0) {
      toast.error("Add at least one social profile entry.");
      return;
    }

    setSocialLoading(true);
    try {
      const response = await aiMonitorService.checkSocialProfiles({
        case_id: socialCaseId.trim() || undefined,
        consent_provided: socialConsent,
        profiles: normalizedProfiles,
      });
      setSocialResult(response);
      setSocialError(null);
      toast.success("Social profile check completed.");
    } catch (error) {
      const message = error instanceof Error ? error.message : "Social profile check failed.";
      setSocialError(message);
      toast.error(message);
    } finally {
      setSocialLoading(false);
    }
  };

  const renderClassifierCard = (title: string, result?: AiMonitorClassifierModelResult) => {
    if (!result) {
      return null;
    }

    return (
      <article className="rounded-xl border border-slate-200 p-4">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-slate-900">{title}</h3>
          <span
            className={`rounded-full px-2 py-0.5 text-xs font-semibold ${
              result.available ? "bg-emerald-100 text-emerald-700" : "bg-rose-100 text-rose-700"
            }`}
          >
            {result.available ? "available" : "unavailable"}
          </span>
        </div>

        {!result.available ? (
          <p className="mt-2 text-xs text-rose-700">{result.error || "Model unavailable."}</p>
        ) : (
          <>
            <p className="mt-2 text-sm text-slate-700">
              Label: <span className="font-semibold text-slate-900">{result.predicted_label || "-"}</span>
            </p>
            <p className="text-sm text-slate-700">
              Confidence: <span className="font-semibold text-slate-900">{scoreToPercent(result.confidence)}</span>
            </p>
            {Array.isArray(result.top_k) && result.top_k.length > 0 ? (
              <div className="mt-3 overflow-x-auto">
                <table className="min-w-full text-xs">
                  <thead className="bg-slate-50 text-left uppercase text-slate-700">
                    <tr>
                      <th className="px-2 py-1">Label</th>
                      <th className="px-2 py-1">Score</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.top_k.map((item) => (
                      <tr key={`${title}-${item.label}`} className="border-t border-slate-100">
                        <td className="px-2 py-1 text-slate-700">{item.label}</td>
                        <td className="px-2 py-1 text-slate-700">{scoreToPercent(item.score)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : null}
          </>
        )}
      </article>
    );
  };

  return (
    <main className="mx-auto max-w-7xl space-y-6 px-4 py-8">
      <header className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <h1 className="text-3xl font-black tracking-tight text-slate-900">AI Monitor</h1>
        <p className="mt-1 text-sm text-slate-700">
          Runtime model health, document type classification, and advisory social profile checks.
        </p>
      </header>

      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Brain className="h-5 w-5 text-indigo-600" />
            <h2 className="text-lg font-bold text-slate-900">Model Health</h2>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Input
              value={modelName}
              onChange={(event) => setModelName(event.target.value)}
              placeholder="default"
              className="w-48"
            />
            <Button type="button" variant="outline" onClick={() => void handleHealthRefresh()} disabled={healthLoading}>
              <RefreshCw className={`mr-2 h-4 w-4 ${healthLoading ? "animate-spin" : ""}`} />
              Refresh
            </Button>
          </div>
        </div>

        {healthError ? (
          <ProcessingErrorTraceCallout message={healthError} />
        ) : null}

        {health ? (
          <div className="mt-4 grid gap-3 md:grid-cols-3">
            <article className="rounded-xl border border-slate-200 p-4">
              <p className="text-xs uppercase text-slate-700">Model</p>
              <p className="mt-1 text-sm font-semibold text-slate-900">{health.model_name}</p>
              <p className="mt-1 text-xs text-slate-700">Updated {formatDate(health.timestamp)}</p>
            </article>
            <article className="rounded-xl border border-slate-200 p-4">
              <p className="text-xs uppercase text-slate-700">Monitor</p>
              <p className="mt-1 text-sm font-semibold text-slate-900">
                {health.monitor.enabled ? "Enabled" : "Disabled"}
              </p>
              <p className="mt-1 text-xs text-slate-700">
                backend: {health.monitor.backend || "-"} | redis:{" "}
                {health.monitor.redis_configured ? "configured" : "not configured"}
              </p>
            </article>
            <article className="rounded-xl border border-slate-200 p-4">
              <p className="text-xs uppercase text-slate-700">Status</p>
              <p className="mt-1 text-sm font-semibold text-slate-900">{health.status}</p>
              <p className="mt-1 text-xs text-slate-700">use_redis: {health.monitor.use_redis ? "true" : "false"}</p>
            </article>
          </div>
        ) : null}
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex items-center gap-2">
          <FileSearch className="h-5 w-5 text-cyan-600" />
          <h2 className="text-lg font-bold text-slate-900">Document Classification</h2>
        </div>

        <form className="mt-4 grid gap-3 md:grid-cols-3" onSubmit={handleClassifyDocument}>
          <div>
            <label htmlFor="ai-monitor-file" className="mb-1 block text-xs font-semibold uppercase text-slate-700">
              File
            </label>
            <Input
              id="ai-monitor-file"
              type="file"
              accept="image/*,.pdf"
              onChange={(event) => setDocumentFile(event.target.files?.[0] || null)}
              disabled={classifyLoading}
            />
          </div>
          <div>
            <label
              htmlFor="ai-monitor-document-type"
              className="mb-1 block text-xs font-semibold uppercase text-slate-700"
            >
              Declared Document Type
            </label>
            <Input
              id="ai-monitor-document-type"
              placeholder="passport, id_card, resume..."
              value={documentType}
              onChange={(event) => setDocumentType(event.target.value)}
              disabled={classifyLoading}
            />
          </div>
          <div>
            <label htmlFor="ai-monitor-top-k" className="mb-1 block text-xs font-semibold uppercase text-slate-700">
              Top-K
            </label>
            <Select value={topK} onValueChange={setTopK}>
              <SelectTrigger id="ai-monitor-top-k">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="1">1</SelectItem>
                <SelectItem value="2">2</SelectItem>
                <SelectItem value="3">3</SelectItem>
                <SelectItem value="4">4</SelectItem>
                <SelectItem value="5">5</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="md:col-span-3">
            <Button type="submit" disabled={classifyLoading}>
              {classifyLoading ? "Classifying..." : "Classify Document"}
            </Button>
          </div>
        </form>

        {classificationError ? (
          <ProcessingErrorTraceCallout
            message={classificationError}
            className="mt-4"
          />
        ) : null}

        {classification ? (
          <div className="mt-4 space-y-3">
            <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700">
              File: <span className="font-semibold text-slate-900">{classification.filename}</span>
            </div>
            <div className="grid gap-3 md:grid-cols-2">
              {renderClassifierCard("RVL-CDIP", classification.document_classification?.rvl_cdip)}
              {renderClassifierCard("MIDV-500", classification.document_classification?.midv500)}
            </div>
            <div className="rounded-xl border border-slate-200 p-4">
              <p className="text-sm font-semibold text-slate-900">Document Type Alignment</p>
              <p className="mt-1 text-sm text-slate-700">
                Mismatch detected:{" "}
                <span className="font-semibold">
                  {classification.document_type_alignment?.mismatch_detected ? "yes" : "no"}
                </span>
              </p>
              {classification.document_type_alignment?.mismatch_reason ? (
                <p className="mt-1 text-sm text-rose-700">{classification.document_type_alignment.mismatch_reason}</p>
              ) : null}
              {Array.isArray(classification.document_type_alignment?.details) &&
              classification.document_type_alignment.details.length > 0 ? (
                <ul className="mt-2 list-disc space-y-1 pl-5 text-xs text-slate-700">
                  {classification.document_type_alignment.details.map((item, index) => (
                    <li key={`detail-${index}`}>
                      {item.model ? `${item.model}: ` : ""}
                      {item.reason || "Mismatch details available"}
                    </li>
                  ))}
                </ul>
              ) : null}
            </div>
          </div>
        ) : null}
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex items-center gap-2">
          <ScanFace className="h-5 w-5 text-violet-600" />
          <h2 className="text-lg font-bold text-slate-900">Advisory Social Profile Check</h2>
        </div>

        <form className="mt-4 space-y-3" onSubmit={handleSocialCheck}>
          <div className="grid gap-3 md:grid-cols-3">
            <div>
              <label htmlFor="social-case-id" className="mb-1 block text-xs font-semibold uppercase text-slate-700">
                Case ID (Optional)
              </label>
              <Input
                id="social-case-id"
                value={socialCaseId}
                onChange={(event) => setSocialCaseId(event.target.value)}
                placeholder="CASE-2026-001"
                disabled={socialLoading}
              />
            </div>
            <div className="flex items-end">
              <label className="inline-flex items-center gap-2 text-sm text-slate-700">
                <input
                  type="checkbox"
                  checked={socialConsent}
                  onChange={(event) => setSocialConsent(event.target.checked)}
                  disabled={socialLoading}
                />
                Consent provided
              </label>
            </div>
          </div>

          <div className="space-y-2">
            {socialProfiles.map((profile) => (
              <div key={profile.id} className="grid gap-2 rounded-xl border border-slate-200 p-3 md:grid-cols-5">
                <Input
                  placeholder="platform"
                  value={profile.platform || ""}
                  onChange={(event) => updateSocialProfileRow(profile.id, "platform", event.target.value)}
                  disabled={socialLoading}
                />
                <Input
                  placeholder="url"
                  value={profile.url || ""}
                  onChange={(event) => updateSocialProfileRow(profile.id, "url", event.target.value)}
                  disabled={socialLoading}
                />
                <Input
                  placeholder="username"
                  value={profile.username || ""}
                  onChange={(event) => updateSocialProfileRow(profile.id, "username", event.target.value)}
                  disabled={socialLoading}
                />
                <Input
                  placeholder="display name"
                  value={profile.display_name || ""}
                  onChange={(event) => updateSocialProfileRow(profile.id, "display_name", event.target.value)}
                  disabled={socialLoading}
                />
                <div className="flex items-center justify-end">
                  <Button
                    type="button"
                    variant="ghost"
                    onClick={() => removeSocialProfileRow(profile.id)}
                    disabled={socialLoading || socialProfiles.length === 1}
                  >
                    <Trash2 className="mr-1 h-4 w-4" />
                    Remove
                  </Button>
                </div>
              </div>
            ))}
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Button type="button" variant="outline" onClick={addSocialProfileRow} disabled={socialLoading}>
              <Plus className="mr-2 h-4 w-4" />
              Add Profile
            </Button>
            <Button type="submit" disabled={socialLoading}>
              {socialLoading ? "Running..." : "Run Social Check"}
            </Button>
          </div>
        </form>

        {socialError ? (
          <ProcessingErrorTraceCallout
            message={socialError}
            className="mt-4"
          />
        ) : null}

        {socialResult ? (
          <div className="mt-4 space-y-3">
            <div className="grid gap-3 md:grid-cols-4">
              <article className="rounded-xl border border-slate-200 p-4">
                <p className="text-xs uppercase text-slate-700">Case</p>
                <p className="mt-1 text-sm font-semibold text-slate-900">{socialResult.case_id || "-"}</p>
              </article>
              <article className="rounded-xl border border-slate-200 p-4">
                <p className="text-xs uppercase text-slate-700">Profiles Checked</p>
                <p className="mt-1 text-sm font-semibold text-slate-900">{socialResult.profiles_checked}</p>
              </article>
              <article className="rounded-xl border border-slate-200 p-4">
                <p className="text-xs uppercase text-slate-700">Overall Score</p>
                <p className="mt-1 text-sm font-semibold text-slate-900">
                  {socialResult.overall_score.toFixed(2)}
                </p>
              </article>
              <article className="rounded-xl border border-slate-200 p-4">
                <p className="text-xs uppercase text-slate-700">Risk Level</p>
                <span className={`mt-1 inline-flex rounded-full px-2 py-1 text-xs font-semibold ${riskPillClass(socialResult.risk_level)}`}>
                  {socialResult.risk_level}
                </span>
              </article>
            </div>

            {socialResult.profiles.length > 0 ? (
              <div className="overflow-x-auto rounded-xl border border-slate-200">
                <table className="min-w-full text-sm">
                  <thead className="bg-slate-50 text-left text-xs uppercase text-slate-700">
                    <tr>
                      <th className="px-3 py-2">Platform</th>
                      <th className="px-3 py-2">Username</th>
                      <th className="px-3 py-2">Score</th>
                      <th className="px-3 py-2">Risk</th>
                      <th className="px-3 py-2">Findings</th>
                    </tr>
                  </thead>
                  <tbody>
                    {socialResult.profiles.map((profile, index) => (
                      <tr key={`${profile.platform || "profile"}-${index}`} className="border-t border-slate-100">
                        <td className="px-3 py-2 text-slate-700">{profile.platform || "-"}</td>
                        <td className="px-3 py-2 text-slate-700">{profile.username || "-"}</td>
                        <td className="px-3 py-2 text-slate-700">{profile.score.toFixed(2)}</td>
                        <td className="px-3 py-2">
                          <span
                            className={`inline-flex rounded-full px-2 py-1 text-xs font-semibold ${riskPillClass(profile.risk_level)}`}
                          >
                            {profile.risk_level}
                          </span>
                        </td>
                        <td className="px-3 py-2 text-slate-700">
                          {Array.isArray(profile.findings) && profile.findings.length > 0
                            ? profile.findings.join(", ")
                            : "-"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700">
                No profile-level records returned.
              </p>
            )}
          </div>
        ) : null}
      </section>
    </main>
  );
};

export default AiMonitorPage;
