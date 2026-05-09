// src/pages/ApplicationDetailPage.tsx
import React, { useEffect, useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import {
  ArrowLeft,
  FileText,
  CheckCircle,
  XCircle,
  Clock,
  AlertTriangle,
} from "lucide-react";
import { useApplications } from "@/hooks/useApplications";
import { HelpTooltip } from "@/components/common/FieldHelp";
import { applicationService } from "@/services/application.service";
import { toast } from "react-toastify";
import { useAuth } from "@/hooks/useAuth";
import type { CaseInfoRequest } from "@/types";

import { StatusBadge } from "@/components/common/StatusBadge";
import { Loader } from "@/components/common/Loader";

import { formatDate, formatFileSize } from "@/utils/helper";
import { getWorkspacePath } from "@/utils/appPaths";

export const ApplicationDetailPage: React.FC = () => {
  const { caseId } = useParams<{ caseId: string }>();
  const navigate = useNavigate();
  const { currentCase, loading, loadApplication } = useApplications();
  const {
    canManageActiveOrganizationGovernance,
    userType,
    canAdvanceAppointmentStage,
    canManageRegistry,
  } = useAuth();

  const [reviewNotes, setReviewNotes] = useState("");
  const [requestMessage, setRequestMessage] = useState("");
  const [infoRequests, setInfoRequests] = useState<CaseInfoRequest[]>([]);
  const [responseDrafts, setResponseDrafts] = useState<Record<string, string>>(
    {},
  );
  const [respondingRequestId, setRespondingRequestId] = useState<string | null>(
    null,
  );
  const [actionLoading, setActionLoading] = useState(false);
  const [activeDecision, setActiveDecision] = useState<
    "approve" | "reject" | "review" | null
  >(null);

  const canRespondToInfoRequests = userType === "applicant";

  const loadInfoRequests = async (id: string) => {
    try {
      const rows = await applicationService.listInfoRequests(id);
      setInfoRequests(rows);
    } catch {
      // non-fatal for page rendering
      setInfoRequests([]);
    }
  };

  const handleApprove = async () => {
    if (!caseId) return;
    setActionLoading(true);
    setActiveDecision("approve");
    try {
      await applicationService.update(caseId, {
        status: "approved",
        notes: reviewNotes.trim(),
      });
      toast.success("Case approved successfully");
      navigate("/workspace/applications");
    } catch {
      toast.error("Failed to approve case");
    } finally {
      setActionLoading(false);
      setActiveDecision(null);
    }
  };

  const handleReject = async () => {
    if (!caseId) return;
    if (!reviewNotes.trim()) {
      toast.error("Please provide a reason for rejection");
      return;
    }
    setActionLoading(true);
    setActiveDecision("reject");
    try {
      await applicationService.update(caseId, {
        status: "rejected",
        notes: reviewNotes.trim(),
      });
      toast.success("Case rejected");
      navigate("/workspace/applications");
    } catch {
      toast.error("Failed to reject case");
    } finally {
      setActionLoading(false);
      setActiveDecision(null);
    }
  };

  const handleRequestMoreInfo = async () => {
    if (!caseId) return;
    if (!requestMessage.trim()) {
      toast.error("Please describe what additional information is needed");
      return;
    }
    setActionLoading(true);
    setActiveDecision("review");
    try {
      await applicationService.requestMoreInfo(caseId, requestMessage.trim());
      if (reviewNotes.trim()) {
        await applicationService.update(caseId, { notes: reviewNotes.trim() });
      }
      toast.info("Information request sent to applicant");
      setRequestMessage("");
      await loadInfoRequests(caseId);
      navigate("/workspace/applications");
    } catch {
      toast.error("Failed to request more information");
    } finally {
      setActionLoading(false);
      setActiveDecision(null);
    }
  };

  const handleRespondToRequest = async (infoRequestId: string) => {
    if (!caseId) return;
    const responseText = (responseDrafts[infoRequestId] || "").trim();
    if (!responseText) {
      toast.error("Please enter your response before submitting");
      return;
    }
    setRespondingRequestId(infoRequestId);
    try {
      await applicationService.respondToInfoRequest(
        caseId,
        infoRequestId,
        responseText,
      );
      toast.success("Your response has been submitted");
      setResponseDrafts((prev) => ({ ...prev, [infoRequestId]: "" }));
      await loadInfoRequests(caseId);
      await loadApplication(caseId);
    } catch {
      toast.error("Failed to submit response");
    } finally {
      setRespondingRequestId(null);
    }
  };

  useEffect(() => {
    if (caseId) {
      loadApplication(caseId);
      loadInfoRequests(caseId);
    }
  }, [caseId, loadApplication]);

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50">
        <div className="flex justify-center items-center py-20">
          <Loader size="lg" />
        </div>
      </div>
    );
  }

  if (!currentCase) {
    return (
      <div className="min-h-screen bg-gray-50">
        <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-6 xl:px-8">
          <div className="bg-white rounded-lg shadow-sm p-12 text-center">
            <div className="text-6xl mb-4">❌</div>
            <h3 className="text-xl font-semibold text-gray-900 mb-2">
              Vetting dossier not found
            </h3>
            <button
              onClick={() => navigate("/applications")}
              className="mt-4 px-6 py-3 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700"
            >
              Back to Vetting Dossiers
            </button>
          </div>
        </div>
      </div>
    );
  }

  const applicationLabel =
    currentCase.position_applied ||
    currentCase.application_type?.replace("_", " ") ||
    "Vetting Dossier";
  const resolveDocumentName = (doc: (typeof currentCase.documents)[number]) =>
    doc.original_filename ||
    doc.file_name ||
    doc.document_type_display ||
    "Document";
  const resolveDocumentStatus = (doc: (typeof currentCase.documents)[number]) =>
    doc.status || doc.verification_status;
  const resolveDocumentConfidence = (
    doc: (typeof currentCase.documents)[number],
  ) =>
    doc.ai_confidence_score ??
    doc.verification_result?.authenticity_confidence ??
    doc.verification_result?.ocr_confidence;
  const backgroundChecksPath = `${getWorkspacePath("background-checks")}?case_id=${encodeURIComponent(currentCase.case_id)}`;

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-6 xl:px-8">
        {/* Header */}
        <button
          onClick={() => navigate("/applications")}
          className="mb-6 flex items-center gap-2 text-slate-700 hover:text-slate-900"
        >
          <ArrowLeft className="w-5 h-5" />
          Back to Vetting Dossiers
        </button>

        <div className="mb-6 rounded-xl border border-slate-200 bg-white px-5 py-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-2">
            Your Responsibilities
          </p>
          <div className="flex flex-wrap gap-2">
            {canManageRegistry && (
              <span className="rounded-full bg-indigo-100 px-3 py-0.5 text-xs font-semibold text-indigo-800">
                Registry Admin
              </span>
            )}
            {canAdvanceAppointmentStage && (
              <span className="rounded-full bg-amber-100 px-3 py-0.5 text-xs font-semibold text-amber-800">
                Vetting / Stage Review
              </span>
            )}
            {canManageActiveOrganizationGovernance && (
              <span className="rounded-full bg-emerald-100 px-3 py-0.5 text-xs font-semibold text-emerald-800">
                Case Decision Authority
              </span>
            )}
            {canRespondToInfoRequests && (
              <span className="rounded-full bg-cyan-100 px-3 py-0.5 text-xs font-semibold text-cyan-800">
                Applicant
              </span>
            )}
            {!canManageRegistry &&
              !canAdvanceAppointmentStage &&
              !canManageActiveOrganizationGovernance &&
              !canRespondToInfoRequests && (
                <span className="rounded-full bg-slate-100 px-3 py-0.5 text-xs font-semibold text-slate-600">
                  View-only access
                </span>
              )}
          </div>
        </div>

        <div className="flex justify-between items-start mb-8">
          <div>
            <h1 className="text-3xl font-bold text-gray-900 mb-2">
              {currentCase.case_id}
            </h1>
            <p className="text-slate-700 capitalize">{applicationLabel}</p>
            <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
              {currentCase.office_title || currentCase.position_applied ? (
                <span className="inline-flex rounded bg-slate-100 px-2 py-1 font-semibold text-slate-700">
                  Office:{" "}
                  {currentCase.office_title || currentCase.position_applied}
                </span>
              ) : null}
              {currentCase.appointment_exercise_name ? (
                <span className="inline-flex rounded bg-cyan-100 px-2 py-1 font-semibold text-cyan-800">
                  Exercise: {currentCase.appointment_exercise_name}
                </span>
              ) : null}
              {currentCase.appointment_exercise_id ? (
                <Link
                  to={`/campaigns/${currentCase.appointment_exercise_id}`}
                  className="inline-flex rounded bg-indigo-100 px-2 py-1 font-semibold text-indigo-800 hover:bg-indigo-200"
                >
                  Open Exercise Workspace
                </Link>
              ) : null}
              <Link
                to={`/government/appointments?dossier=${currentCase.id}`}
                className="inline-flex rounded bg-cyan-100 px-2 py-1 font-semibold text-cyan-800 hover:bg-cyan-200"
              >
                Open Linked Nomination Files
              </Link>
            </div>
          </div>
          <StatusBadge status={currentCase.status} />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Main Content */}
          <div className="lg:col-span-2 space-y-6">
            {/* Vetting Dossier Details */}
            <div className="bg-white rounded-lg shadow-sm p-6">
              <h2 className="mb-4 inline-flex items-center gap-1.5 text-xl font-semibold">
                Vetting Dossier Details
                <HelpTooltip text="Overview of core dossier metadata used in vetting and review decisions." />
              </h2>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <span className="text-sm text-slate-700">Priority</span>
                  <p className="font-medium capitalize">
                    {currentCase.priority}
                  </p>
                </div>
                <div>
                  <span className="text-sm text-slate-700">Submitted</span>
                  <p className="font-medium">
                    {formatDate(currentCase.created_at)}
                  </p>
                </div>
                <div>
                  <span className="text-sm text-slate-700">Last Updated</span>
                  <p className="font-medium">
                    {formatDate(currentCase.updated_at)}
                  </p>
                </div>
                <div>
                  <span className="text-sm text-slate-700">Documents</span>
                  <p className="font-medium">
                    {currentCase.documents?.length || 0} uploaded
                  </p>
                </div>
              </div>
              {currentCase.notes && (
                <div className="mt-4 pt-4 border-t">
                  <span className="text-sm text-slate-700">Notes</span>
                  <p className="mt-1">{currentCase.notes}</p>
                </div>
              )}
            </div>

            {/* Documents */}
            <div className="bg-white rounded-lg shadow-sm p-6">
              <div className="mb-4">
                <h2 className="inline-flex items-center gap-1.5 text-xl font-semibold">
                  Documents
                  <HelpTooltip text="Uploaded files, verification status, and AI confidence metrics for this dossier." />
                </h2>
              </div>

              {currentCase.documents && currentCase.documents.length > 0 ? (
                <div className="space-y-3">
                  {currentCase.documents.map((doc) => (
                    <div
                      key={doc.id}
                      className="flex items-center justify-between rounded-lg border border-slate-200 p-4"
                    >
                      <div className="flex items-center gap-3">
                        <FileText className="w-8 h-8 text-slate-700" />
                        <div>
                          <p className="font-medium">
                            {resolveDocumentName(doc)}
                          </p>
                          <p className="text-sm text-slate-700">
                            {doc.document_type_display || doc.document_type} •{" "}
                            {formatFileSize(doc.file_size)}
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center gap-3">
                        <StatusBadge status={resolveDocumentStatus(doc)} />
                        {typeof resolveDocumentConfidence(doc) === "number" && (
                          <span className="text-sm text-slate-700">
                            {resolveDocumentConfidence(doc)?.toFixed(1)}%
                            confidence
                          </span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-8">
                  <FileText className="w-12 h-12 text-slate-700 mx-auto mb-3" />
                  <p className="text-slate-700">No documents uploaded yet</p>
                </div>
              )}
            </div>

            {/* Verification Results */}
            {currentCase.documents && currentCase.documents.length > 0 && (
              <div className="bg-white rounded-lg shadow-sm p-6">
                <h2 className="mb-4 inline-flex items-center gap-1.5 text-xl font-semibold">
                  Verification Status
                  <HelpTooltip text="Per-document verification state plus aggregate AI consistency and fraud signals." />
                </h2>

                {currentCase.documents.map((doc) => (
                  <div key={doc.id} className="mb-4 p-4 bg-gray-50 rounded-lg">
                    <div className="flex justify-between items-start mb-2">
                      <span className="font-medium">
                        {doc.document_type_display || doc.document_type}
                      </span>
                      <StatusBadge status={resolveDocumentStatus(doc)} />
                    </div>
                    {typeof resolveDocumentConfidence(doc) === "number" && (
                      <div className="text-sm text-slate-700">
                        AI Confidence:{" "}
                        {resolveDocumentConfidence(doc)?.toFixed(1)}%
                      </div>
                    )}
                  </div>
                ))}

                {(currentCase.consistency_result ||
                  currentCase.fraud_result) && (
                  <div className="mt-6 pt-4 border-t">
                    <h3 className="font-semibold mb-3">Overall Scores</h3>
                    <div className="grid grid-cols-2 gap-4">
                      {currentCase.consistency_result && (
                        <div>
                          <span className="text-sm text-slate-700">
                            Consistency
                          </span>
                          <p className="text-2xl font-bold text-indigo-600">
                            {currentCase.consistency_result.overall_score.toFixed(
                              1,
                            )}
                            %
                          </p>
                        </div>
                      )}
                      {currentCase.fraud_result && (
                        <div>
                          <span className="text-sm text-slate-700">
                            Fraud Risk
                          </span>
                          <p className="text-2xl font-bold text-red-600">
                            {currentCase.fraud_result.fraud_probability.toFixed(
                              1,
                            )}
                            %
                          </p>
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Background Checks */}
            <div className="bg-white rounded-lg shadow-sm p-6">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <h2 className="inline-flex items-center gap-1.5 text-xl font-semibold">
                    Background Checks
                    <HelpTooltip text="Open third-party verification checks associated with this vetting dossier." />
                  </h2>
                  <p className="mt-2 text-sm text-slate-700">
                    Review and submit checks scoped to this dossier. The
                    destination page opens with this dossier already filtered.
                  </p>
                  <p className="mt-2 text-xs font-semibold uppercase tracking-wide text-slate-600">
                    Dossier Filter: {currentCase.case_id}
                  </p>
                </div>
                <Link
                  to={backgroundChecksPath}
                  className="inline-flex items-center rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700"
                >
                  Open Background Checks
                </Link>
              </div>
            </div>
          </div>

          {/* Sidebar */}
          <div className="space-y-6">
            {/* Status Timeline */}
            <div className="bg-white rounded-lg shadow-sm p-6">
              <h3 className="mb-4 inline-flex items-center gap-1.5 font-semibold">
                Status Timeline
                <HelpTooltip text="Chronological progression of the vetting dossier through submission, review, and outcome." />
              </h3>
              <div className="space-y-4">
                <div className="flex gap-3">
                  <div className="flex flex-col items-center">
                    <CheckCircle className="w-5 h-5 text-green-500" />
                    <div className="w-px h-full bg-gray-300 mt-2"></div>
                  </div>
                  <div>
                    <p className="font-medium">Submitted</p>
                    <p className="text-sm text-slate-700">
                      {formatDate(currentCase.created_at)}
                    </p>
                  </div>
                </div>

                {currentCase.status !== "pending" && (
                  <div className="flex gap-3">
                    <div className="flex flex-col items-center">
                      <Clock className="w-5 h-5 text-blue-500" />
                      {currentCase.status !== "under_review" &&
                        currentCase.status !== "info_requested" && (
                          <div className="w-px h-full bg-gray-300 mt-2"></div>
                        )}
                    </div>
                    <div>
                      <p className="font-medium">Under Review</p>
                      <p className="text-sm text-slate-700">
                        {formatDate(currentCase.updated_at)}
                      </p>
                    </div>
                  </div>
                )}

                {(currentCase.status === "approved" ||
                  currentCase.status === "rejected") && (
                  <div className="flex gap-3">
                    <div className="flex flex-col items-center">
                      {currentCase.status === "approved" ? (
                        <CheckCircle className="w-5 h-5 text-green-500" />
                      ) : (
                        <XCircle className="w-5 h-5 text-red-500" />
                      )}
                    </div>
                    <div>
                      <p className="font-medium capitalize">
                        {currentCase.status}
                      </p>
                      <p className="text-sm text-slate-700">
                        {formatDate(currentCase.updated_at)}
                      </p>
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Quick Actions */}
            <div className="bg-white rounded-lg shadow-sm p-6">
              <h3 className="mb-4 inline-flex items-center gap-1.5 font-semibold">
                Quick Actions
                <HelpTooltip text="Operational shortcuts for this vetting dossier. Some actions may depend on your role permissions." />
              </h3>
              <div className="space-y-2">
                <button className="w-full px-4 py-2 text-left text-sm hover:bg-slate-100 rounded-lg transition-colors">
                  Download All Documents
                </button>
                <Link
                  to={backgroundChecksPath}
                  className="block w-full rounded-lg px-4 py-2 text-left text-sm text-indigo-700 hover:bg-indigo-50 transition-colors"
                >
                  Open Background Checks (Filtered)
                </Link>
                {canAdvanceAppointmentStage && (
                  <button className="w-full px-4 py-2 text-left text-sm hover:bg-slate-100 rounded-lg transition-colors">
                    Request Status Update
                  </button>
                )}
                {(canManageRegistry ||
                  canManageActiveOrganizationGovernance) && (
                  <button className="w-full px-4 py-2 text-left text-sm text-red-600 hover:bg-red-50 rounded-lg transition-colors">
                    Cancel Dossier
                  </button>
                )}
              </div>
            </div>

            {infoRequests.length > 0 && (
              <div className="bg-white rounded-lg shadow-sm p-6">
                <h3 className="mb-4 inline-flex items-center gap-1.5 font-semibold">
                  Information Requests
                  <HelpTooltip text="Track requests from reviewers and submit your responses here." />
                </h3>
                <div className="space-y-4">
                  {infoRequests.map((infoRequest) => {
                    const isOpen = infoRequest.status === "open";
                    const responseValue = responseDrafts[infoRequest.id] || "";
                    return (
                      <div
                        key={infoRequest.id}
                        className="rounded-lg border border-slate-200 p-4"
                      >
                        <div className="mb-2 flex items-center justify-between gap-3">
                          <p className="text-sm font-semibold text-slate-900 capitalize">
                            {infoRequest.status}
                          </p>

                          <div className="mt-2 flex flex-wrap gap-2">
                            {infoRequest.category && (
                              <span className="inline-flex items-center rounded-full bg-blue-100 px-2.5 py-1 text-xs font-medium text-blue-800 capitalize">
                                {infoRequest.category.replace("_", " ")}
                              </span>
                            )}
                            {infoRequest.status === "open" &&
                              infoRequest.due_by && (
                                <span
                                  className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium ${
                                    infoRequest.is_overdue
                                      ? "bg-red-100 text-red-800"
                                      : "bg-yellow-100 text-yellow-800"
                                  }`}
                                >
                                  {infoRequest.is_overdue
                                    ? "⚠️ Overdue"
                                    : `Due in ${infoRequest.days_remaining} day${infoRequest.days_remaining !== 1 ? "s" : ""}`}
                                </span>
                              )}
                            {infoRequest.status === "revision_requested" && (
                              <span className="inline-flex items-center rounded-full bg-orange-100 px-2.5 py-1 text-xs font-medium text-orange-800">
                                Revision Requested
                              </span>
                            )}
                          </div>
                          <p className="text-xs text-slate-600">
                            {formatDate(infoRequest.created_at)}
                          </p>
                        </div>
                        <p className="text-sm text-slate-800">
                          {infoRequest.message}
                        </p>

                        {infoRequest.response_attachments &&
                          infoRequest.response_attachments.length > 0 && (
                            <div className="mt-2 space-y-1 text-xs text-slate-600">
                              <p className="font-semibold">Attachments:</p>
                              {infoRequest.response_attachments.map(
                                (attachment) => (
                                  <div
                                    key={attachment.id}
                                    className="flex items-center gap-2"
                                  >
                                    <a
                                      href={attachment.download_url || "#"}
                                      target="_blank"
                                      rel="noopener noreferrer"
                                      className="text-indigo-600 hover:underline"
                                    >
                                      {attachment.filename}
                                    </a>
                                    <span>
                                      (
                                      {attachment.file_size &&
                                        (attachment.file_size / 1024).toFixed(
                                          1,
                                        )}{" "}
                                      KB)
                                    </span>
                                  </div>
                                ),
                              )}
                            </div>
                          )}
                        {infoRequest.response ? (
                          <div className="mt-3 rounded bg-green-50 p-3 text-sm text-green-900">
                            <p className="mb-1 font-semibold">Your response</p>
                            <p>{infoRequest.response}</p>
                          </div>
                        ) : null}

                        {canRespondToInfoRequests && isOpen && (
                          <div className="mt-3 space-y-2">
                            <textarea
                              value={responseValue}
                              onChange={(e) =>
                                setResponseDrafts((prev) => ({
                                  ...prev,
                                  [infoRequest.id]: e.target.value,
                                }))
                              }
                              className="h-24 w-full resize-none rounded-lg border border-slate-300 p-3 text-sm text-slate-900 focus:border-transparent focus:outline-none focus:ring-2 focus:ring-indigo-500"
                              placeholder="Provide the requested information..."
                            />
                            <button
                              onClick={() =>
                                handleRespondToRequest(infoRequest.id)
                              }
                              disabled={respondingRequestId === infoRequest.id}
                              className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-60"
                            >
                              {respondingRequestId === infoRequest.id
                                ? "Submitting..."
                                : "Submit Response"}
                            </button>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Decision Actions — visible to governance managers only */}
            {canManageActiveOrganizationGovernance && (
              <>
                <div className="bg-white rounded-lg shadow-sm p-6">
                  <h3 className="font-semibold mb-3 text-gray-900">
                    Review Notes
                  </h3>
                  <textarea
                    value={reviewNotes}
                    onChange={(e) => setReviewNotes(e.target.value)}
                    className="h-28 w-full resize-none rounded-lg border border-slate-300 p-3 text-sm text-slate-900 focus:border-transparent focus:outline-none focus:ring-2 focus:ring-indigo-500"
                    placeholder="Add decision notes or rejection reason..."
                  />
                  <p className="mt-1 text-xs text-slate-500">
                    {reviewNotes.length === 0
                      ? "Note is required for rejection"
                      : `${reviewNotes.length} characters`}
                  </p>
                </div>

                <div className="bg-white rounded-lg shadow-sm p-6">
                  <h3 className="font-semibold mb-3 text-gray-900">
                    Request Details
                  </h3>
                  <textarea
                    value={requestMessage}
                    onChange={(e) => setRequestMessage(e.target.value)}
                    className="h-28 w-full resize-none rounded-lg border border-slate-300 p-3 text-sm text-slate-900 focus:border-transparent focus:outline-none focus:ring-2 focus:ring-indigo-500"
                    placeholder="Describe exactly what additional information or clarification is needed..."
                  />
                  <p className="mt-1 text-xs text-slate-500">
                    {requestMessage.length === 0
                      ? "Required for Request More Info"
                      : `${requestMessage.length} characters`}
                  </p>
                </div>

                <div className="bg-white rounded-lg shadow-sm p-6">
                  <h3 className="font-semibold mb-4 text-gray-900">
                    Decision Actions
                  </h3>
                  <div className="space-y-3">
                    <button
                      onClick={handleApprove}
                      disabled={actionLoading}
                      className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 font-semibold disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                    >
                      {actionLoading && activeDecision === "approve" ? (
                        <>
                          <Loader size="sm" color="white" /> Processing...
                        </>
                      ) : (
                        <>
                          <CheckCircle className="w-5 h-5" /> Approve Case
                        </>
                      )}
                    </button>
                    <button
                      onClick={handleReject}
                      disabled={actionLoading}
                      className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-red-600 text-white rounded-lg hover:bg-red-700 font-semibold disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                    >
                      {actionLoading && activeDecision === "reject" ? (
                        <>
                          <Loader size="sm" color="white" /> Processing...
                        </>
                      ) : (
                        <>
                          <XCircle className="w-5 h-5" /> Reject Case
                        </>
                      )}
                    </button>
                    <button
                      onClick={handleRequestMoreInfo}
                      disabled={actionLoading}
                      className="w-full flex items-center justify-center gap-2 px-4 py-3 border-2 border-indigo-600 text-indigo-600 rounded-lg hover:bg-indigo-50 font-semibold disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                    >
                      {actionLoading && activeDecision === "review" ? (
                        <>
                          <Loader size="sm" color="white" /> Processing...
                        </>
                      ) : (
                        <>
                          <AlertTriangle className="w-5 h-5" /> Request More
                          Info
                        </>
                      )}
                    </button>
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
