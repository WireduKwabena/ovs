// src/types/index.ts - ALL TYPE DEFINITIONS (Redux-Aligned, Expanded)

export interface User {
  id: number;
  email: string;
  full_name: string;
  user_type?: 'applicant' | 'hr_manager' | 'admin';
  phone_number: string;
  profile_picture_url:string;
  avatar_url:string;
  date_of_birth: string;
  is_active: boolean;
  created_at: string;
}

export interface AdminUser {
  id: number;
  email: string;
  user_type?: 'applicant' | 'hr_manager' | 'admin';
  role_display?: string;
  username?: string;
  role?: 'admin' | 'reviewer' | 'hr_manager' | 'super_admin';
  is_active: boolean;
  avatar_url?:string;
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

export interface FraudDetectionApiResult {
  id: string;
  application: number | string;
  application_case_id: string;
  is_fraud: boolean;
  fraud_probability: number;
  anomaly_score: number;
  risk_level: "LOW" | "MEDIUM" | "HIGH";
  risk_level_display?: string;
  recommendation: "PROCEED" | "MANUAL_REVIEW" | "REJECT";
  recommendation_display?: string;
  feature_scores: Record<string, number>;
  detected_at: string;
}

export interface FraudStatistics {
  total_scans: number;
  fraud_detected: number;
  fraud_rate: number;
  risk_distribution: {
    HIGH: number;
    MEDIUM: number;
    LOW: number;
  };
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

export interface ConsistencyCheckApiResult {
  id: string;
  application: number | string;
  application_case_id: string;
  overall_consistent: boolean;
  overall_score: number;
  name_consistency: Record<string, { match: boolean; score: number }>;
  date_consistency: Record<string, { match: boolean; score: number }>;
  entity_consistency: Record<string, { match: boolean; score: number }>;
  recommendation: string;
  checked_at: string;
}

export interface ConsistencyStatistics {
  total_checks: number;
  consistent_count: number;
  consistency_rate: number;
  average_score: number;
  median_score: number;
}

export interface SocialProfileCheckApiResult {
  id: string;
  application: number | string;
  application_case_id: string;
  consent_provided: boolean;
  profiles_checked: number;
  overall_score: number;
  risk_level: "LOW" | "MEDIUM" | "HIGH";
  risk_level_display?: string;
  recommendation: string;
  automated_decision_allowed: boolean;
  decision_constraints: unknown[];
  profiles: unknown[];
  checked_at: string;
  updated_at: string;
}

export interface SocialProfileStatistics {
  total_checks: number;
  manual_review_count: number;
  manual_review_rate: number;
  average_score: number;
  risk_distribution: {
    HIGH: number;
    MEDIUM: number;
    LOW: number;
  };
}

export type BackgroundCheckStatus =
  | "pending"
  | "submitted"
  | "in_progress"
  | "completed"
  | "manual_review"
  | "failed"
  | "cancelled";

export type BackgroundCheckType =
  | "criminal"
  | "employment"
  | "education"
  | "kyc_aml"
  | "identity";

export type BackgroundCheckRiskLevel = "low" | "medium" | "high" | "unknown";

export type BackgroundCheckRecommendation = "clear" | "review" | "reject" | "unavailable";

export interface BackgroundCheck {
  id: string;
  case: number;
  case_id: string;
  applicant_email: string;
  check_type: BackgroundCheckType;
  provider_key: string;
  status: BackgroundCheckStatus;
  external_reference: string;
  score: number | null;
  risk_level: BackgroundCheckRiskLevel;
  recommendation: BackgroundCheckRecommendation;
  request_payload: Record<string, unknown>;
  response_payload: Record<string, unknown>;
  result_summary: Record<string, unknown>;
  consent_evidence: Record<string, unknown>;
  submitted_by: number | null;
  submitted_by_email: string;
  error_code: string;
  error_message: string;
  submitted_at: string | null;
  last_polled_at: string | null;
  webhook_received_at: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
  refresh_queued?: boolean;
}

export interface BackgroundCheckEvent {
  id: number;
  event_type: "submitted" | "provider_update" | "webhook" | "manual" | "error";
  status_before: string;
  status_after: string;
  payload: Record<string, unknown>;
  message: string;
  created_at: string;
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
  recent_applications: Array<{
    id: string;
    case_id: string;
    applicant_name: string;
    application_type: string;
    status: ApplicationStatus;
    created_at: string;
    rubric_score?: number | null;
  }>;
  verification_accuracy?: number;
  avg_processing_time?: number;
  fraud_detection_rate?: number;
}


export interface AdminCase {
  id: string;
  case_id: string;
  applicant_name: string;
  applicant_email: string;
  status: ApplicationStatus;
  application_type: string;
  priority: Priority | string;
  consistency_score?: number | null;
  fraud_risk_score?: number | null;
  created_at: string;
  updated_at: string;
  admin?: string | null;
}

export interface AdminCasesResponse {
  results: AdminCase[];
  count: number;
  page: number;
  page_size: number;
  total_pages: number;
  ordering?: string;
}

export interface AdminManagedUser {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  full_name: string;
  user_type: "admin" | "hr_manager" | "applicant";
  is_active: boolean;
  is_staff: boolean;
  is_superuser: boolean;
  is_two_factor_enabled: boolean;
  last_login: string | null;
  created_at: string;
  updated_at: string;
}

export interface AdminUsersResponse {
  results: AdminManagedUser[];
  count: number;
  page: number;
  page_size: number;
  total_pages: number;
  ordering?: string;
}

export interface AdminUserUpdatePayload {
  user_type?: "admin" | "hr_manager" | "applicant";
  is_active?: boolean;
  is_staff?: boolean;
  reset_two_factor?: boolean;
}
export type CampaignStatus = 'draft' | 'active' | 'closed' | 'archived';

export interface VettingCampaign {
  id: number;
  name: string;
  description: string;
  status: CampaignStatus;
  starts_at: string | null;
  ends_at: string | null;
  settings_json: Record<string, unknown>;
  initiated_by: number;
  initiated_by_email?: string;
  created_at: string;
  updated_at: string;
}

export interface CampaignDashboard {
  total_candidates: number;
  invited: number;
  registered: number;
  in_progress: number;
  completed: number;
  reviewed: number;
  approved: number;
  rejected: number;
  escalated: number;
}

export interface CandidateProfile {
  id: number;
  first_name: string;
  last_name: string;
  full_name?: string;
  email: string;
  phone_number: string;
  preferred_channel: 'email' | 'sms';
  consent_recording: boolean;
  consent_ai_processing: boolean;
  created_at: string;
  updated_at: string;
}

export interface CandidateSocialProfile {
  id: number;
  candidate: number;
  platform: string;
  platform_display?: string;
  url: string;
  username: string;
  display_name: string;
  is_primary: boolean;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export type CandidateEnrollmentStatus =
  | 'invited'
  | 'registered'
  | 'in_progress'
  | 'completed'
  | 'reviewed'
  | 'approved'
  | 'rejected'
  | 'escalated';

export interface CandidateEnrollment {
  id: number;
  campaign: number;
  campaign_name?: string;
  candidate: number;
  candidate_email?: string;
  status: CandidateEnrollmentStatus;
  invited_at: string | null;
  registered_at: string | null;
  completed_at: string | null;
  reviewed_at: string | null;
  review_notes: string;
  decision_by: number | null;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export type InvitationChannel = 'email' | 'sms';
export type InvitationStatus = 'pending' | 'sent' | 'failed' | 'accepted' | 'expired';

export interface Invitation {
  id: number;
  enrollment: number;
  token: string;
  channel: InvitationChannel;
  status: InvitationStatus;
  send_to: string;
  expires_at: string;
  sent_at: string | null;
  accepted_at: string | null;
  attempts: number;
  last_error: string;
  created_by: number | null;
  created_at: string;
  updated_at: string;
  accept_url?: string;
}

export interface CandidateImportRow {
  first_name: string;
  last_name?: string;
  email: string;
  phone_number?: string;
  preferred_channel?: InvitationChannel;
}

export interface CandidateImportResult {
  campaign_id: number;
  created_candidates: number;
  created_enrollments: number;
  created_invitations: number;
  errors: Array<{ email?: string | null; error: string }>;
}

export interface CandidateAccessContext {
  session_key: string;
  session_expires_at: string;
  enrollment_id: number;
  enrollment_status: CandidateEnrollmentStatus;
  campaign: {
    id: number;
    name: string;
    status: CampaignStatus;
  };
  candidate: {
    id: number;
    first_name: string;
    last_name: string;
    email: string;
    preferred_channel: InvitationChannel;
  };
}

export interface CandidateAccessConsumeResponse extends CandidateAccessContext {
  pass_type: string;
  remaining_uses: number;
  message: string;
}

export interface CandidateAccessResults {
  available: boolean;
  enrollment_id: number;
  enrollment_status: CandidateEnrollmentStatus;
  decision: 'approved' | 'rejected' | 'escalated' | null;
  review_notes: string;
  results: Record<string, unknown>;
  case: Record<string, unknown> | null;
  latest_interview: Record<string, unknown> | null;
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
  subscription_reference?: string;
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
  backup_codes?: string[];
}

export interface TwoFactorStatusResponse {
  user_type: "admin" | "hr_manager" | "applicant";
  two_factor_required: boolean;
  applicant_exempt: boolean;
  is_two_factor_enabled: boolean;
  has_totp_secret: boolean;
  backup_codes_remaining: number;
}

export interface TwoFactorSetupResponse {
  provisioning_uri: string;
}

export interface TwoFactorBackupCodesResponse {
  message: string;
  backup_codes: string[];
}

export interface TwoFactorChallengeResponse {
  message: string;
  token: string;
  user_type?: 'applicant' | 'hr_manager' | 'admin';
  setup_required?: boolean;
  expires_in_seconds?: number;
  provisioning_uri?: string | null;
}

export type LoginAttemptResponse = LoginResponse | TwoFactorChallengeResponse;

export interface RegisterResponse {
  user: User | AdminUser;
  user_type?: 'applicant' | 'hr_manager' | 'admin';
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
  user_type: 'applicant' | 'hr_manager' | 'admin';
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
  id: string;
  user?: number | null;
  user_name?: string | null;
  admin_user?: number | null;
  admin_user_name?: string | null;
  action: string;
  action_display?: string;
  entity_type: string;
  entity_id?: string;
  changes: Record<string, any>;
  ip_address?: string;
  user_agent?: string;
  created_at: string;
}

export interface AuditStatistics {
  total_logs: number;
  action_distribution: Array<{ action: string; count: number }>;
  entity_distribution: Array<{ entity_type: string; count: number }>;
}

// ML Model Metrics Interface
export interface MLModelMetrics {
  id: string;
  model_name: string;
  model_version: string;
  accuracy: number;
  precision: number;
  recall: number;
  f1_score: number;
  confusion_matrix: Record<string, unknown>;
  trained_at: string;
  evaluated_at: string;
}

export interface MLPerformanceSummary {
  models: Record<
    string,
    {
      version: string;
      accuracy: number;
      precision: number;
      recall: number;
      f1_score: number;
      last_evaluated: string;
    }
  >;
  total_models: number;
}

export interface AiMonitorHealthResponse {
  status: string;
  timestamp: string;
  model_name: string;
  monitor: {
    enabled: boolean;
    backend: string;
    use_redis: boolean;
    redis_configured: boolean;
  };
  metrics: Record<string, unknown>;
  drift: Record<string, unknown>;
}

export interface AiMonitorClassifierModelResult {
  available: boolean;
  model_path?: string;
  predicted_label?: string;
  confidence?: number;
  top_k?: Array<{ label: string; score: number }>;
  classes?: string[];
  model_kind?: string;
  error?: string;
}

export interface AiMonitorDocumentTypeAlignment {
  enabled: boolean;
  declared_document_type: string;
  expected?: Record<string, unknown>;
  confidence_threshold?: number;
  mismatch_detected: boolean;
  mismatch_reason?: string;
  details?: Array<{ model?: string; reason?: string }>;
}

export interface AiMonitorDocumentClassificationResponse {
  status: string;
  timestamp: string;
  filename: string;
  document_classification: {
    rvl_cdip: AiMonitorClassifierModelResult;
    midv500: AiMonitorClassifierModelResult;
  };
  document_type_alignment: AiMonitorDocumentTypeAlignment;
}

export interface AiMonitorSocialProfileItem {
  platform?: string;
  url?: string;
  username?: string;
  display_name?: string;
}

export interface AiMonitorSocialProfileResult extends AiMonitorSocialProfileItem {
  provided_platform?: string;
  score: number;
  risk_level: string;
  findings: string[];
  url_reachable?: boolean | null;
  url_status_code?: number | null;
  probe_error?: string | null;
}

export interface AiMonitorSocialProfileResponse {
  status: string;
  timestamp: string;
  case_id: string;
  consent_provided: boolean;
  profiles_checked: number;
  overall_score: number;
  risk_level: string;
  recommendation: string;
  automated_decision_allowed: boolean;
  decision_constraints: Array<{ code: string; reason: string }>;
  profiles: AiMonitorSocialProfileResult[];
}

// File Upload Progress (for UI state)
export interface UploadProgress {
  progress: number;
  file_name: string;
  status: 'uploading' | 'completed' | 'failed';
  error?: string;
}

export type VideoMeetingStatus = "scheduled" | "ongoing" | "completed" | "cancelled";
export type VideoMeetingRole = "host" | "candidate" | "observer";
export type VideoMeetingParticipantStatus = "invited" | "joined" | "left" | "declined";

export interface VideoMeetingParticipant {
  id: string;
  user: string;
  user_email: string;
  user_full_name: string;
  user_type?: "applicant" | "hr_manager" | "admin";
  role: VideoMeetingRole;
  status: VideoMeetingParticipantStatus;
  invited_at: string;
  joined_at: string | null;
  left_at: string | null;
}

export interface VideoMeeting {
  id: string;
  series_id: string | null;
  organizer: string;
  organizer_email: string;
  organizer_name: string;
  case: string | null;
  title: string;
  description: string;
  status: VideoMeetingStatus;
  scheduled_start: string;
  scheduled_end: string;
  timezone: string;
  livekit_room_name: string;
  allow_join_before_seconds: number;
  reminder_before_minutes: number;
  cancellation_reason?: string;
  reminder_before_sent_at: string | null;
  reminder_start_sent_at: string | null;
  created_at: string;
  updated_at: string;
  participants: VideoMeetingParticipant[];
}

export interface VideoMeetingCreatePayload {
  case?: string | null;
  title: string;
  description?: string;
  scheduled_start: string;
  scheduled_end: string;
  timezone?: string;
  allow_join_before_seconds?: number;
  reminder_before_minutes?: number;
  participant_user_ids?: string[];
  participant_emails?: string[];
}

export interface VideoMeetingReschedulePayload {
  scheduled_start: string;
  scheduled_end: string;
  timezone?: string;
}

export type VideoMeetingRecurrence = "none" | "daily" | "weekly";

export interface VideoMeetingSeriesPayload extends VideoMeetingCreatePayload {
  recurrence: VideoMeetingRecurrence;
  occurrences: number;
}

export interface VideoMeetingSeriesResponse {
  count: number;
  results: VideoMeeting[];
}

export interface VideoMeetingSeriesReschedulePayload {
  scheduled_start: string;
  scheduled_end: string;
  timezone?: string;
  scope?: "future" | "all";
}

export interface VideoMeetingSeriesCancelPayload {
  reason?: string;
  scope?: "future" | "all";
}

export interface VideoMeetingJoinToken {
  token: string;
  ws_url: string;
  room_name: string;
  expires_in: number;
}

export type VideoMeetingEventAction =
  | "created"
  | "rescheduled"
  | "extended"
  | "cancelled"
  | "started"
  | "completed"
  | "left";

export type VideoMeetingEventScope = "single" | "future" | "all";

export interface VideoMeetingEvent {
  id: string;
  meeting: string;
  actor: string | null;
  actor_email: string | null;
  actor_name: string;
  actor_user_type?: "applicant" | "hr_manager" | "admin";
  action: VideoMeetingEventAction;
  scope: VideoMeetingEventScope;
  detail: string;
  metadata: Record<string, unknown>;
  created_at: string;
}






