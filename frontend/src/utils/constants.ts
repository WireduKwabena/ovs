// src/utils/constants.ts
export const APPLICATION_TYPES = [
  { value: 'employment', label: 'Employment Verification' },
  { value: 'background', label: 'Background Check' },
  { value: 'credential', label: 'Credential Verification' },
  { value: 'education', label: 'Educational Verification' },
] as const;

export const PRIORITIES = [
  { value: 'low', label: 'Low' },
  { value: 'medium', label: 'Medium' },
  { value: 'high', label: 'High' },
  { value: 'urgent', label: 'Urgent' },
] as const;

export const DOCUMENT_TYPES = [
  { value: 'id_card', label: 'ID Card' },
  { value: 'passport', label: 'Passport' },
  { value: 'certificate', label: 'Certificate' },
  { value: 'diploma', label: 'Diploma' },
  { value: 'employment_letter', label: 'Employment Letter' },
  { value: 'reference_letter', label: 'Reference Letter' },
  { value: 'birth_certificate', label: 'Birth Certificate' },
  { value: 'other', label: 'Other' },
] as const;

export const STATUS_COLORS = {
  pending: 'bg-yellow-100 text-yellow-800 border-yellow-200',
  under_review: 'bg-blue-100 text-blue-800 border-blue-200',
  approved: 'bg-green-100 text-green-800 border-green-200',
  rejected: 'bg-red-100 text-red-800 border-red-200',
  processing: 'bg-purple-100 text-purple-800 border-purple-200',
  verified: 'bg-green-100 text-green-800 border-green-200',
  failed: 'bg-red-100 text-red-800 border-red-200',
} as const;

export const CRITERIA_TYPES = [
  { value: 'document_authenticity', label: 'Document Authenticity', icon: '📄' },
  { value: 'ocr_confidence', label: 'OCR Quality', icon: '🔤' },
  { value: 'data_consistency', label: 'Data Consistency', icon: '🔗' },
  { value: 'fraud_score', label: 'Fraud Risk', icon: '⚠️' },
  { value: 'credential_validity', label: 'Credential Validity', icon: '🎓' },
  { value: 'experience_years', label: 'Years of Experience', icon: '💼' },
  { value: 'education_level', label: 'Education Level', icon: '📚' },
] as const;