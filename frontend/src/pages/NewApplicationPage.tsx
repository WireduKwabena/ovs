// src/pages/NewApplicationPage.tsx
import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { yupResolver } from '@hookform/resolvers/yup';
import { ArrowLeft, X } from 'lucide-react';
// import { Navbar } from '@/components/common/Navbar';
import { FileUpload } from '@/components/common/FileUpload';
import { applicationService } from '@/services/application.service';
import { applicationSchema } from '@/utils/validators';
import { useApplications } from '@/hooks/useApplications';
import { APPLICATION_TYPES, PRIORITIES, DOCUMENT_TYPES } from '@/utils/constants';
import { toast } from 'react-toastify';
import { Navbar } from '@/components/common/Navbar';
import type { DocumentType } from '@/types';

interface ApplicationFormData {
  application_type: string;
  priority: string;
  notes?: string;
}

export const NewApplicationPage: React.FC = () => {
  const navigate = useNavigate();
  const { createApplication } = useApplications();
  const [files, setFiles] = useState<File[]>([]);
  const [documentType, setDocumentType] = useState<DocumentType>('other');
  const [submitting, setSubmitting] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<ApplicationFormData>({
    resolver: yupResolver(applicationSchema) as any,
  });

  const onSubmit = async (data: ApplicationFormData) => {
    if (files.length === 0) {
      toast.error('Please upload at least one document');
      return;
    }

    setSubmitting(true);
    try {
      const application = await createApplication(data);
      // Upload files to the created application using selected document type
      if (files.length > 0) {
        for (const file of files) {
          try {
            await applicationService.uploadDocument(application.case_id, file, documentType || 'other');
          } catch (err) {
            console.error('Upload failed for', file.name, err);
            toast.warn(`Failed to upload ${file.name}`);
          }
        }
      }

      toast.success('Application created successfully!');
      navigate(`/applications/${application.case_id}`);
    } catch {
      toast.error('Failed to create application');
    } finally {
      setSubmitting(false);
    }
  };

  const handleFilesAdded = (newFiles: File[]) => {
    setFiles((prev) => [...prev, ...newFiles]);
  };

  const removeFile = (index: number) => {
    setFiles(files.filter((_, i) => i !== index));
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />
      
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <button
          onClick={() => navigate('/applications')}
          className="flex items-center gap-2 text-gray-300 mb-6 transition-colors"
        >
          <ArrowLeft className="w-5 h-5" />
          Back to Applications
        </button>

        <div className="bg-white rounded-lg shadow-sm p-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">New Application</h1>
          <p className="text-gray-600 mb-8">Fill in the details and upload required documents</p>

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
            {/* Application Type */}
            <div>
              <label htmlFor="new-app-type" className="block text-sm font-medium text-gray-700 mb-2">
                Application Type *
              </label>
              <select
                id="new-app-type"
                {...register('application_type')}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg text-black focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
              >
                <option value="">Select type...</option>
                {APPLICATION_TYPES.map((type) => (
                  <option key={type.value} value={type.value}>
                    {type.label}
                  </option>
                ))}
              </select>
              {errors.application_type && (
                <p className="mt-1 text-sm text-red-600">{errors.application_type.message}</p>
              )}
            </div>

            {/* Priority */}
            <div>
              <label htmlFor="new-app-priority" className="block text-sm font-medium text-gray-700 mb-2">
                Priority *
              </label>
              <select
                id="new-app-priority"
                {...register('priority')}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg text-black focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
              >
                <option value="">Select priority...</option>
                {PRIORITIES.map((priority) => (
                  <option key={priority.value} value={priority.value}>
                    {priority.label}
                  </option>
                ))}
              </select>
              {errors.priority && (
                <p className="mt-1 text-sm text-red-600">{errors.priority.message}</p>
              )}
            </div>

            {/* Notes */}
            <div>
              <label htmlFor="new-app-notes" className="block text-sm font-medium text-gray-700 mb-2">
                Additional Notes
              </label>
              <textarea
                id="new-app-notes"
                {...register('notes')}
                rows={4}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg text-black focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent resize-none"
                placeholder="Any additional information you'd like to provide..."
              />
            </div>

            {/* File Upload */}
            <div>
              <label htmlFor="upload-doc-type" className="block text-sm font-medium text-gray-700 mb-2">
                Document Type for Uploads
              </label>
              <select
                id="upload-doc-type"
                aria-label="Document type for uploads"
                value={documentType}
                onChange={(e) => setDocumentType(e.target.value as DocumentType)}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg text-black focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent mb-4"
              >
                {DOCUMENT_TYPES.map((t) => (
                  <option key={t.value} value={t.value}>{t.label}</option>
                ))}
              </select>
              <p className="block text-sm font-medium text-gray-700 mb-2">
                Documents * (PDF, JPG, PNG - Max 10MB each)
              </p>
              <FileUpload
                pageDocumentType={documentType}
                onFilesChanged={(fileItems) => handleFilesAdded(fileItems.map((fi) => fi.file))}
              />
              
              {/* Uploaded Files List */}
              {files.length > 0 && (
                <div className="mt-4 space-y-2">
                  {files.map((file, index) => (
                    <div
                      key={index}
                      className="flex items-center justify-between p-3 bg-gray-50 rounded-lg border border-gray-200"
                    >
                      <div className="flex items-center gap-3">
                        <span className="text-2xl">📄</span>
                        <div>
                          <p className="font-medium text-gray-900">{file.name}</p>
                          <p className="text-sm text-gray-500">
                            {(file.size / 1024).toFixed(2)} KB
                          </p>
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={() => removeFile(index)}
                        className="p-1 text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                        title="Remove file"
                      >
                        <X className="w-5 h-5" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Submit */}
            <div className="flex gap-4 pt-6">
              <button
                type="button"
                onClick={() => navigate('/applications')}
                className="flex-1 px-6 py-3 border-2 border-gray-300 text-gray-300 rounded-lg hover:bg-gray-50 font-medium transition-colors"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={submitting}
                className="flex-1 px-6 py-3 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed font-medium transition-colors"
              >
                {submitting ? 'Creating...' : 'Create Application'}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
};
