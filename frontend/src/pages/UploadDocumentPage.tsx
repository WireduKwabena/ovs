// src/pages/UploadDocumentPage.tsx
import React, { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import { Navbar } from '@/components/common/Navbar';
import { FileUpload } from '@/components/common/FileUpload';
import Modal from '@/components/common/Modal';
import { toast } from 'react-toastify';

export const UploadDocumentPage: React.FC = () => {
  const navigate = useNavigate();
  const { caseId } = useParams<{ caseId: string }>();
  const [selectedFiles, setSelectedFiles] = useState<{ id: string; name: string; status: string }[]>([]);
  const [confirmState, setConfirmState] = useState<{
    open: boolean;
    file?: any;
    resolve?: (ok: boolean) => void;
  }>({ open: false });
  

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />
      
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <button
          onClick={() => navigate(`/applications/${caseId}`)}
          className="flex items-center gap-2 text-gray-600 hover:text-gray-900 mb-6"
        >
          <ArrowLeft className="w-5 h-5" />
          Back to Application
        </button>

        <div className="bg-white rounded-lg shadow-sm p-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">Upload Documents</h1>
          <p className="text-gray-600 mb-8">Add additional documents to your application</p>

          <div className="space-y-6">
            {/* File Upload */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Files (PDF, JPG, PNG - Max 10MB each)
              </label>
              {caseId ? (
                <>
                  <FileUpload
                    caseId={caseId}
                    onFilesChanged={(files) =>
                      setSelectedFiles(files.map((f) => ({ id: f.id, name: f.file.name, status: f.status })))
                    }
                    onRemoveRequest={(file) =>
                      new Promise<boolean>((resolve) => {
                        setConfirmState({ open: true, file, resolve });
                      })
                    }
                    onUploadComplete={() => {
                      toast.success('Documents uploaded successfully!');
                      navigate(`/applications/${caseId}`);
                    }}
                  />

                  {/* Brief selected files list */}
                  {selectedFiles.length > 0 && (
                    <div className="mt-4 bg-gray-50 p-3 rounded">
                      <h4 className="text-sm font-medium mb-2">Selected files</h4>
                      <ul className="text-sm text-gray-700 space-y-1">
                        {selectedFiles.map((f) => (
                          <li key={f.id} className="flex justify-between">
                            <span className="truncate">{f.name}</span>
                            <span className="ml-4 text-xs text-gray-500">{f.status}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </>
              ) : (
                <p className="text-red-600">Invalid application ID</p>
              )}
            </div>

            {/* Actions */}
            <div className="flex gap-4 pt-6">
              <button
                type="button"
                onClick={() => navigate(`/applications/${caseId}`)}
                className="w-full px-6 py-3 border-2 border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 font-medium"
              >
                Back to Application
              </button>
            </div>
          </div>
        </div>
      </div>
      {/* Confirm Remove Modal (uses shared Modal component) */}
      <React.Suspense fallback={null}>
        <Modal
          open={confirmState.open}
          title="Remove File"
          onCancel={() => {
            try { confirmState.resolve?.(false); } catch (e) {}
            setConfirmState({ open: false });
          }}
          onConfirm={() => {
            try { confirmState.resolve?.(true); } catch (e) {}
            setConfirmState({ open: false });
          }}
          confirmLabel="Remove"
          cancelLabel="Cancel"
        >
          <p className="text-sm text-gray-700">Are you sure you want to remove <strong>{confirmState.file?.file?.name ?? confirmState.file?.name}</strong>?</p>
        </Modal>
      </React.Suspense>
    </div>
  );
};

export default UploadDocumentPage;