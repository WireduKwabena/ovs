// src/pages/ApplicationDetailPage.tsx
import React, { useEffect, useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import {
  ArrowLeft,
  Upload,
  FileText,
  CheckCircle,
  XCircle,
  Clock,
} from "lucide-react";
import Modal from "@/components/common/Modal";
import { DOCUMENT_TYPES } from "@/utils/constants";
import { useApplications } from "@/hooks/useApplications";
import { FieldLabel, HelpTooltip } from "@/components/common/FieldHelp";

import { StatusBadge } from "@/components/common/StatusBadge";
import { Loader } from "@/components/common/Loader";

import { applicationService } from "@/services/application.service";
import { toast } from "react-toastify";
import { formatDate, formatFileSize } from "@/utils/helper";

export const ApplicationDetailPage: React.FC = () => {
  const { caseId } = useParams<{ caseId: string }>();
  const navigate = useNavigate();
  const { currentCase, loading, loadApplication } = useApplications();

  useEffect(() => {
    if (caseId) {
      loadApplication(caseId);
    }
  }, [caseId, loadApplication]);
  const [uploading, setUploading] = useState(false);
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [pickedFile, setPickedFile] = useState<File | null>(null);
  const [pickedDocType, setPickedDocType] = useState<string>("other");

  const handleFileUpload = async (file: File, documentType: string) => {
    if (!caseId) return;

    setUploading(true);
    try {
      await applicationService.uploadDocument(caseId, file, documentType);
      toast.success("Document uploaded successfully!");
      loadApplication(caseId);
    } catch {
      toast.error("Failed to upload document");
    } finally {
      setUploading(false);
    }
  };

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
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
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
    doc.original_filename || doc.file_name || doc.document_type_display || "Document";
  const resolveDocumentStatus = (doc: (typeof currentCase.documents)[number]) =>
    doc.status || doc.verification_status;
  const resolveDocumentConfidence = (doc: (typeof currentCase.documents)[number]) =>
    doc.ai_confidence_score ?? doc.verification_result?.authenticity_confidence ?? doc.verification_result?.ocr_confidence;

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <button
          onClick={() => navigate("/applications")}
          className="mb-6 flex items-center gap-2 text-slate-700 hover:text-slate-900"
        >
          <ArrowLeft className="w-5 h-5" />
          Back to Vetting Dossiers
        </button>

        <div className="flex justify-between items-start mb-8">
          <div>
            <h1 className="text-3xl font-bold text-gray-900 mb-2">
              {currentCase.case_id}
            </h1>
            <p className="text-slate-700 capitalize">{applicationLabel}</p>
            <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
              {currentCase.office_title || currentCase.position_applied ? (
                <span className="inline-flex rounded bg-slate-100 px-2 py-1 font-semibold text-slate-700">
                  Office: {currentCase.office_title || currentCase.position_applied}
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
              <div className="flex justify-between items-center mb-4">
                <h2 className="inline-flex items-center gap-1.5 text-xl font-semibold">
                  Documents
                  <HelpTooltip text="Uploaded files, verification status, and AI confidence metrics for this dossier." />
                </h2>
                <button
                  onClick={() => {
                    setShowUploadModal(true);
                    setPickedFile(null);
                    setPickedDocType("other");
                  }}
                  disabled={uploading}
                  className="inline-flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50"
                >
                  <Upload className="w-4 h-4" />
                  Upload Document
                </button>
              </div>

              {/* Upload Modal */}
              <Modal
                open={showUploadModal}
                title="Upload Document"
                cancelLabel="Cancel"
                confirmLabel={uploading ? "Uploading..." : "Upload"}
                onCancel={() => setShowUploadModal(false)}
                onConfirm={async () => {
                  if (!pickedFile) {
                    toast.error("Please select a file to upload");
                    return;
                  }
                  if (!caseId) {
                    toast.error("Invalid case ID");
                    return;
                  }
                  await handleFileUpload(pickedFile, pickedDocType);
                  setShowUploadModal(false);
                }}
              >
                <div className="space-y-4">
                  <div>
                    <FieldLabel
                      htmlFor="detail-upload-file"
                      label="Select file"
                      help="Choose a PDF or image document to attach to this vetting dossier."
                      className="mb-1 flex items-center gap-1.5"
                      textClassName="block text-sm text-slate-700"
                    />
                    <input
                      title="Select file"
                      id="detail-upload-file"
                      type="file"
                      accept="application/pdf,image/*"
                      onChange={(e) =>
                        setPickedFile(
                          e.target.files && e.target.files[0]
                            ? e.target.files[0]
                            : null,
                        )
                      }
                      className="w-full"
                    />
                    {pickedFile && (
                      <p className="mt-1 text-xs text-slate-700">
                        Selected: {pickedFile.name}
                      </p>
                    )}
                  </div>
                  <div>
                    <FieldLabel
                      htmlFor="detail-upload-type"
                      label="Document type"
                      help="Classify the uploaded file so verification rules and scoring are applied correctly."
                      className="mb-1 flex items-center gap-1.5"
                      textClassName="block text-sm text-slate-700"
                    />
                    <select
                      id="detail-upload-type"
                      aria-label="Document type"
                      value={pickedDocType}
                      onChange={(e) => setPickedDocType(e.target.value)}
                      className="w-full px-3 py-2 border rounded"
                    >
                      {DOCUMENT_TYPES.map((t) => (
                        <option key={t.value} value={t.value}>
                          {t.label}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
              </Modal>

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
                          <p className="font-medium">{resolveDocumentName(doc)}</p>
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
                            {resolveDocumentConfidence(doc)?.toFixed(1)}% confidence
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
                      <span className="font-medium">{doc.document_type_display || doc.document_type}</span>
                      <StatusBadge status={resolveDocumentStatus(doc)} />
                    </div>
                    {typeof resolveDocumentConfidence(doc) === "number" && (
                      <div className="text-sm text-slate-700">
                        AI Confidence: {resolveDocumentConfidence(doc)?.toFixed(1)}%
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
                      {currentCase.status !== "under_review" && (
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
                <button className="w-full px-4 py-2 text-left text-sm hover:bg-slate-100 rounded-lg transition-colors">
                  Request Status Update
                </button>
                <button className="w-full px-4 py-2 text-left text-sm text-red-600 hover:bg-red-50 rounded-lg transition-colors">
                  Cancel Dossier
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

