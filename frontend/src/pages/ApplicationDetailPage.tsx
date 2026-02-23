// src/pages/ApplicationDetailPage.tsx
import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Upload, FileText, CheckCircle, XCircle, Clock } from 'lucide-react';
import Modal from '@/components/common/Modal';
import { DOCUMENT_TYPES } from '@/utils/constants';
import { useApplications } from '@/hooks/useApplications';
import { Navbar } from '@/components/common/Navbar';
import { StatusBadge } from '@/components/common/StatusBadge';
import { Loader } from '@/components/common/Loader';

import { applicationService } from '@/services/application.service';
import { toast } from 'react-toastify';
import { formatDate, formatFileSize } from '@/utils/helper';

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
  const [pickedDocType, setPickedDocType] = useState<string>('other');

  const handleFileUpload = async (file: File, documentType: string) => {
    if (!caseId) return;

    setUploading(true);
    try {
      await applicationService.uploadDocument(caseId, file, documentType);
      toast.success('Document uploaded successfully!');
      loadApplication(caseId);
    } catch {
      toast.error('Failed to upload document');
    } finally {
      setUploading(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50">
        <Navbar />
        <div className="flex justify-center items-center py-20">
          <Loader size="lg" />
        </div>
      </div>
    );
  }

  if (!currentCase) {
    return (
      <div className="min-h-screen bg-gray-50">
        <Navbar />
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="bg-white rounded-lg shadow-sm p-12 text-center">
            <div className="text-6xl mb-4">❌</div>
            <h3 className="text-xl font-semibold text-gray-900 mb-2">Application not found</h3>
            <button
              onClick={() => navigate('/applications')}
              className="mt-4 px-6 py-3 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700"
            >
              Back to Applications
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />
      
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <button
          onClick={() => navigate('/applications')}
          className="flex items-center gap-2 text-gray-600 hover:text-gray-900 mb-6"
        >
          <ArrowLeft className="w-5 h-5" />
          Back to Applications
        </button>

        <div className="flex justify-between items-start mb-8">
          <div>
            <h1 className="text-3xl font-bold text-gray-900 mb-2">{currentCase.case_id}</h1>
            <p className="text-gray-600">{currentCase.application_type}</p>
          </div>
          <StatusBadge status={currentCase.status} />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Main Content */}
          <div className="lg:col-span-2 space-y-6">
            {/* Application Details */}
            <div className="bg-white rounded-lg shadow-sm p-6">
              <h2 className="text-xl font-semibold mb-4">Application Details</h2>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <span className="text-gray-500 text-sm">Priority</span>
                  <p className="font-medium capitalize">{currentCase.priority}</p>
                </div>
                <div>
                  <span className="text-gray-500 text-sm">Submitted</span>
                  <p className="font-medium">{formatDate(currentCase.created_at)}</p>
                </div>
                <div>
                  <span className="text-gray-500 text-sm">Last Updated</span>
                  <p className="font-medium">{formatDate(currentCase.updated_at)}</p>
                </div>
                <div>
                  <span className="text-gray-500 text-sm">Documents</span>
                  <p className="font-medium">{currentCase.documents?.length || 0} uploaded</p>
                </div>
              </div>
              {currentCase.notes && (
                <div className="mt-4 pt-4 border-t">
                  <span className="text-gray-500 text-sm">Notes</span>
                  <p className="mt-1">{currentCase.notes}</p>
                </div>
              )}
            </div>

            {/* Documents */}
            <div className="bg-white rounded-lg shadow-sm p-6">
              <div className="flex justify-between items-center mb-4">
                <h2 className="text-xl font-semibold">Documents</h2>
                <button
                        onClick={() => { setShowUploadModal(true); setPickedFile(null); setPickedDocType('other'); }}
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
                      confirmLabel={uploading ? 'Uploading...' : 'Upload'}
                      onCancel={() => setShowUploadModal(false)}
                      onConfirm={async () => {
                        if (!pickedFile) {
                          toast.error('Please select a file to upload');
                          return;
                        }
                        if (!caseId) {
                          toast.error('Invalid case ID');
                          return;
                        }
                        await handleFileUpload(pickedFile, pickedDocType);
                        setShowUploadModal(false);
                      }}
                    >
                      <div className="space-y-4">
                        <div>
                          <label htmlFor="detail-upload-file" className="block text-sm text-gray-700 mb-1">Select file</label>
                          <input
                            id="detail-upload-file"
                            type="file"
                            accept="application/pdf,image/*"
                            onChange={(e) => setPickedFile(e.target.files && e.target.files[0] ? e.target.files[0] : null)}
                            className="w-full"
                          />
                          {pickedFile && <p className="text-xs text-gray-500 mt-1">Selected: {pickedFile.name}</p>}
                        </div>
                        <div>
                          <label htmlFor="detail-upload-type" className="block text-sm text-gray-700 mb-1">Document type</label>
                          <select
                            id="detail-upload-type"
                            aria-label="Document type"
                            value={pickedDocType}
                            onChange={(e) => setPickedDocType(e.target.value)}
                            className="w-full px-3 py-2 border rounded"
                          >
                            {DOCUMENT_TYPES.map((t) => (
                              <option key={t.value} value={t.value}>{t.label}</option>
                            ))}
                          </select>
                        </div>
                      </div>
                    </Modal>

                {currentCase.documents && currentCase.documents.length > 0 ? (
                <div className="space-y-3">
                  {currentCase.documents.map((doc) => (
                    <div key={doc.id} className="flex items-center justify-between p-4 border border-gray-200 rounded-lg">
                      <div className="flex items-center gap-3">
                        <FileText className="w-8 h-8 text-gray-400" />
                        <div>
                          <p className="font-medium">{doc.file_name}</p>
                          <p className="text-sm text-gray-500">
                            {doc.document_type} • {formatFileSize(doc.file_size)}
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center gap-3">
                        <StatusBadge status={doc.verification_status} />
                        {doc.ai_confidence_score && (
                          <span className="text-sm text-gray-600">
                            {doc.ai_confidence_score.toFixed(1)}% confidence
                          </span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-8">
                  <FileText className="w-12 h-12 text-gray-300 mx-auto mb-3" />
                  <p className="text-gray-500">No documents uploaded yet</p>
                </div>
              )}
            </div>

            {/* Verification Results */}
            {currentCase.documents && currentCase.documents.length > 0 && (
              <div className="bg-white rounded-lg shadow-sm p-6">
                <h2 className="text-xl font-semibold mb-4">Verification Status</h2>

                {currentCase.documents.map((doc) => (
                  <div key={doc.id} className="mb-4 p-4 bg-gray-50 rounded-lg">
                    <div className="flex justify-between items-start mb-2">
                      <span className="font-medium">{doc.document_type}</span>
                      <StatusBadge status={doc.verification_status} />
                    </div>
                    {typeof doc.ai_confidence_score === 'number' && (
                      <div className="text-sm text-gray-600">
                        AI Confidence: {doc.ai_confidence_score.toFixed(1)}%
                      </div>
                    )}
                  </div>
                ))}

                {(currentCase.consistency_result || currentCase.fraud_result) && (
                  <div className="mt-6 pt-4 border-t">
                    <h3 className="font-semibold mb-3">Overall Scores</h3>
                    <div className="grid grid-cols-2 gap-4">
                      {currentCase.consistency_result && (
                        <div>
                          <span className="text-sm text-gray-500">Consistency</span>
                          <p className="text-2xl font-bold text-indigo-600">
                            {currentCase.consistency_result.overall_score.toFixed(1)}%
                          </p>
                        </div>
                      )}
                      {currentCase.fraud_result && (
                        <div>
                          <span className="text-sm text-gray-500">Fraud Risk</span>
                          <p className="text-2xl font-bold text-red-600">
                            {currentCase.fraud_result.fraud_probability.toFixed(1)}%
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
              <h3 className="font-semibold mb-4">Status Timeline</h3>
              <div className="space-y-4">
                <div className="flex gap-3">
                  <div className="flex flex-col items-center">
                    <CheckCircle className="w-5 h-5 text-green-500" />
                    <div className="w-px h-full bg-gray-300 mt-2"></div>
                  </div>
                  <div>
                    <p className="font-medium">Submitted</p>
                    <p className="text-sm text-gray-500">{formatDate(currentCase.created_at)}</p>
                  </div>
                </div>

                {currentCase.status !== 'pending' && (
                  <div className="flex gap-3">
                    <div className="flex flex-col items-center">
                      <Clock className="w-5 h-5 text-blue-500" />
                      {currentCase.status !== 'under_review' && (
                        <div className="w-px h-full bg-gray-300 mt-2"></div>
                      )}
                    </div>
                    <div>
                      <p className="font-medium">Under Review</p>
                      <p className="text-sm text-gray-500">{formatDate(currentCase.updated_at)}</p>
                    </div>
                  </div>
                )}

                {(currentCase.status === 'approved' || currentCase.status === 'rejected') && (
                  <div className="flex gap-3">
                    <div className="flex flex-col items-center">
                      {currentCase.status === 'approved' ? (
                        <CheckCircle className="w-5 h-5 text-green-500" />
                      ) : (
                        <XCircle className="w-5 h-5 text-red-500" />
                      )}
                    </div>
                    <div>
                      <p className="font-medium capitalize">{currentCase.status}</p>
                      <p className="text-sm text-gray-500">{formatDate(currentCase.updated_at)}</p>
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Quick Actions */}
            <div className="bg-white rounded-lg shadow-sm p-6">
              <h3 className="font-semibold mb-4">Quick Actions</h3>
              <div className="space-y-2">
                <button className="w-full px-4 py-2 text-left text-sm hover:bg-gray-50 rounded-lg transition-colors">
                  Download All Documents
                </button>
                <button className="w-full px-4 py-2 text-left text-sm hover:bg-gray-50 rounded-lg transition-colors">
                  Request Status Update
                </button>
                <button className="w-full px-4 py-2 text-left text-sm text-red-600 hover:bg-red-50 rounded-lg transition-colors">
                  Cancel Application
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
