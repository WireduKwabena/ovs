// src/components/FileUpload.tsx
import { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { Upload, File, X, CheckCircle, AlertCircle } from 'lucide-react';
import { Button } from '../ui/button';
import { useDispatch } from 'react-redux';
import type { AppDispatch } from '@/app/store';
import { uploadDocument } from '@/store/applicationSlice';  // Assume thunk
import { toast } from 'react-toastify';
import type { DocumentType, FileItem } from '@/types';
import { cn } from '@/utils/helper';


// interface FileItem {
//   file: File;
//   id: string;
//   status: 'pending' | 'uploading' | 'success' | 'error';
//   progress: number;
//   documentType: DocumentType;
// }

interface FileUploadProps {
  caseId?: string;
  onUploadComplete?: () => void;
  onFilesChanged?: (files: FileItem[]) => void;
  onRemoveRequest?: (file: FileItem) => boolean | Promise<boolean>;
  pageDocumentType?: string;
}

export function FileUpload({ caseId, onUploadComplete, onFilesChanged, onRemoveRequest, pageDocumentType }: FileUploadProps) {
  const dispatch = useDispatch<AppDispatch>();
  const [files, setFiles] = useState<FileItem[]>([]);

  // Helper to update state and notify parent
  const setFilesAndNotify = (updater: React.SetStateAction<FileItem[]>) => {
    setFiles((prev) => {
      const next = typeof updater === 'function' ? (updater as (p: FileItem[]) => FileItem[])(prev) : (updater as FileItem[]);
      try {
        onFilesChanged?.(next);
      } catch (e) {
        // ignore notification errors
      }
      return next;
    });
  };

  const onDrop = useCallback((acceptedFiles: File[]) => {
    const newFiles: FileItem[] = acceptedFiles.map((file) => ({
      file,
      id: Math.random().toString(36).substr(2, 9),
      status: 'pending',
      progress: 0,
      documentType: 'other' as DocumentType,
    }));

    setFilesAndNotify((prev) => [...prev, ...newFiles]);
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'image/*': ['.png', '.jpg', '.jpeg'],
    },
    maxSize: 10485760, // 10MB
    multiple: true,
  });

  const updateFileDocumentType = (fileId: string, documentType: DocumentType) => {
    setFilesAndNotify((prev) => prev.map((f) => (f.id === fileId ? { ...f, documentType } : f)));
  };

  const removeFile = async (fileId: string) => {
    const target = files.find((f) => f.id === fileId);
    if (!target) return;

    let allow = true;
    if (onRemoveRequest) {
      try {
        const result = onRemoveRequest(target);
        allow = result instanceof Promise ? await result : result;
      } catch (e) {
        allow = false;
      }
    }

    if (!allow) return;

    setFilesAndNotify((prev) => prev.filter((f) => f.id !== fileId));
  };

  const uploadFile = async (fileItem: FileItem) => {
    if (!caseId) {
      setFilesAndNotify((prev) => prev.map((f) => f.id === fileItem.id ? { ...f, status: 'error', progress: 0 } : f));
      toast.error('Missing caseId. Unable to upload file.');
      return;
    }

    try {
      setFilesAndNotify((prev) => prev.map((f) => f.id === fileItem.id ? { ...f, status: 'uploading', progress: 0 } : f));

      // Dispatch thunk (handles progress via service/axios onUploadProgress)
      const result = await dispatch(uploadDocument({ caseId, file: fileItem.file, documentType: fileItem.documentType })).unwrap();

      setFilesAndNotify((prev) => prev.map((f) => f.id === fileItem.id ? { ...f, status: 'success', progress: 100, uploadedDoc: result.document } : f));

      toast.success(`Uploaded: ${fileItem.file.name}`);
    } catch (error: any) {
      setFilesAndNotify((prev) => prev.map((f) => f.id === fileItem.id ? { ...f, status: 'error', progress: 0 } : f));
      toast.error(`Failed to upload ${fileItem.file.name}`);
    }
  };

  const uploadAll = useCallback(async () => {
    for (const fileItem of files.filter((f) => f.status === 'pending')) {
      await uploadFile(fileItem);
    }
    onUploadComplete?.();
  }, [files, uploadFile, onUploadComplete]);

  const allUploaded = files.every((f) => f.status === 'success' || f.status === 'error');

  return (
    <div className="p-6 bg-white rounded-lg shadow-md">
      {/* Dropzone */}
      <div
        {...getRootProps()}
        className={cn(
          'border-2 border-dashed rounded-lg p-8 text-center transition-colors',
          isDragActive ? 'border-blue-400 bg-blue-50' : 'border-gray-300'
        )}
      >
        <input {...getInputProps()} />
        <Upload className="mx-auto w-12 h-12 text-gray-400 mb-4" />
        <p className="text-lg font-medium text-gray-900 mb-2">
          {isDragActive ? 'Drop the files here ...' : 'Drag & drop files here, or click to select'}
        </p>
        <p className="text-sm text-gray-500 mb-4">PDF, PNG, JPG up to 10MB</p>
      </div>

      {/* Page-level document type hint */}
      {pageDocumentType && (
        <div className="mt-3 text-sm text-gray-600">Uploading as: <span className="font-medium">{pageDocumentType.replace('_', ' ')}</span></div>
      )}

      {/* File List */}
      {files.length > 0 && (
        <div className="mt-6 space-y-3">
          {files.map((fileItem) => (
            <div key={fileItem.id} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
              <div className="flex items-center gap-3 flex-1">
                <File className="w-5 h-5 text-gray-400" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-gray-900 truncate">{fileItem.file.name}</p>
                  <label> Select option:
                  <select
                    value={fileItem.documentType}
                    onChange={(e) => updateFileDocumentType(fileItem.id, e.target.value as DocumentType)}
                    className="mt-1 text-xs border rounded px-2 py-1"
                  >
                    {/* Map DOCUMENT_TYPES from constants */}
                    <option value="id_card">ID Card</option>
                    <option value="passport">Passport</option>
                    {/* ... full list */}
                  </select>
                  </label>
                </div>

                {/* Progress */}
                {fileItem.status === 'uploading' && (
                  <div className="w-16">
                    <div className="w-full bg-gray-200 rounded-full h-2">
                      <div
                        className="bg-blue-600 h-2 rounded-full transition-all"
                        style={{ width: `${fileItem.progress}%` }}
                      />
                    </div>
                    <p className="text-xs text-gray-500 mt-1">
                      {fileItem.progress}%
                    </p>
                  </div>
                )}

                {/* Status Icons */}
                {fileItem.status === 'success' && <CheckCircle className="w-5 h-5 text-green-500" />}
                {fileItem.status === 'error' && <AlertCircle className="w-5 h-5 text-red-500" />}
              </div>

              {/* Remove Button */}
              {fileItem.status !== 'uploading' && (
                <Button
                  onClick={() => removeFile(fileItem.id)}
                  className="shrink-0 p-1 hover:bg-gray-100 rounded"
                  variant="ghost"
                  size="sm"
                >
                  <X className="w-5 h-5 text-gray-400" />
                </Button>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Upload Button (only when caseId is provided) */}
      {caseId && files.length > 0 && !allUploaded && (
        <Button
          onClick={uploadAll}
          disabled={files.every((f) => f.status !== 'pending')}
          className="w-full mt-4 px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-semibold disabled:bg-gray-400 disabled:cursor-not-allowed"
        >
          Upload All Files ({files.filter((f) => f.status === 'pending').length} pending)
        </Button>
      )}

      {!caseId && files.length > 0 && (
        <div className="mt-4 p-3 text-sm text-gray-600 bg-yellow-50 rounded">
          Files are staged locally and will be uploaded after the application is created.
        </div>
      )}

      {/* Success Message */}
      {allUploaded && (
        <div className="p-4 bg-green-50 border-l-4 border-green-500 text-green-700 mt-4 rounded">
          <p className="font-semibold">✓ All files uploaded successfully!</p>
          <p className="text-sm mt-1">
            Your documents are being verified by our AI system. You'll be notified once the process is complete.
          </p>
        </div>
      )}
    </div>
  );
}