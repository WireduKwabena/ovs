// src/components/application/DocumentUpload.tsx
import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { FileUpload } from '../common/FileUpload';
import { CheckCircle, ArrowRight } from 'lucide-react';

export function DocumentUpload() {
  const { caseId } = useParams<{ caseId: string }>();
  const navigate = useNavigate();
  const [uploadComplete, setUploadComplete] = useState(false);
  
  if (!caseId) {
    return <div className="text-center py-12">Invalid application ID</div>;
  }
  
  const handleUploadComplete = () => {
    setUploadComplete(true);
  };
  
  const handleContinue = () => {
    navigate(`/applications/${caseId}`);
  };
  
  return (
    <div className="max-w-4xl mx-auto p-6">
      <div className="bg-white rounded-lg shadow-lg p-8">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">
            Upload Documents
          </h1>
          <p className="text-gray-600">
            Application ID: <span className="font-semibold">{caseId}</span>
          </p>
        </div>
        
        {/* Instructions */}
        <div className="bg-blue-50 border-l-4 border-blue-500 p-4 mb-6">
          <h3 className="font-semibold text-blue-900 mb-2">Upload Requirements</h3>
          <ul className="list-disc list-inside text-sm text-blue-800 space-y-1">
            <li>Accepted formats: PDF, JPG, PNG</li>
            <li>Maximum file size: 10MB per file</li>
            <li>Multiple files can be uploaded</li>
            <li>Please specify the document type for each file</li>
          </ul>
        </div>
        
        {/* File Upload */}
        <FileUpload 
          caseId={caseId} 
          onUploadComplete={handleUploadComplete}
        />
        
        {/* Success */}
        {uploadComplete && (
          <div className="mt-6 p-6 bg-green-50 border-l-4 border-green-500 rounded-lg">
            <div className="flex items-start">
              <CheckCircle className="w-6 h-6 text-green-500 mr-3 shrink-0 mt-1" />
              <div className="flex-1">
                <h3 className="font-semibold text-green-900 mb-2">
                  Upload Complete!
                </h3>
                <p className="text-sm text-green-800 mb-4">
                  Your documents have been uploaded successfully. Our AI system is now processing them.
                  You&apos;ll receive notifications as the verification progresses.
                </p>
                <button
                  onClick={handleContinue}
                  className="flex items-center gap-2 px-6 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 font-semibold"
                >
                  Continue to Application
                  <ArrowRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
