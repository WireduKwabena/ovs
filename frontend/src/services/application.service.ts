import api from "./api";
import { toServiceError } from "@/utils/apiError";
import type {
  ApplicationStatus,
  ApplicationType,
  ApplicationWithDocuments,
  Document,
  DocumentType,
  Priority,
  User,
  VerificationResult,
  VerificationStatusResponse,
  VerificationStatusType,
  VettingCase,
} from "@/types";

export interface CreateApplicationData {
  application_type: string;
  priority: string;
  notes?: string;
}

export interface SocialProfileRecheckResponse {
  status: "ok" | "skipped" | "error";
  success?: boolean;
  reason?: string;
  record_id?: string;
  result?: Record<string, unknown>;
  [key: string]: unknown;
}

interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

const APPLICATION_TYPES = new Set<ApplicationType>([
  "employment",
  "background",
  "credential",
  "education",
]);
const PRIORITIES = new Set<Priority>(["low", "medium", "high", "urgent"]);
const APPLICATION_STATUSES = new Set<ApplicationStatus>([
  "pending",
  "document_upload",
  "document_analysis",
  "interview_scheduled",
  "interview_in_progress",
  "under_review",
  "approved",
  "rejected",
  "on_hold",
]);
const DOCUMENT_TYPES = new Set<DocumentType>([
  "id_card",
  "passport",
  "drivers_license",
  "degree",
  "transcript",
  "pay_slip",
  "bank_statement",
  "utility_bill",
  "certificate",
  "diploma",
  "employment_letter",
  "reference_letter",
  "birth_certificate",
  "other",
]);
const DOCUMENT_STATUSES = new Set<VerificationStatusType>([
  "uploaded",
  "queued",
  "pending",
  "processing",
  "verified",
  "failed",
  "flagged",
  "rejected",
]);


const asObject = (value: unknown): Record<string, unknown> =>
  value && typeof value === "object" ? (value as Record<string, unknown>) : {};

const asString = (value: unknown): string => (typeof value === "string" ? value : "");

const asOptionalString = (value: unknown): string | undefined => {
  const normalized = asString(value).trim();
  return normalized || undefined;
};

const asNumber = (value: unknown): number | undefined => {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : undefined;
  }
  return undefined;
};

const extractResults = <T>(payload: PaginatedResponse<T> | T[]): T[] => {
  if (Array.isArray(payload)) {
    return payload;
  }
  return Array.isArray(payload.results) ? payload.results : [];
};

const normalizeApplicationType = (value: unknown): ApplicationType => {
  const normalized = asString(value).trim().toLowerCase();
  if (APPLICATION_TYPES.has(normalized as ApplicationType)) {
    return normalized as ApplicationType;
  }
  return "employment";
};

const normalizePriority = (value: unknown): Priority => {
  const normalized = asString(value).trim().toLowerCase();
  if (PRIORITIES.has(normalized as Priority)) {
    return normalized as Priority;
  }
  return "medium";
};

const normalizeApplicationStatus = (value: unknown): ApplicationStatus => {
  const normalized = asString(value).trim().toLowerCase();
  if (APPLICATION_STATUSES.has(normalized as ApplicationStatus)) {
    return normalized as ApplicationStatus;
  }
  return "pending";
};

const normalizeDocumentType = (value: unknown): DocumentType => {
  const normalized = asString(value).trim().toLowerCase();
  if (DOCUMENT_TYPES.has(normalized as DocumentType)) {
    return normalized as DocumentType;
  }
  return "other";
};

const normalizeDocumentStatus = (value: unknown): VerificationStatusType => {
  const normalized = asString(value).trim().toLowerCase();
  if (DOCUMENT_STATUSES.has(normalized as VerificationStatusType)) {
    return normalized as VerificationStatusType;
  }
  return "pending";
};

const normalizeVerificationResult = (raw: unknown): VerificationResult | undefined => {
  if (!raw || typeof raw !== "object") {
    return undefined;
  }
  const payload = asObject(raw);
  const id = asString(payload.id).trim();
  if (!id) {
    return undefined;
  }
  return {
    id,
    document: asOptionalString(payload.document),
    ocr_text: asString(payload.ocr_text),
    ocr_confidence: asNumber(payload.ocr_confidence),
    ocr_language: asOptionalString(payload.ocr_language),
    ocr_method: asOptionalString(payload.ocr_method),
    authenticity_score: asNumber(payload.authenticity_score) ?? 0,
    authenticity_confidence: asNumber(payload.authenticity_confidence),
    is_authentic: Boolean(payload.is_authentic),
    metadata_check_passed: Boolean(payload.metadata_check_passed),
    visual_check_passed: Boolean(payload.visual_check_passed),
    tampering_detected: Boolean(payload.tampering_detected),
    fraud_risk_score: asNumber(payload.fraud_risk_score),
    fraud_prediction: asOptionalString(payload.fraud_prediction),
    fraud_indicators: Array.isArray(payload.fraud_indicators)
      ? payload.fraud_indicators.map((item) => String(item))
      : undefined,
    extracted_data: payload.extracted_data as Record<string, unknown> | undefined,
    cv_checks: payload.cv_checks as Record<string, unknown> | undefined,
    detailed_results: payload.detailed_results as Record<string, unknown> | undefined,
    details: payload.details as Record<string, unknown> | undefined,
    ocr_model_version: asOptionalString(payload.ocr_model_version),
    authenticity_model_version: asOptionalString(payload.authenticity_model_version),
    fraud_model_version: asOptionalString(payload.fraud_model_version),
    created_at: asOptionalString(payload.created_at),
    verified_at: asOptionalString(payload.verified_at),
  };
};

const normalizeDocument = (raw: unknown): Document => {
  const payload = asObject(raw);
  const id = asString(payload.id).trim();
  const documentType = normalizeDocumentType(payload.document_type);
  const status = normalizeDocumentStatus(payload.status ?? payload.verification_status);
  const uploadedAt = asOptionalString(payload.uploaded_at ?? payload.upload_date) || "";
  const processedAt = asOptionalString(payload.processed_at) || null;
  const verificationResult = normalizeVerificationResult(payload.verification_result);
  const aiConfidence =
    asNumber(payload.ai_confidence_score) ??
    asNumber(verificationResult?.authenticity_confidence) ??
    asNumber(verificationResult?.ocr_confidence);
  const fileName =
    asOptionalString(payload.original_filename) ||
    asOptionalString(payload.file_name) ||
    asOptionalString(payload.document_type_display) ||
    "Document";
  const filePath = asOptionalString(payload.file_url ?? payload.file_path ?? payload.file) || "";

  return {
    id,
    case: asOptionalString(payload.case),
    document_type: documentType,
    document_type_display: asOptionalString(payload.document_type_display),
    file: asOptionalString(payload.file),
    original_filename: asOptionalString(payload.original_filename) || fileName,
    file_name: fileName,
    file_path: filePath,
    file_size: asNumber(payload.file_size) ?? 0,
    mime_type: asOptionalString(payload.mime_type),
    status,
    status_display: asOptionalString(payload.status_display),
    verification_status: status,
    ocr_completed: Boolean(payload.ocr_completed),
    authenticity_check_completed: Boolean(payload.authenticity_check_completed),
    fraud_check_completed: Boolean(payload.fraud_check_completed),
    processing_error: asOptionalString(payload.processing_error),
    retry_count: asNumber(payload.retry_count),
    extracted_text: asOptionalString(payload.extracted_text),
    extracted_data: payload.extracted_data as Record<string, unknown> | undefined,
    ai_confidence_score: aiConfidence,
    upload_date: uploadedAt,
    uploaded_at: uploadedAt || undefined,
    processed_at: processedAt,
    updated_at:
      asOptionalString(payload.updated_at) ||
      processedAt ||
      uploadedAt ||
      new Date().toISOString(),
    file_url: asOptionalString(payload.file_url),
    verification_result: verificationResult,
    verification_results: verificationResult ? [verificationResult] : [],
  };
};

const normalizeApplicant = (
  rawApplicant: unknown,
  fallbackEmail: string,
  createdAt: string,
): User => {
  if (rawApplicant && typeof rawApplicant === "object") {
    const payload = rawApplicant as Partial<User> & Record<string, unknown>;
    const id = String(payload.id ?? payload.email ?? "unknown");
    const email = String(payload.email ?? fallbackEmail ?? "");
    const fullName =
      String(payload.full_name ?? "").trim() ||
      `${String(payload.first_name ?? "").trim()} ${String(payload.last_name ?? "").trim()}`.trim() ||
      email ||
      "Applicant";
    return {
      id,
      email,
      full_name: fullName,
      first_name: asOptionalString(payload.first_name),
      last_name: asOptionalString(payload.last_name),
      user_type: payload.user_type as User["user_type"],
      roles: Array.isArray(payload.roles) ? (payload.roles as string[]) : [],
      group_roles: Array.isArray(payload.group_roles) ? (payload.group_roles as string[]) : [],
      capabilities: Array.isArray(payload.capabilities) ? (payload.capabilities as string[]) : [],
      is_internal_operator: Boolean(payload.is_internal_operator),
      phone_number: String(payload.phone_number ?? ""),
      organization: asOptionalString(payload.organization),
      department: asOptionalString(payload.department),
      profile_picture_url: String(payload.profile_picture_url ?? ""),
      avatar_url: String(payload.avatar_url ?? ""),
      date_of_birth: String(payload.date_of_birth ?? ""),
      profile: (payload.profile as User["profile"]) ?? null,
      is_active: Boolean(payload.is_active ?? true),
      is_staff: Boolean(payload.is_staff),
      is_superuser: Boolean(payload.is_superuser),
      created_at: String(payload.created_at ?? createdAt),
    };
  }

  const fallbackIdentifier = String((rawApplicant ?? fallbackEmail) || "unknown");
  const email = fallbackEmail || "";
  const fullName = email || "Applicant";
  return {
    id: fallbackIdentifier,
    email,
    full_name: fullName,
    phone_number: "",
    profile_picture_url: "",
    avatar_url: "",
    date_of_birth: "",
    profile: null,
    is_active: true,
    created_at: createdAt,
  };
};

const normalizeCase = (raw: unknown): ApplicationWithDocuments => {
  const payload = asObject(raw);
  const createdAt = asOptionalString(payload.created_at) || new Date().toISOString();
  const documents = Array.isArray(payload.documents)
    ? payload.documents.map((document) => normalizeDocument(document))
    : [];
  const applicantEmail = asOptionalString(payload.applicant_email) || "";
  const applicant = normalizeApplicant(payload.applicant, applicantEmail, createdAt);

  return {
    ...(payload as unknown as ApplicationWithDocuments),
    id: asString(payload.id),
    case_id: asString(payload.case_id),
    vetting_dossier_id: asOptionalString(payload.vetting_dossier_id) || asString(payload.case_id),
    applicant,
    applicant_email: applicantEmail || undefined,
    position_applied: asOptionalString(payload.position_applied),
    office_title: asOptionalString(payload.office_title) || asOptionalString(payload.position_applied),
    appointment_exercise_id: asOptionalString(payload.appointment_exercise_id),
    appointment_exercise_name: asOptionalString(payload.appointment_exercise_name),
    department: asOptionalString(payload.department),
    status: normalizeApplicationStatus(payload.status),
    vetting_dossier_status: normalizeApplicationStatus(payload.vetting_dossier_status ?? payload.status),
    vetting_dossier_status_display: asOptionalString(payload.vetting_dossier_status_display),
    application_type: normalizeApplicationType(payload.application_type),
    priority: normalizePriority(payload.priority),
    notes: asString(payload.notes),
    created_at: createdAt,
    updated_at: asOptionalString(payload.updated_at) || createdAt,
    documents,
  };
};

export const applicationService = {
  async create(data: CreateApplicationData): Promise<VettingCase> {
    try {
      const response = await api.post<VettingCase>("/applications/cases/", data);
      return normalizeCase(response.data);
    } catch (error) {
      throw toServiceError(error, "Creation failed");
    }
  },

  async getAll(options?: { scope?: "all" | "assigned" | "mine" }): Promise<ApplicationWithDocuments[]> {
    try {
      const response = await api.get<PaginatedResponse<ApplicationWithDocuments> | ApplicationWithDocuments[]>(
        "/applications/cases/",
        {
          params: options?.scope ? { scope: options.scope } : undefined,
        },
      );
      return extractResults(response.data).map((row) => normalizeCase(row));
    } catch (error) {
      throw toServiceError(error, "Fetch failed");
    }
  },

  async getById(caseId: string): Promise<ApplicationWithDocuments> {
    try {
      const response = await api.get<ApplicationWithDocuments>(`/applications/cases/${caseId}/`);
      return normalizeCase(response.data);
    } catch (error) {
      throw toServiceError(error, "Detail fetch failed");
    }
  },

  async update(caseId: string, data: Partial<VettingCase>): Promise<VettingCase> {
    try {
      const response = await api.patch<VettingCase>(`/applications/cases/${caseId}/`, data);
      return normalizeCase(response.data);
    } catch (error) {
      throw toServiceError(error, "Update failed");
    }
  },

  async delete(caseId: string): Promise<void> {
    try {
      await api.delete(`/applications/cases/${caseId}/`);
    } catch (error) {
      throw toServiceError(error, "Deletion failed");
    }
  },

  async approve(caseId: string): Promise<VettingCase> {
    return applicationService.update(caseId, { status: "approved" });
  },

  async reject(caseId: string): Promise<VettingCase> {
    return applicationService.update(caseId, { status: "rejected" });
  },

  async uploadDocument(
    caseId: string,
    file: File,
    documentType: string,
  ): Promise<{ document: Document; message?: string }> {
    try {
      const formData = new FormData();
      formData.append("document", file);
      formData.append("document_type", documentType);

      const response = await api.post(
        `/applications/cases/${caseId}/upload-document/`,
        formData,
        {
          headers: {
            "Content-Type": "multipart/form-data",
          },
        },
      );
      const payload = asObject(response.data);
      if ("document" in payload) {
        return {
          document: normalizeDocument(payload.document),
          message: asOptionalString(payload.message),
        };
      }
      return {
        document: normalizeDocument(response.data),
      };
    } catch (error) {
      throw toServiceError(error, "Upload failed");
    }
  },

  async getVerificationStatus(caseId: string): Promise<VerificationStatusResponse> {
    try {
      const response = await api.get<VerificationStatusResponse>(`/applications/cases/${caseId}/verification-status/`);
      return response.data;
    } catch (error) {
      throw toServiceError(error, "Status fetch failed");
    }
  },

  async recheckSocialProfiles(caseId: string): Promise<SocialProfileRecheckResponse> {
    try {
      const response = await api.post<SocialProfileRecheckResponse>(
        `/applications/cases/${caseId}/recheck-social-profiles/`,
        {},
      );
      return response.data;
    } catch (error) {
      throw toServiceError(error, "Social profile recheck failed");
    }
  },

  async listDocuments(): Promise<Document[]> {
    try {
      const response = await api.get<PaginatedResponse<Document> | Document[]>("/applications/documents/");
      return extractResults(response.data).map((row) => normalizeDocument(row));
    } catch (error) {
      throw toServiceError(error, "Document list fetch failed");
    }
  },

  async getDocumentById(documentId: string): Promise<Document> {
    try {
      const response = await api.get<Document>(`/applications/documents/${documentId}/`);
      return normalizeDocument(response.data);
    } catch (error) {
      throw toServiceError(error, "Document detail fetch failed");
    }
  },
};
