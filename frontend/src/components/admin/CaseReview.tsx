// src/components/admin/CaseReview.tsx
import React, { useCallback, useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  ArrowLeft,
  FileText,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Download,
} from "lucide-react";
import { applicationService } from "@/services/application.service";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Loader } from "@/components/common/Loader";

import { toast } from "react-toastify";
import type { ApplicationWithDocuments } from "@/types";
import { formatDate, formatFileSize } from "@/utils/helper";
import { Button } from "../ui/button";

export const CaseReview: React.FC = () => {
  const { caseId } = useParams<{ caseId: string }>();
  const navigate = useNavigate();
  const [application, setApplication] =
    useState<ApplicationWithDocuments | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [notes, setNotes] = useState("");
  const [decision, setDecision] = useState<"approve" | "reject" | null>(null);

  const loadApplication = useCallback(async () => {
    if (!caseId) return;

    try {
      setLoading(true);
      const data = await applicationService.getById(caseId);
      setApplication(data);
      setNotes(data.notes || "");
    } catch (error: any) {
      console.error("Failed to load application:", error);
      toast.error("Failed to load application details");
    } finally {
      setLoading(false);
    }
  }, [caseId]);

  useEffect(() => {
    if (caseId) {
      loadApplication();
    }
  }, [caseId, loadApplication]);

  const handleApprove = async () => {
    if (!caseId) return;

    setActionLoading(true);
    setDecision("approve");
    try {
      await applicationService.update(caseId, {
        status: "approved",
        notes: notes.trim(),
      });
      toast.success("Application approved successfully!");
      navigate("/admin/cases");
    } catch {
      toast.error("Failed to approve application");
    } finally {
      setActionLoading(false);
      setDecision(null);
    }
  };

  const handleReject = async () => {
    if (!caseId) return;

    if (!notes.trim()) {
      toast.error("Please provide a reason for rejection");
      return;
    }

    setActionLoading(true);
    setDecision("reject");
    try {
      await applicationService.update(caseId, {
        status: "rejected",
        notes: notes.trim(),
      });
      toast.success("Application rejected");
      navigate("/admin/cases");
    } catch {
      toast.error("Failed to reject application");
    } finally {
      setActionLoading(false);
      setDecision(null);
    }
  };

  const handleRequestMoreInfo = async () => {
    if (!caseId) return;

    setActionLoading(true);
    try {
      await applicationService.update(caseId, {
        status: "under_review",
        notes: notes.trim(),
      });
      toast.info("Applicant has been notified to provide more information");
      navigate("/admin/cases");
    } catch {
      toast.error("Failed to request more information");
    } finally {
      setActionLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex justify-center items-center">
        <Loader size="xl" />
      </div>
    );
  }

  if (!application) {
    return (
      <div className="min-h-screen bg-gray-50">
        <div className="max-w-4xl mx-auto p-6">
          <div className="bg-red-50 border-l-4 border-red-500 p-6 rounded-lg">
            <div className="flex items-center gap-3">
              <XCircle className="w-6 h-6 text-red-600" />
              <div>
                <h3 className="font-semibold text-red-900">
                  Application Not Found
                </h3>
                <p className="text-red-700 mt-1">
                  The application you&apos;re looking for doesn&apos;t exist or you don&apos;t
                  have permission to view it.
                </p>
              </div>
            </div>
            <button
              onClick={() => navigate("/admin/cases")}
              className="mt-4 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700"
            >
              Back to Cases
            </button>
          </div>
        </div>
      </div>
    );
  }

  const getScoreColor = (score: number): string => {
    if (score >= 85) return "text-green-600";
    if (score >= 70) return "text-amber-700";
    return "text-red-600";
  };

  const getScoreBg = (score: number): string => {
    if (score >= 85) return "bg-green-500";
    if (score >= 70) return "bg-amber-600";
    return "bg-red-500";
  };
  const applicantProfile =
    application.applicant && typeof application.applicant === "object"
      ? application.applicant
      : null;
  const applicationLabel =
    application.position_applied ||
    application.application_type?.replace("_", " ") ||
    "Vetting Case";
  const resolveDocumentName = (doc: (typeof application.documents)[number]) =>
    doc.original_filename || doc.file_name || doc.document_type_display || "Document";
  const resolveDocumentStatus = (doc: (typeof application.documents)[number]) =>
    doc.status || doc.verification_status;
  const resolveDocumentConfidence = (doc: (typeof application.documents)[number]) =>
    doc.ai_confidence_score ?? doc.verification_result?.authenticity_confidence ?? doc.verification_result?.ocr_confidence;
  const resolveDocumentUploadedAt = (doc: (typeof application.documents)[number]) =>
    doc.uploaded_at || doc.upload_date || doc.updated_at;
  const rubricScore =
    application.rubric_evaluation?.overall_score ??
    application.rubric_evaluation?.total_weighted_score;
  const rubricPassed =
    application.rubric_evaluation?.passed ??
    application.rubric_evaluation?.passes_threshold;
  const rubricRecommendation =
    application.rubric_evaluation?.ai_recommendation ||
    application.rubric_evaluation?.decision_recommendation?.recommendation_status ||
    application.rubric_evaluation?.final_decision ||
    "NO_RECOMMENDATION";

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="mx-auto max-w-7xl space-y-6 px-4 py-6 sm:px-6">
        {/* Header */}
        <div className="flex flex-wrap items-center gap-3 sm:gap-4">
          <Button
            onClick={() => navigate("/admin/cases")}
            variant="ghost"
            className="rounded-lg p-2 text-slate-800 transition-colors hover:bg-slate-100"
          >
            <ArrowLeft className="h-6 w-6 text-slate-800" />
          </Button>
          <div className="flex-1">
            <h1 className="text-2xl font-bold text-gray-900 sm:text-3xl">
              Case Review: {application.case_id}
            </h1>
            <p className="mt-1 text-slate-800">
              Submitted: {formatDate(application.created_at)}
            </p>
          </div>
          <StatusBadge status={application.status} />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Main Content */}
          <div className="lg:col-span-2 space-y-6">
            {/* Applicant Information */}
            <div className="bg-white rounded-lg shadow-sm p-6">
              <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
                <FileText className="w-5 h-5 text-indigo-600" />
                Applicant Information
              </h2>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div>
                  <p className="text-sm text-slate-800">Full Name</p>
                  <p className="font-semibold text-gray-900">
                    {applicantProfile?.full_name || application.applicant_email || "N/A"}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-slate-800">Email</p>
                  <p className="font-semibold text-gray-900">
                    {applicantProfile?.email || application.applicant_email || "N/A"}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-slate-800">Phone</p>
                  <p className="font-semibold text-gray-900">
                    {applicantProfile?.phone_number || "N/A"}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-slate-800">Date of Birth</p>
                  <p className="font-semibold text-gray-900">
                    {applicantProfile?.date_of_birth
                      ? formatDate(applicantProfile.date_of_birth)
                      : "N/A"}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-slate-800">Application Type</p>
                  <p className="font-semibold text-gray-900 capitalize">
                    {applicationLabel}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-slate-800">Priority</p>
                  <p className="font-semibold text-gray-900 capitalize">
                    {application.priority}
                  </p>
                </div>
              </div>
            </div>

            {/* Documents */}
            <div className="bg-white rounded-lg shadow-sm p-6">
              <h2 className="text-xl font-semibold mb-4 flex items-center justify-between">
                <span className="flex items-center gap-2">
                  <FileText className="w-5 h-5 text-indigo-600" />
                  Documents ({application.documents?.length || 0})
                </span>
                {application.documents && application.documents.length > 0 && (
                  <button className="text-sm text-indigo-600 hover:text-indigo-700 font-medium flex items-center gap-1">
                    <Download className="w-4 h-4" />
                    Download All
                  </button>
                )}
              </h2>

              {application.documents && application.documents.length > 0 ? (
                <div className="space-y-3">
                  {application.documents.map((doc) => (
                    <div
                      key={doc.id}
                      className="flex flex-col gap-3 rounded-lg border border-slate-200 p-4 transition-colors hover:border-indigo-300 sm:flex-row sm:items-center sm:justify-between"
                    >
                      <div className="flex items-center gap-3">
                        <FileText className="w-8 h-8 text-slate-800" />
                        <div>
                          <p className="font-semibold text-gray-900 capitalize">
                            {(doc.document_type_display || doc.document_type).replace("_", " ")}
                          </p>
                          <p className="text-sm text-slate-800">
                            {resolveDocumentName(doc)} • {formatFileSize(doc.file_size)}
                          </p>
                          <p className="mt-1 text-xs text-slate-800">
                            Uploaded: {resolveDocumentUploadedAt(doc) ? formatDate(resolveDocumentUploadedAt(doc) || "") : "N/A"}
                          </p>
                        </div>
                      </div>
                      <div className="text-left sm:text-right">
                        <StatusBadge status={resolveDocumentStatus(doc)} />
                        {typeof resolveDocumentConfidence(doc) === "number" && (
                          <p className="mt-2 text-sm text-slate-800">
                            Confidence:{" "}
                            <span className="font-semibold">
                              {resolveDocumentConfidence(doc)?.toFixed(1)}%
                            </span>
                          </p>
                        )}
                        <button className="mt-2 text-sm text-indigo-600 hover:text-indigo-700 font-medium">
                          View Details
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="py-8 text-center text-slate-800">
                  <FileText className="w-12 h-12 text-slate-800 mx-auto mb-3" />
                  <p>No documents uploaded</p>
                </div>
              )}
            </div>

            {/* AI Analysis */}
            {(application.consistency_score !== undefined ||
              application.fraud_risk_score !== undefined ||
              application.rubric_evaluation) && (
              <div className="bg-white rounded-lg shadow-sm p-6">
                <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
                  <AlertTriangle className="w-5 h-5 text-indigo-600" />
                  AI Analysis Results
                </h2>

                <div className="space-y-6">
                  {application.consistency_score !== undefined && (
                    <div>
                      <div className="flex justify-between items-center mb-2">
                        <span className="text-sm font-medium text-slate-800">
                          Consistency Score
                        </span>
                        <span
                          className={`text-lg font-bold ${getScoreColor(
                            application.consistency_score
                          )}`}
                        >
                          {application.consistency_score.toFixed(1)}%
                        </span>
                      </div>
                      <div className="h-3 w-full rounded-full bg-slate-200">
                        <div
                          className={`h-3 rounded-full transition-all ${getScoreBg(
                            application.consistency_score
                          )}`}
                          style={{ width: `${application.consistency_score}%` }}
                        />
                      </div>
                      <p className="mt-1 text-xs text-slate-800">
                        Measures consistency across all submitted documents
                      </p>
                    </div>
                  )}

                  {application.fraud_risk_score !== undefined && (
                    <div>
                      <div className="flex justify-between items-center mb-2">
                        <span className="text-sm font-medium text-slate-800">
                          Fraud Risk Score
                        </span>
                        <span
                          className={`text-lg font-bold ${getScoreColor(
                            100 - application.fraud_risk_score
                          )}`}
                        >
                          {application.fraud_risk_score.toFixed(1)}%
                        </span>
                      </div>
                      <div className="h-3 w-full rounded-full bg-slate-200">
                        <div
                          className="bg-red-500 h-3 rounded-full transition-all"
                          style={{ width: `${application.fraud_risk_score}%` }}
                        />
                      </div>
                      <p className="mt-1 text-xs text-slate-800">
                        Probability of fraudulent information (lower is better)
                      </p>
                    </div>
                  )}

                  {application.rubric_evaluation && (
                    <div className="mt-4 p-4 bg-indigo-50 rounded-lg">
                      <div className="flex justify-between items-center">
                        <div>
                          <p className="text-sm font-medium text-slate-800">
                            Rubric Evaluation
                          </p>
                        </div>
                        <div className="text-right">
                          <p className="text-3xl font-bold text-indigo-600">
                            {typeof rubricScore === "number" ? rubricScore.toFixed(1) : "N/A"}
                            %
                          </p>
                          <p
                            className={`text-sm font-semibold ${
                              rubricPassed
                                ? "text-green-600"
                                : "text-red-600"
                            }`}
                          >
                            {rubricPassed
                              ? "PASSED"
                              : "FAILED"}
                          </p>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Admin Notes */}
            <div className="bg-white rounded-lg shadow-sm p-6">
              <h2 className="text-xl font-semibold mb-4">
                Admin Notes & Decision
              </h2>
              <textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                className="h-32 w-full resize-none rounded-lg border border-slate-700 p-3 text-slate-900 focus:border-transparent focus:outline-none focus:ring-2 focus:ring-indigo-500"
                placeholder="Add your review notes, reasons for decision, or additional comments..."
              />
              <p className="mt-2 text-xs text-slate-800">
                {notes.length === 0 && decision === "reject"
                  ? "Note: Rejection reason is required"
                  : `${notes.length} characters`}
              </p>
            </div>
          </div>

          {/* Sidebar */}
          <div className="space-y-6">
            {/* Decision Actions */}
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
                  {actionLoading && decision === "approve" ? (
                    <>
                      <Loader size="sm" color="white" />
                      Processing...
                    </>
                  ) : (
                    <>
                      <CheckCircle className="w-5 h-5" />
                      Approve Application
                    </>
                  )}
                </button>

                <button
                  onClick={handleReject}
                  disabled={actionLoading}
                  className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-red-600 text-white rounded-lg hover:bg-red-700 font-semibold disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  {actionLoading && decision === "reject" ? (
                    <>
                      <Loader size="sm" color="white" />
                      Processing...
                    </>
                  ) : (
                    <>
                      <XCircle className="w-5 h-5" />
                      Reject Application
                    </>
                  )}
                </button>
                <button
                  onClick={handleRequestMoreInfo}
                  disabled={actionLoading}
                  className="w-full flex items-center justify-center gap-2 px-4 py-3 border-2 border-indigo-600 text-indigo-600 rounded-lg hover:bg-indigo-50 font-semibold disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  <AlertTriangle className="w-5 h-5" />
                  Request More Info
                </button>
              </div>
            </div>

            {/* Case Summary */}
            <div className="bg-white rounded-lg shadow-sm p-6">
              <h3 className="font-semibold mb-4 text-gray-900">Case Summary</h3>
              <div className="space-y-3 text-sm">
                <div className="flex items-start justify-between gap-3">
                  <span className="text-slate-800">Case ID:</span>
                  <span className="font-medium text-gray-900 text-right break-all">
                    {application.case_id}
                  </span>
                </div>
                <div className="flex items-start justify-between gap-3">
                  <span className="text-slate-800">Status:</span>
                  <StatusBadge status={application.status} />
                </div>
                <div className="flex items-start justify-between gap-3">
                  <span className="text-slate-800">Priority:</span>
                  <span className="font-medium text-gray-900 capitalize text-right">
                    {application.priority}
                  </span>
                </div>
                <div className="flex items-start justify-between gap-3">
                  <span className="text-slate-800">Documents:</span>
                  <span className="font-medium text-gray-900 text-right">
                    {application.documents?.length || 0}
                  </span>
                </div>
                <div className="flex items-start justify-between gap-3">
                  <span className="text-slate-800">Created:</span>
                  <span className="font-medium text-gray-900 text-right">
                    {formatDate(application.created_at)}
                  </span>
                </div>
                <div className="flex items-start justify-between gap-3">
                  <span className="text-slate-800">Updated:</span>
                  <span className="font-medium text-gray-900 text-right">
                    {formatDate(application.updated_at)}
                  </span>
                </div>
              </div>
            </div>

            {/* AI Recommendation */}
            {application.rubric_evaluation && (
              <div
                className={`rounded-lg shadow-sm p-6 ${
                  rubricPassed
                    ? "bg-green-50 border-2 border-green-200"
                    : "bg-red-50 border-2 border-red-200"
                }`}
              >
                <h3 className="font-semibold mb-2 text-gray-900">
                  AI Recommendation
                </h3>
                <p
                  className={`text-2xl font-bold ${
                    rubricPassed
                      ? "text-green-600"
                      : "text-red-600"
                  }`}
                >
                  {rubricRecommendation}
                </p>
                <p className="mt-2 text-sm text-slate-800">
                  Based on rubric evaluation and AI analysis
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
