// src/types/index.ts - ALL TYPE DEFINITIONS (Redux-Aligned, Expanded)

export interface User {
  id: number;
  email: string;
  full_name: string;
  phone_number: string;
  profile_picture_url:string;
  avatar_url:string;
  date_of_birth: string;
  is_active: boolean;
  created_at: string;
}

export interface AdminUser {
  id: number;
  username: string;
  email: string;
  role: 'admin' | 'reviewer' | 'hr_manager' | 'super_admin';
  is_active: boolean;
  avatar_url:string;
  created_at: string;
}

export interface AuthTokens {
  access: string;
  refresh: string;
}

// Redux AuthState (Data-Only, No Methods)
export interface AuthState {
  user: User | AdminUser | null;
  tokens: AuthTokens | null;  // Updated: Full tokens object
  isAuthenticated: boolean;
  userType: 'applicant' | 'hr_manager' | 'admin' | null;
  loading: boolean;
  error: string | null;
}

// Add ApiError (For Services/Slices)
export interface ApiError {
  message: string;
  errors?: Record<string, string[]>;
  status?: number;
}

export type ApplicationStatus = 'pending' | 'under_review' | 'approved' | 'rejected';
export type ApplicationType = 'employment' | 'background' | 'credential' | 'education';
export type Priority = 'low' | 'medium' | 'high' | 'urgent';

export interface VettingCase {
  id: number;
  case_id: string;
  applicant: User;
  status: ApplicationStatus;
  application_type: ApplicationType;
  priority: Priority;
  consistency_score?: number;
  fraud_risk_score?: number;
  notes?: string;
  created_at: string;
  updated_at: string;
}

export type DocumentType = 
  | 'id_card' 
  | 'passport' 
  | 'certificate' 
  | 'diploma' 
  | 'employment_letter' 
  | 'reference_letter' 
  | 'birth_certificate' 
  | 'other';

export type VerificationStatusType = 'pending' | 'processing' | 'verified' | 'failed' | 'rejected';

export interface Document {
  id: number;
  document_type: DocumentType;
  file_name: string;
  file_path: string;
  file_size: number;
  verification_status: VerificationStatusType;
  ai_confidence_score?: number;
  upload_date: string;
  updated_at: string;
  file_url?: string;
  verification_results?: VerificationResult[];
}

export interface VerificationResult {
  id: number;
  ocr_text: string;
  ocr_confidence: number;
  ocr_method: string;
  authenticity_score: number;
  is_authentic: boolean;
  extracted_data: Record<string, any>;
  cv_checks: Record<string, any>;
  details: Record<string, any>;
  verified_at: string;
}

export interface ApplicationWithDocuments extends VettingCase {
  documents: Document[];
  fraud_result?: FraudDetectionResult;
  consistency_result?: ConsistencyCheckResult;
  rubric_evaluation?: RubricEvaluation;
}

export interface FraudDetectionResult {
  id: number;
  application: VettingCase;
  is_fraud: boolean;
  fraud_probability: number;
  anomaly_score: number;
  risk_level: 'LOW' | 'MEDIUM' | 'HIGH';
  recommendation: 'PROCEED' | 'MANUAL_REVIEW' | 'REJECT';
  feature_scores: Record<string, number>;
  detected_at: string;
}

export interface ConsistencyCheckResult {
  id: number;
  application: VettingCase;
  overall_consistent: boolean;
  overall_score: number;
  name_consistency: Record<string, { match: boolean; score: number }>;
  date_consistency: Record<string, { match: boolean; score: number }>;
  entity_consistency: Record<string, { match: boolean; score: number }>;
  recommendation: string;
  checked_at: string;
}

export interface RubricEvaluation {
  id: number;
  application: VettingCase;
  rubric: VettingRubric;
  overall_score: number;
  criteria_scores: Record<string, { score: number; weight: number }>;
  passed: boolean;
  ai_recommendation: 'AUTO_APPROVE' | 'AUTO_REJECT' | 'MANUAL_REVIEW';
  evaluation_details: Record<string, any>;
  flags: string[];
  warnings: string[];
  evaluated_at: string;
}

export type NotificationType = 
  | 'application_submitted' 
  | 'document_verified' 
  | 'status_updated' 
  | 'approval' 
  | 'rejection' 
  | 'review_required';

export interface Notification {
  id: number;
  notification_type: NotificationType;
  title: string;
  message: string;
  status: 'unread' | 'read' | 'archived';
  metadata: Record<string, any>;
  is_read: boolean;
  created_at: string;
  read_at?: string;
}

export type CriteriaType = 
  | 'document_authenticity' 
  | 'ocr_confidence' 
  | 'data_consistency' 
  | 'fraud_score' 
  | 'credential_validity' 
  | 'background_check' 
  | 'experience_years' 
  | 'education_level' 
  | 'reference_check' 
  | 'custom_field';

export interface RubricCriteria {
  id: number;
  name: string;
  description?: string;
  criteria_type: CriteriaType;
  weight: number;
  minimum_score: number;
  is_mandatory: boolean;
  scoring_rules: Record<string, any>;
  order: number;
}

// src/types/index.ts (Updated - Add uploadedDoc to FileItem)
export interface FileItem {
  file: File;
  id: string;
  status: 'pending' | 'uploading' | 'success' | 'error';
  progress: number;
  documentType: DocumentType;
  uploadedDoc?: Document;  // New: Server response after upload
}

export interface VettingRubric {
  id: number;
  rubric_id?: string;
  name: string;
  description?: string;
  rubric_type: ApplicationType;
  department?: string;
  position_level?: string;
  status?: 'draft' | 'active' | 'archived';
  passing_score: number;
  auto_approve_threshold?: number;
  auto_reject_threshold?: number;
  criteria: RubricCriteria[];
  created_at?: string;
  updated_at?: string;
}

export interface VerificationStatusResponse {
  case_id: string;
  status: ApplicationStatus;
  documents: Array<{
    document_type: string;
    verification_status: VerificationStatusType;
    ai_confidence?: number;
    ocr_confidence?: number;
    authenticity_score?: number;
  }>;
  consistency_check?: Omit<ConsistencyCheckResult, 'id' | 'application'>;
  fraud_detection?: Omit<FraudDetectionResult, 'id' | 'application'>;
  rubric_evaluation?: Omit<RubricEvaluation, 'id' | 'application' | 'rubric'> & { rubric_name: string };
  overall_scores?: {
    consistency?: number;
    fraud_risk?: number;
  };
}

export interface PaginatedResponse<T> {
  results: T[];
  count: number;
  next?: string;
  previous?: string;
}

export interface DashboardStats {
  total_applications: number;
  pending: number;
  under_review: number;
  approved: number;
  rejected: number;
  recent_applications: VettingCase[];
  verification_accuracy?: number;
  avg_processing_time?: number;
  fraud_detection_rate?: number;
}

// Form Interfaces (for validation and submission)
export interface LoginCredentials {
  email: string;
  password: string;
}

export interface RegisterData {
  email: string;
  password: string;
  password_confirm: string;
  first_name: string;
  last_name: string;
  phone_number: string;
  organization: string;
  department: string;
}

export interface CreateApplicationData {
  application_type: ApplicationType;
  priority: Priority;
  notes?: string;
}

export interface UpdateApplicationData {
  status?: ApplicationStatus;
  priority?: Priority;
  notes?: string;
}

export interface UploadDocumentData {
  document: File;
  document_type: DocumentType;
}

export interface ChangePasswordData {
  old_password: string;
  new_password: string;
  new_password_confirm: string;
}

export type CreateRubricData = Omit<VettingRubric, 'id' | 'created_at' | 'updated_at'>;

// API Response Interfaces
export interface LoginResponse {
  user: User | AdminUser;
  tokens: AuthTokens;
  user_type?: 'applicant' | 'hr_manager' | 'admin';
}

export interface RegisterResponse extends LoginResponse {
  message?: string;
}

export interface CreateApplicationResponse {
  success: boolean;
  case: VettingCase;
  message?: string;
}

export interface UploadDocumentResponse {
  success: boolean;
  document: Document;
  message?: string;
}

export interface ProfileResponse {
  user: User | AdminUser;
  user_type: string;
}

// Analytics/Chart Interfaces
export interface ChartDataPoint {
  name: string;
  value: number;
  fill?: string;
}

export interface AnalyticsData {
  verification_accuracy: number;
  avg_processing_time: number;
  fraud_detection_rate: number;
  status_distribution: ChartDataPoint[];
  monthly_submissions: { month: string; count: number }[];
}

// Criteria Override Interface
export interface CriteriaOverride {
  id?: number;
  evaluation_id: number;
  criteria_id: number;
  original_score: number;
  override_score: number;
  reason: string;
  overridden_at?: string;
}

// Audit Log Interface (for admin views)
export interface AuditLog {
  id: number;
  user?: string;
  admin_user?: string;
  action: string;
  entity_type: string;
  entity_id?: number;
  changes: Record<string, any>;
  ip_address?: string;
  created_at: string;
}

// ML Model Metrics Interface
export interface MLModelMetrics {
  id: number;
  model_name: string;
  model_version: string;
  accuracy: number;
  precision: number;
  recall: number;
  f1_score: number;
  confusion_matrix: Record<string, number>;
  trained_at: string;
  evaluated_at: string;
}

// File Upload Progress (for UI state)
export interface UploadProgress {
  progress: number;
  file_name: string;
  status: 'uploading' | 'completed' | 'failed';
  error?: string;
}
