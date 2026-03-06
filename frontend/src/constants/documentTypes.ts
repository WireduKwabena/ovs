import type { DocumentType } from "@/types";

export interface DocumentTypeOption {
  value: DocumentType;
  label: string;
}

export const DOCUMENT_TYPE_OPTIONS: DocumentTypeOption[] = [
  { value: "id_card", label: "National ID Card" },
  { value: "passport", label: "Passport" },
  { value: "drivers_license", label: "Driver's License" },
  { value: "birth_certificate", label: "Birth Certificate" },
  { value: "degree", label: "Degree / Certificate" },
  { value: "transcript", label: "Academic Transcript" },
  { value: "employment_letter", label: "Employment Letter" },
  { value: "reference_letter", label: "Reference Letter" },
  { value: "pay_slip", label: "Pay Slip" },
  { value: "bank_statement", label: "Bank Statement" },
  { value: "utility_bill", label: "Utility Bill" },
  { value: "other", label: "Other" },
];

const DOCUMENT_TYPE_VALUE_SET = new Set<DocumentType>(
  DOCUMENT_TYPE_OPTIONS.map((option) => option.value),
);

export const getDocumentTypeLabel = (value: string): string => {
  const match = DOCUMENT_TYPE_OPTIONS.find((option) => option.value === value);
  return match?.label || value;
};

export const normalizeRequiredDocumentTypes = (raw: unknown): DocumentType[] => {
  if (!Array.isArray(raw)) {
    return [];
  }
  const normalized: DocumentType[] = [];
  for (const item of raw) {
    const value = String(item) as DocumentType;
    if (!DOCUMENT_TYPE_VALUE_SET.has(value)) {
      continue;
    }
    if (!normalized.includes(value)) {
      normalized.push(value);
    }
  }
  return normalized;
};
