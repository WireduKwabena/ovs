// src/components/FileUpload.tsx
import { useCallback, useMemo, useState, type SetStateAction } from 'react';
import { useDropzone, type FileRejection } from 'react-dropzone';
import { Upload, File, X, CheckCircle, AlertCircle } from 'lucide-react';
import { Button } from '../ui/button';
import { useDispatch } from 'react-redux';
import type { AppDispatch } from '@/app/store';
import { uploadDocument } from '@/store/applicationSlice';  // Assume thunk
import { toast } from 'react-toastify';
import type { DocumentType, FileItem } from '@/types';
import { cn } from '@/utils/helper';
import { DOCUMENT_TYPES } from '@/utils/constants';


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
  pageDocumentType?: DocumentType;
}

export function FileUpload({ caseId, onUploadComplete, onFilesChanged, onRemoveRequest, pageDocumentType }: FileUploadProps) {
  const dispatch = useDispatch<AppDispatch>();
  const [files, setFiles] = useState<FileItem[]>([]);
  const normalizedPageDocumentType = useMemo<DocumentType | undefined>(() => {
    if (!pageDocumentType) {
      return undefined;
    }
    return DOCUMENT_TYPES.some((item) => item.value === pageDocumentType)
      ? pageDocumentType
      : undefined;
  }, [pageDocumentType]);

  const createLocalFileId = () => {
    if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
      return crypto.randomUUID();
    }
    return `file-${Date.now()}-${Math.floor(Math.random() * 1000000)}`;
  };

  // Helper to update state and notify parent
  const setFilesAndNotify = useCallback((updater: SetStateAction<FileItem[]>) => {
    setFiles((prev) => {
      const next = typeof updater === 'function'
        ? (updater as (p: FileItem[]) => FileItem[])(prev)
        : (updater as FileItem[]);
      try {
        onFilesChanged?.(next);
      } catch {
        // ignore notification errors
      }
      return next;
    });
  }, [onFilesChanged]);

  const onDrop = useCallback((acceptedFiles: File[]) => {
    setFilesAndNotify((prev) => {
      const duplicateKeys = new Set(prev.map((fileItem) => `${fileItem.file.name}-${fileItem.file.size}-${fileItem.file.lastModified}`));

      const nextNewFiles: FileItem[] = [];
      let duplicates = 0;

      acceptedFiles.forEach((file) => {
        const key = `${file.name}-${file.size}-${file.lastModified}`;
        if (duplicateKeys.has(key)) {
          duplicates += 1;
          return;
        }

        duplicateKeys.add(key);
        nextNewFiles.push({
          file,
          id: createLocalFileId(),
          status: 'pending',
          progress: 0,
          documentType: normalizedPageDocumentType || 'other',
        });
      });

      if (duplicates > 0) {
        toast.info(`${duplicates} duplicate file${duplicates > 1 ? 's were' : ' was'} skipped.`);
      }

      return [...prev, ...nextNewFiles];
    });
  }, [normalizedPageDocumentType, setFilesAndNotify]);

  const onDropRejected = useCallback((rejections: FileRejection[]) => {
    if (rejections.length === 0) {
      return;
    }

    const message = rejections
      .slice(0, 3)
      .map((entry) => {
        const firstError = entry.errors[0];
        return `${entry.file.name}: ${firstError?.message || 'Invalid file'}`;
      })
      .join(' | ');

    toast.error(message);
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    onDropRejected,
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
      } catch {
        allow = false;
      }
    }

    if (!allow) return;

    setFilesAndNotify((prev) => prev.filter((f) => f.id !== fileId));
  };

  const uploadFile = useCallback(async (fileItem: FileItem): Promise<boolean> => {
    if (!caseId) {
      setFilesAndNotify((prev) => prev.map((f) => f.id === fileItem.id ? { ...f, status: 'error', progress: 0 } : f));
      toast.error('Missing caseId. Unable to upload file.');
      return false;
    }

    try {
      setFilesAndNotify((prev) => prev.map((f) => f.id === fileItem.id ? { ...f, status: 'uploading', progress: 20 } : f));

      // Dispatch thunk (handles progress via service/axios onUploadProgress)
      const result = await dispatch(
        uploadDocument({
          caseId,
          file: fileItem.file,
          documentType: normalizedPageDocumentType || fileItem.documentType,
        })
      ).unwrap();

      setFilesAndNotify((prev) => prev.map((f) => f.id === fileItem.id ? { ...f, status: 'success', progress: 100, uploadedDoc: result.document } : f));

      toast.success(`Uploaded: ${fileItem.file.name}`);
      return true;
    } catch {
      setFilesAndNotify((prev) => prev.map((f) => f.id === fileItem.id ? { ...f, status: 'error', progress: 0 } : f));
      toast.error(`Failed to upload ${fileItem.file.name}`);
      return false;
    }
  }, [caseId, dispatch, normalizedPageDocumentType, setFilesAndNotify]);

  const uploadAll = useCallback(async () => {
    const pendingFiles = files.filter((f) => f.status === 'pending');
    if (pendingFiles.length === 0) {
      return;
    }

    let failed = 0;

    for (const fileItem of pendingFiles) {
      const successful = await uploadFile(fileItem);
      if (!successful) {
        failed += 1;
      }
    }

    if (failed === 0) {
      onUploadComplete?.();
      return;
    }

    toast.warn(`${failed} file${failed > 1 ? 's' : ''} failed to upload. Please retry.`);
  }, [files, uploadFile, onUploadComplete]);

  const allFinished = files.length > 0 && files.every((f) => f.status === 'success' || f.status === 'error');
  const allSuccessful = files.length > 0 && files.every((f) => f.status === 'success');
  const hasAnySuccess = files.some((f) => f.status === 'success');
  const hasAnyError = files.some((f) => f.status === 'error');

  return (
    <div className="p-6 bg-white rounded-lg shadow-md">
      {/* Dropzone */}
      <div
        {...getRootProps()}
        className={cn(
          'border-2 border-dashed rounded-lg p-8 text-center transition-colors',
          isDragActive ? 'border-blue-400 bg-blue-50' : 'border-slate-700'
        )}
      >
        <input {...getInputProps()} />
        <Upload className="mx-auto w-12 h-12 text-slate-700 mb-4" />
        <p className="text-lg font-medium text-gray-900 mb-2">
          {isDragActive ? 'Drop the files here ...' : 'Drag & drop files here, or click to select'}
        </p>
        <p className="text-sm text-slate-700 mb-4">PDF, PNG, JPG up to 10MB</p>
      </div>

      {/* Page-level document type hint */}
      {normalizedPageDocumentType && (
        <div className="mt-3 text-sm text-slate-700">
          Uploading as: <span className="font-medium">{normalizedPageDocumentType.replace('_', ' ')}</span>
        </div>
      )}

      {/* File List */}
      {files.length > 0 && (
        <div className="mt-6 space-y-3">
          {files.map((fileItem) => (
            <div key={fileItem.id} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
              <div className="flex items-center gap-3 flex-1">
                <File className="w-5 h-5 text-slate-700" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-gray-900 truncate">{fileItem.file.name}</p>
                  <label htmlFor={`document-type-${fileItem.id}`} className="text-xs text-slate-800">
                    Select option:
                  </label>
                  <select
                    id={`document-type-${fileItem.id}`}
                    value={normalizedPageDocumentType || fileItem.documentType}
                    onChange={(e) => updateFileDocumentType(fileItem.id, e.target.value as DocumentType)}
                    disabled={Boolean(normalizedPageDocumentType)}
                    className="mt-1 text-xs border rounded px-2 py-1 disabled:bg-gray-100 disabled:text-slate-700"
                  >
                    {DOCUMENT_TYPES.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Progress */}
                {fileItem.status === 'uploading' && (
                  <div className="w-16">
                    <div className="w-full bg-slate-200 rounded-full h-2">
                      <div
                        className="bg-blue-600 h-2 rounded-full transition-all"
                        style={{ width: `${fileItem.progress}%` }}
                      />
                    </div>
                    <p className="text-xs text-slate-700 mt-1">
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
                  className="shrink-0 p-1 hover:bg-slate-100 rounded"
                  variant="ghost"
                  size="sm"
                  aria-label={`Remove ${fileItem.file.name}`}
                >
                  <X className="w-5 h-5 text-slate-700" />
                </Button>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Upload Button (only when caseId is provided) */}
      {caseId && files.length > 0 && !allFinished && (
        <Button
          onClick={uploadAll}
          disabled={files.every((f) => f.status !== 'pending')}
          className="w-full mt-4 px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-semibold disabled:bg-gray-400 disabled:cursor-not-allowed"
        >
          Upload All Files ({files.filter((f) => f.status === 'pending').length} pending)
        </Button>
      )}

      {!caseId && files.length > 0 && (
        <div className="mt-4 p-3 text-sm text-slate-700 bg-amber-50 rounded">
          Files are staged locally and will be uploaded after the application is created.
        </div>
      )}

      {/* Success Message */}
      {allFinished && allSuccessful && (
        <div className="p-4 bg-green-50 border-l-4 border-green-500 text-green-700 mt-4 rounded">
          <p className="font-semibold">✓ All files uploaded successfully!</p>
          <p className="text-sm mt-1">
            Your documents are being verified by our AI system. You&apos;ll be notified once the process is complete.
          </p>
        </div>
      )}

      {allFinished && hasAnySuccess && hasAnyError && (
        <div className="p-4 bg-amber-50 border-l-4 border-amber-500 text-amber-800 mt-4 rounded">
          <p className="font-semibold">Some files uploaded, but some failed.</p>
          <p className="text-sm mt-1">Retry failed files or remove them before continuing.</p>
        </div>
      )}

      {allFinished && !hasAnySuccess && hasAnyError && (
        <div className="p-4 bg-red-50 border-l-4 border-red-500 text-red-700 mt-4 rounded">
          <p className="font-semibold">No files were uploaded successfully.</p>
          <p className="text-sm mt-1">Please fix file issues and try again.</p>
        </div>
      )}
    </div>
  );
}

