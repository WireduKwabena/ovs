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
    if (score >= 70) return "text-yellow-600";
    return "text-red-600";
  };

  const getScoreBg = (score: number): string => {
    if (score >= 85) return "bg-green-500";
    if (score >= 70) return "bg-yellow-500";
    return "bg-red-500";
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto p-6 space-y-6">
        {/* Header */}
        <div className="flex items-center gap-4">
          <Button
            onClick={() => navigate("/admin/cases")}
            className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <ArrowLeft className="w-6 h-6 text-gray-700" />
          </Button>
          <div className="flex-1">
            <h1 className="text-3xl font-bold text-gray-900">
              Case Review: {application.case_id}
            </h1>
            <p className="text-gray-600 mt-1">
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
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-sm text-gray-600">Full Name</p>
                  <p className="font-semibold text-gray-900">
                    {application.applicant?.full_name || "N/A"}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-gray-600">Email</p>
                  <p className="font-semibold text-gray-900">
                    {application.applicant?.email || "N/A"}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-gray-600">Phone</p>
                  <p className="font-semibold text-gray-900">
                    {application.applicant?.phone_number || "N/A"}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-gray-600">Date of Birth</p>
                  <p className="font-semibold text-gray-900">
                    {application.applicant?.date_of_birth
                      ? formatDate(application.applicant.date_of_birth)
                      : "N/A"}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-gray-600">Application Type</p>
                  <p className="font-semibold text-gray-900 capitalize">
                    {application.application_type.replace("_", " ")}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-gray-600">Priority</p>
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
                      className="flex items-center justify-between p-4 border border-gray-200 rounded-lg hover:border-indigo-300 transition-colors"
                    >
                      <div className="flex items-center gap-3">
                        <FileText className="w-8 h-8 text-gray-400" />
                        <div>
                          <p className="font-semibold text-gray-900 capitalize">
                            {doc.document_type.replace("_", " ")}
                          </p>
                          <p className="text-sm text-gray-600">
                            {doc.file_name} • {formatFileSize(doc.file_size)}
                          </p>
                          <p className="text-xs text-gray-500 mt-1">
                            Uploaded: {formatDate(doc.upload_date)}
                          </p>
                        </div>
                      </div>
                      <div className="text-right">
                        <StatusBadge status={doc.verification_status} />
                        {doc.ai_confidence_score && (
                          <p className="text-sm text-gray-600 mt-2">
                            Confidence:{" "}
                            <span className="font-semibold">
                              {doc.ai_confidence_score.toFixed(1)}%
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
                <div className="text-center py-8 text-gray-500">
                  <FileText className="w-12 h-12 text-gray-300 mx-auto mb-3" />
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
                        <span className="text-sm font-medium text-gray-700">
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
                      <div className="w-full bg-gray-200 rounded-full h-3">
                        <div
                          className={`h-3 rounded-full transition-all ${getScoreBg(
                            application.consistency_score
                          )}`}
                          style={{ width: `${application.consistency_score}%` }}
                        />
                      </div>
                      <p className="text-xs text-gray-600 mt-1">
                        Measures consistency across all submitted documents
                      </p>
                    </div>
                  )}

                  {application.fraud_risk_score !== undefined && (
                    <div>
                      <div className="flex justify-between items-center mb-2">
                        <span className="text-sm font-medium text-gray-700">
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
                      <div className="w-full bg-gray-200 rounded-full h-3">
                        <div
                          className="bg-red-500 h-3 rounded-full transition-all"
                          style={{ width: `${application.fraud_risk_score}%` }}
                        />
                      </div>
                      <p className="text-xs text-gray-600 mt-1">
                        Probability of fraudulent information (lower is better)
                      </p>
                    </div>
                  )}

                  {application.rubric_evaluation && (
                    <div className="mt-4 p-4 bg-indigo-50 rounded-lg">
                      <div className="flex justify-between items-center">
                        <div>
                          <p className="text-sm font-medium text-gray-700">
                            Rubric Evaluation
                          </p>
                        </div>
                        <div className="text-right">
                          <p className="text-3xl font-bold text-indigo-600">
                            {application.rubric_evaluation.overall_score.toFixed(
                              1
                            )}
                            %
                          </p>
                          <p
                            className={`text-sm font-semibold ${
                              application.rubric_evaluation.passed
                                ? "text-green-600"
                                : "text-red-600"
                            }`}
                          >
                            {application.rubric_evaluation.passed
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
                className="w-full h-32 p-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent resize-none"
                placeholder="Add your review notes, reasons for decision, or additional comments..."
              />
              <p className="text-xs text-gray-500 mt-2">
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
                <div className="flex justify-between">
                  <span className="text-gray-600">Case ID:</span>
                  <span className="font-medium text-gray-900">
                    {application.case_id}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">Status:</span>
                  <StatusBadge status={application.status} />
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">Priority:</span>
                  <span className="font-medium text-gray-900 capitalize">
                    {application.priority}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">Documents:</span>
                  <span className="font-medium text-gray-900">
                    {application.documents?.length || 0}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">Created:</span>
                  <span className="font-medium text-gray-900">
                    {formatDate(application.created_at)}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">Updated:</span>
                  <span className="font-medium text-gray-900">
                    {formatDate(application.updated_at)}
                  </span>
                </div>
              </div>
            </div>

            {/* AI Recommendation */}
            {application.rubric_evaluation && (
              <div
                className={`rounded-lg shadow-sm p-6 ${
                  application.rubric_evaluation.passed
                    ? "bg-green-50 border-2 border-green-200"
                    : "bg-red-50 border-2 border-red-200"
                }`}
              >
                <h3 className="font-semibold mb-2 text-gray-900">
                  AI Recommendation
                </h3>
                <p
                  className={`text-2xl font-bold ${
                    application.rubric_evaluation.passed
                      ? "text-green-600"
                      : "text-red-600"
                  }`}
                >
                  {application.rubric_evaluation.ai_recommendation}
                </p>
                <p className="text-sm text-gray-600 mt-2">
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
