// src/types/index.ts - ALL TYPE DEFINITIONS (Redux-Aligned, Expanded)

export interface User {
  id: string | number;
  email: string;
  first_name?: string;
  last_name?: string;
  full_name: string;
  user_type?: 'applicant' | 'internal' | 'admin';
  roles?: string[];
  group_roles?: string[];
  capabilities?: string[];
  is_internal_operator?: boolean;
  phone_number: string;
  organization?: string;
  department?: string;
  profile_picture_url:string;
  avatar_url:string;
  date_of_birth: string;
  profile?: ExtendedUserProfile | null;
  is_active: boolean;
  is_staff?: boolean;
  is_superuser?: boolean;
  created_at: string;
}

export interface OrganizationSummary {
  id: string;
  code: string;
  name: string;
  organization_type: string;
}

export interface OrganizationMembershipContext {
  id: string;
  organization_id: string;
  organization_code: string;
  organization_name: string;
  organization_type: string;
  title: string;
  membership_role: string;
  is_default: boolean;
  is_active: boolean;
  joined_at?: string | null;
  left_at?: string | null;
}

export interface GovernanceOrganizationBootstrapPayload {
  name: string;
  code?: string;
  organization_type?: string;
}

export interface GovernanceOrganizationBootstrapMembership {
  id: string;
  user: string;
  user_email: string;
  organization: string;
  organization_name: string;
  title: string;
  membership_role: string;
  is_active: boolean;
  is_default: boolean;
  joined_at?: string | null;
  left_at?: string | null;
  metadata?: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  user_full_name?: string;
}

export interface GovernanceOrganizationBootstrapResponse {
  status: string;
  message: string;
  organization: OrganizationSummary;
  membership: GovernanceOrganizationBootstrapMembership;
}

export interface GovernanceOrganizationSummary {
  id: string;
  code: string;
  name: string;
  organization_type: string;
  is_active: boolean;
}

export interface GovernanceOrganizationActorSummary {
  is_platform_admin: boolean;
  can_manage_registry: boolean;
  active_membership_id: string;
  active_membership_role: string;
}

export interface GovernanceOrganizationStats {
  members_total: number;
  members_active: number;
  committees_total: number;
  committees_active: number;
  committee_memberships_active: number;
  active_chairs: number;
}

export interface GovernanceOrganizationSummaryResponse {
  organization: GovernanceOrganizationSummary;
  actor: GovernanceOrganizationActorSummary;
  stats: GovernanceOrganizationStats;
  active_organization_source: string;
}

export interface GovernanceOrganizationMember {
  id: string;
  user: string;
  user_email: string;
  user_full_name?: string;
  organization: string;
  organization_name: string;
  title: string;
  membership_role: string;
  is_active: boolean;
  is_default: boolean;
  joined_at?: string | null;
  left_at?: string | null;
  metadata?: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface GovernanceCommittee {
  id: string;
  organization: string;
  organization_name: string;
  code: string;
  name: string;
  committee_type: string;
  description: string;
  is_active: boolean;
  created_by?: string | null;
  created_by_email?: string;
  metadata?: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface GovernanceCommitteeMembership {
  id: string;
  committee: string;
  committee_name: string;
  organization_name: string;
  user: string;
  user_email: string;
  organization_membership: string | null;
  committee_role: string;
  can_vote: boolean;
  is_active: boolean;
  joined_at?: string | null;
  left_at?: string | null;
  metadata?: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface GovernanceChoiceOption {
  value: string;
  label: string;
}

export interface GovernanceChoicesResponse {
  organization_types: GovernanceChoiceOption[];
  committee_types: GovernanceChoiceOption[];
  committee_roles: GovernanceChoiceOption[];
}

export interface GovernanceMemberOption {
  organization_membership_id: string;
  user_id: string;
  user_email: string;
  user_full_name: string;
  membership_role: string;
  title: string;
  is_active: boolean;
  is_default: boolean;
}

export interface GovernanceCommitteeChairReassignPayload {
  target_committee_membership_id?: string;
  target_user_id?: string;
  organization_membership_id?: string;
  can_vote?: boolean;
  reason_note?: string;
}

export interface GovernanceCommitteeChairReassignResponse {
  committee_id: string;
  previous_chair: {
    membership_id: string;
    user_id: string;
    user_email: string;
  } | null;
  new_chair: {
    membership_id: string;
    user_id: string;
    user_email: string;
    committee_role: string;
  };
  changed_at: string;
}

export interface CommitteeContext {
  id: string;
  committee_id: string;
  committee_code: string;
  committee_name: string;
  committee_type: string;
  organization_id: string;
  organization_code: string;
  organization_name: string;
  committee_role: string;
  can_vote: boolean;
  joined_at?: string | null;
  left_at?: string | null;
}

export interface AdminUser {
  id: string | number;
  email: string;
  first_name?: string;
  last_name?: string;
  full_name?: string;
  phone_number?: string;
  organization?: string;
  department?: string;
  user_type?: 'applicant' | 'internal' | 'admin';
  roles?: string[];
  group_roles?: string[];
  capabilities?: string[];
  is_internal_operator?: boolean;
  role_display?: string;
  username?: string;
  role?: 'admin' | 'reviewer' | 'internal' | 'super_admin';
  profile?: ExtendedUserProfile | null;
  is_active: boolean;
  is_staff?: boolean;
  is_superuser?: boolean;
  avatar_url?:string;
  created_at: string;
}

export interface ExtendedUserProfile {
  date_of_birth?: string | null;
  nationality?: string;
  address?: string;
  city?: string;
  country?: string;
  postal_code?: string;
  current_job_title?: string;
  years_of_experience?: number | null;
  linkedin_url?: string;
  bio?: string;
  profile_completion_percentage?: number;
  avatar_url?: string;
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
  userType: 'applicant' | 'internal' | 'admin' | null;
  roles: string[];
  capabilities: string[];
  organizations: OrganizationSummary[];
  organizationMemberships: OrganizationMembershipContext[];
  committees: CommitteeContext[];
  activeOrganization: OrganizationSummary | null;
  activeOrganizationSource: string;
  invalidRequestedOrganizationId: string;
  loading: boolean;
  error: string | null;
}

// Add ApiError (For Services/Slices)
export interface ApiError {
  message: string;
  errors?: Record<string, string[]>;
  status?: number;
}

export type ApplicationStatus =
  | 'pending'
  | 'document_upload'
  | 'document_analysis'
  | 'interview_scheduled'
  | 'interview_in_progress'
  | 'under_review'
  | 'approved'
  | 'rejected'
  | 'on_hold';
export type ApplicationType = 'employment' | 'background' | 'credential' | 'education';
export type Priority = 'low' | 'medium' | 'high' | 'urgent';

export interface VettingCase {
  id: string;
  case_id: string;
  vetting_dossier_id?: string;
  applicant: User | string;
  applicant_email?: string;
  position_applied?: string;
  office_title?: string;
  appointment_exercise_id?: string;
  appointment_exercise_name?: string;
  department?: string;
  status: ApplicationStatus;
  vetting_dossier_status?: ApplicationStatus;
  vetting_dossier_status_display?: string;
  application_type?: ApplicationType;
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
  | 'drivers_license'
  | 'degree'
  | 'transcript'
  | 'pay_slip'
  | 'bank_statement'
  | 'utility_bill'
  | 'certificate' 
  | 'diploma' 
  | 'employment_letter' 
  | 'reference_letter' 
  | 'birth_certificate' 
  | 'other';

export type VerificationStatusType =
  | 'uploaded'
  | 'queued'
  | 'pending'
  | 'processing'
  | 'verified'
  | 'failed'
  | 'flagged'
  | 'rejected';

export interface Document {
  id: string;
  case?: string;
  document_type: DocumentType;
  document_type_display?: string;
  file?: string;
  original_filename?: string;
  file_name: string;
  file_path: string;
  file_size: number;
  mime_type?: string;
  status: VerificationStatusType;
  status_display?: string;
  verification_status: VerificationStatusType;
  ocr_completed?: boolean;
  authenticity_check_completed?: boolean;
  fraud_check_completed?: boolean;
  processing_error?: string;
  retry_count?: number;
  extracted_text?: string;
  extracted_data?: Record<string, unknown>;
  ai_confidence_score?: number;
  upload_date: string;
  uploaded_at?: string;
  processed_at?: string | null;
  updated_at?: string;
  file_url?: string;
  verification_result?: VerificationResult;
  verification_results?: VerificationResult[];
}

export interface VerificationResult {
  id: string;
  document?: string;
  ocr_text: string;
  ocr_confidence?: number;
  ocr_language?: string;
  ocr_method?: string;
  authenticity_score: number;
  authenticity_confidence?: number;
  is_authentic: boolean;
  metadata_check_passed?: boolean;
  visual_check_passed?: boolean;
  tampering_detected?: boolean;
  fraud_risk_score?: number;
  fraud_prediction?: string;
  fraud_indicators?: string[];
  extracted_data?: Record<string, any>;
  cv_checks?: Record<string, any>;
  detailed_results?: Record<string, any>;
  details?: Record<string, any>;
  ocr_model_version?: string;
  authenticity_model_version?: string;
  fraud_model_version?: string;
  created_at?: string;
  verified_at?: string;
}

export interface ApplicationWithDocuments extends VettingCase {
  documents: Document[];
  fraud_result?: FraudDetectionResult;
  consistency_result?: ConsistencyCheckResult;
  rubric_evaluation?: RubricEvaluation;
}

export interface FraudDetectionResult {
  id: string;
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
  application: string;
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
  id: string;
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
  application: string;
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
  application: string;
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
  case: string;
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
  submitted_by: string | null;
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
  id: string;
  event_type: "submitted" | "provider_update" | "webhook" | "manual" | "error";
  status_before: string;
  status_after: string;
  payload: Record<string, unknown>;
  message: string;
  created_at: string;
}

export interface RubricEvaluation {
  id: string;
  application?: VettingCase | string;
  rubric?: VettingRubric | string;
  rubric_id?: string;
  overall_score?: number;
  total_weighted_score?: number;
  criteria_scores?: Record<string, { score: number; weight: number }>;
  passed?: boolean;
  passes_threshold?: boolean;
  ai_recommendation?: 'AUTO_APPROVE' | 'AUTO_REJECT' | 'MANUAL_REVIEW';
  final_decision?: string;
  requires_manual_review?: boolean;
  evaluation_details?: Record<string, any>;
  flags?: string[];
  warnings?: string[];
  decision_recommendation?: {
    id: string;
    recommendation_status: string;
    advisory_only: boolean;
    blocking_issues_count: number;
    warnings_count: number;
  } | null;
  evaluated_at?: string;
}

export type NotificationType = 
  | 'application_submitted' 
  | 'document_verified' 
  | 'status_updated' 
  | 'approval' 
  | 'rejection' 
  | 'review_required'
  | 'in_app'
  | 'email'
  | 'sms';

export interface Notification {
  id: string;
  notification_type: NotificationType;
  title: string;
  subject?: string;
  message: string;
  status: 'unread' | 'read' | 'archived' | 'pending' | 'sent' | 'failed';
  metadata: Record<string, any>;
  is_read: boolean;
  is_archived?: boolean;
  archived_at?: string;
  created_at: string;
  read_at?: string;
  priority?: 'low' | 'normal' | 'high' | 'urgent';
}

export type RubricType = "general" | "technical" | "executive" | "sensitive" | "custom";
export type RubricCriteriaType = "document" | "consistency" | "interview" | "behavioral" | "technical" | "custom";
export type RubricScoringMethod = "ai_score" | "manual_rating" | "binary" | "calculated";

export interface RubricCriteria {
  id: string;
  rubric?: string;
  name: string;
  description: string;
  criteria_type: RubricCriteriaType;
  criteria_type_display?: string;
  scoring_method: RubricScoringMethod;
  scoring_method_display?: string;
  weight: number;
  minimum_score?: number | null;
  is_mandatory: boolean;
  evaluation_guidelines?: string;
  display_order: number;
  // Backward-compat fields kept optional for existing UI helpers.
  scoring_rules?: Record<string, any>;
  order?: number;
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
  id: string;
  name: string;
  description: string;
  rubric_type: RubricType;
  rubric_type_display?: string;
  document_authenticity_weight: number;
  consistency_weight: number;
  fraud_detection_weight: number;
  interview_weight: number;
  manual_review_weight: number;
  passing_score: number;
  auto_approve_threshold: number;
  auto_reject_threshold: number;
  minimum_document_score: number;
  maximum_fraud_score: number;
  require_interview: boolean;
  critical_flags_auto_fail: boolean;
  max_unresolved_flags: number;
  is_active: boolean;
  status?: "active" | "archived";
  is_default: boolean;
  created_by?: string | null;
  criteria: RubricCriteria[];
  total_weight?: number;
  // Optional legacy UI fields (not persisted by backend)
  department?: string;
  position_level?: string;
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
  user_type: "admin" | "internal" | "applicant";
  group_roles?: string[];
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
  user_type?: "admin" | "internal" | "applicant";
  is_active?: boolean;
  is_staff?: boolean;
  reset_two_factor?: boolean;
  group_roles?: string[];
}
export type CampaignStatus = 'draft' | 'active' | 'closed' | 'archived';
export type CampaignExerciseType =
  | "ministerial"
  | "judicial"
  | "board"
  | "local_gov"
  | "diplomatic"
  | "security";

export interface VettingCampaign {
  id: string;
  organization?: string | null;
  organization_name?: string;
  name: string;
  appointment_exercise_name?: string;
  description: string;
  status: CampaignStatus;
  appointment_exercise_status?: CampaignStatus;
  starts_at: string | null;
  ends_at: string | null;
  settings_json: Record<string, unknown>;
  exercise_type?: CampaignExerciseType | "";
  jurisdiction?: GovernmentBranch | "";
  positions?: string[];
  position_ids?: string[];
  office_ids?: string[];
  approval_template?: string | null;
  appointment_route_template_id?: string | null;
  appointment_authority?: string;
  requires_parliamentary_confirmation?: boolean;
  gazette_reference?: string;
  required_document_types?: DocumentType[];
  initiated_by: string;
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
  id: string;
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
  id: string;
  candidate: string;
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
  id: string;
  campaign: string;
  campaign_name?: string;
  candidate: string;
  candidate_email?: string;
  status: CandidateEnrollmentStatus;
  invited_at: string | null;
  registered_at: string | null;
  completed_at: string | null;
  reviewed_at: string | null;
  review_notes: string;
  decision_by: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export type InvitationChannel = 'email' | 'sms';
export type InvitationStatus = 'pending' | 'sent' | 'failed' | 'accepted' | 'expired';

export interface Invitation {
  id: string;
  enrollment: string;
  token: string;
  channel: InvitationChannel;
  status: InvitationStatus;
  send_to: string;
  expires_at: string;
  sent_at: string | null;
  accepted_at: string | null;
  attempts: number;
  last_error: string;
  created_by: string | null;
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
  campaign_id: string;
  created_candidates: number;
  created_enrollments: number;
  created_invitations: number;
  errors: Array<{ email?: string | null; error: string }>;
}

export interface CandidateAccessContext {
  session_key: string;
  session_expires_at: string;
  enrollment_id: string;
  enrollment_status: CandidateEnrollmentStatus;
  campaign: {
    id: string;
    name: string;
    status: CampaignStatus;
    required_document_types?: DocumentType[];
  };
  candidate: {
    id: string;
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
  enrollment_id: string;
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
  department: string;
  onboarding_token: string;
  organization?: string;
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

export interface CreateRubricData {
  name: string;
  description: string;
  rubric_type: RubricType;
  document_authenticity_weight: number;
  consistency_weight: number;
  fraud_detection_weight: number;
  interview_weight: number;
  manual_review_weight: number;
  passing_score: number;
  auto_approve_threshold: number;
  auto_reject_threshold: number;
  minimum_document_score: number;
  maximum_fraud_score: number;
  require_interview: boolean;
  critical_flags_auto_fail: boolean;
  max_unresolved_flags: number;
  is_active?: boolean;
  is_default?: boolean;
  criteria?: Array<{
    name: string;
    description: string;
    criteria_type: RubricCriteriaType;
    scoring_method: RubricScoringMethod;
    weight: number;
    minimum_score?: number | null;
    is_mandatory: boolean;
    evaluation_guidelines?: string;
    display_order: number;
  }>;
}

// API Response Interfaces
export interface LoginResponse {
  user: User | AdminUser;
  tokens: AuthTokens;
  user_type?: 'applicant' | 'internal' | 'admin';
  backup_codes?: string[];
}

export interface TwoFactorStatusResponse {
  user_type: "admin" | "internal" | "applicant";
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
  user_type?: 'applicant' | 'internal' | 'admin';
  setup_required?: boolean;
  expires_in_seconds?: number;
  provisioning_uri?: string | null;
}

export type LoginAttemptResponse = LoginResponse | TwoFactorChallengeResponse;

export interface RegisterResponse {
  user: User | AdminUser;
  user_type?: 'applicant' | 'internal' | 'admin';
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
  user_type: 'applicant' | 'internal' | 'admin';
  roles?: string[];
  capabilities?: string[];
  is_internal_operator?: boolean;
  organizations?: OrganizationSummary[];
  organization_memberships?: OrganizationMembershipContext[];
  committees?: CommitteeContext[];
  active_organization?: OrganizationSummary | null;
  active_organization_source?: string;
  invalid_requested_organization_id?: string;
}

export interface OrganizationOnboardingTokenState {
  id: string;
  subscription_id: string | null;
  token_preview: string;
  is_active: boolean;
  expires_at: string | null;
  max_uses: number | null;
  uses: number;
  remaining_uses: number | null;
  allowed_email_domain: string;
  last_used_at: string | null;
  revoked_at: string | null;
  revoked_reason: string;
  created_at: string;
  updated_at: string;
}

export interface OrganizationOnboardingTokenStateResponse {
  status: string;
  organization_id: string;
  organization_name: string;
  subscription_id: string | null;
  subscription_active: boolean;
  has_active_token: boolean;
  token: OrganizationOnboardingTokenState | null;
  organization_seat_limit?: number | null;
  organization_seat_used?: number | null;
  organization_seat_remaining?: number | null;
}

export interface OrganizationOnboardingTokenGeneratePayload {
  max_uses?: number;
  expires_in_hours?: number;
  allowed_email_domain?: string;
  rotate?: boolean;
}

export interface OrganizationOnboardingTokenGenerateResponse {
  status: string;
  organization_id: string;
  organization_name: string;
  token: string;
  onboarding_link: string;
  token_state: OrganizationOnboardingTokenState;
}

export interface OrganizationOnboardingTokenRevokePayload {
  reason?: string;
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
  id?: string;
  evaluation_id: string;
  criteria_id: string;
  original_score: number;
  override_score: number;
  reason: string;
  overridden_at?: string;
}

// Audit Log Interface (for admin views)
export interface AuditLog {
  id: string;
  user?: string | number | null;
  user_name?: string | null;
  admin_user?: string | number | null;
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

export interface AuditEventCatalogItem {
  key: string;
  entity_type: string;
  action: string;
  description: string;
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
  user_type?: "applicant" | "internal" | "admin";
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
  reminder_before_failure_count: number;
  reminder_before_last_failure_at: string | null;
  reminder_before_next_retry_at: string | null;
  reminder_start_sent_at: string | null;
  reminder_start_failure_count: number;
  reminder_start_last_failure_at: string | null;
  reminder_start_next_retry_at: string | null;
  reminder_time_up_sent_at: string | null;
  reminder_time_up_failure_count: number;
  reminder_time_up_last_failure_at: string | null;
  reminder_time_up_next_retry_at: string | null;
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
  actor_user_type?: "applicant" | "internal" | "admin";
  action: VideoMeetingEventAction;
  scope: VideoMeetingEventScope;
  detail: string;
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface VideoMeetingReminderHealth {
  generated_at: string;
  max_retries: number;
  soon_retry_pending: number;
  soon_retry_exhausted: number;
  start_now_retry_pending: number;
  start_now_retry_exhausted: number;
  time_up_retry_pending: number;
  time_up_retry_exhausted: number;
}

export type GovernmentBranch =
  | "executive"
  | "legislative"
  | "judicial"
  | "independent"
  | "local";

export interface GovernmentPosition {
  id: string;
  organization?: string | null;
  organization_name?: string;
  title: string;
  branch: GovernmentBranch;
  institution: string;
  appointment_authority: string;
  confirmation_required: boolean;
  constitutional_basis: string;
  term_length_years: number | null;
  required_qualifications: string;
  is_vacant: boolean;
  is_public: boolean;
  current_holder: string | null;
  current_holder_name?: string;
  rubric: string | null;
  rubric_name?: string;
  created_at: string;
  updated_at: string;
}

export interface PersonnelRecord {
  id: string;
  organization?: string | null;
  organization_name?: string;
  full_name: string;
  date_of_birth: string | null;
  nationality: string;
  national_id_hash: string;
  national_id_encrypted: string;
  gender: string;
  contact_email: string;
  contact_phone: string;
  bio_summary: string;
  academic_qualifications: unknown[];
  professional_history: unknown[];
  is_active_officeholder: boolean;
  is_public: boolean;
  linked_candidate: string | null;
  linked_candidate_email?: string;
  created_at: string;
  updated_at: string;
}

export type AppointmentStatus =
  | "nominated"
  | "under_vetting"
  | "committee_review"
  | "confirmation_pending"
  | "appointed"
  | "rejected"
  | "withdrawn"
  | "serving"
  | "exited";

export interface AppointmentStageAction {
  id: string;
  appointment: string;
  stage: string | null;
  stage_name?: string;
  committee_membership?: string | null;
  committee_membership_id?: string;
  committee_name?: string;
  committee_role?: string;
  actor: string;
  actor_email?: string;
  actor_role: string;
  action: "approved" | "rejected" | "referred" | "deferred" | "noted";
  reason_note: string;
  evidence_links: string[];
  previous_status: string;
  new_status: string;
  acted_at: string;
}

export interface ApprovalStage {
  id: string;
  template: string;
  order: number;
  name: string;
  required_role: string;
  is_required: boolean;
  maps_to_status: AppointmentStatus;
  committee?: string | null;
  committee_name?: string;
}

export interface ApprovalStageTemplate {
  id: string;
  organization?: string | null;
  organization_name?: string;
  name: string;
  exercise_type: string;
  created_by: string | null;
  created_at: string;
  stages: ApprovalStage[];
}

export type AppointmentPublicationStatus = "draft" | "published" | "revoked";

export interface AppointmentPublication {
  id: string;
  appointment: string;
  status: AppointmentPublicationStatus;
  publication_reference: string;
  publication_document_hash: string;
  publication_notes: string;
  published_by: string | null;
  published_by_email?: string;
  published_at: string | null;
  revoked_by: string | null;
  revoked_by_email?: string;
  revoked_at: string | null;
  revocation_reason: string;
  created_at: string;
  updated_at: string;
}

export interface PublicAppointmentRecord {
  id: string;
  position_title: string;
  position_branch?: string;
  institution: string;
  appointment_authority?: string;
  nominee_name: string;
  nominated_by_display: string;
  nominated_by_org: string;
  nomination_date?: string;
  appointment_date: string | null;
  gazette_number: string;
  gazette_date: string | null;
  status: AppointmentStatus;
  publication_status: AppointmentPublicationStatus;
  publication_reference: string;
  published_at: string | null;
}

export interface PublicTransparencySummary {
  published_appointments: number;
  open_public_appointments: number;
  public_positions: number;
  vacant_public_positions: number;
  active_public_officeholders: number;
  last_published_at: string | null;
}

export interface PublicTransparencyPosition {
  id: string;
  title: string;
  branch: string;
  institution: string;
  appointment_authority: string;
  confirmation_required: boolean;
  constitutional_basis: string;
  term_length_years: number | null;
  is_vacant: boolean;
  current_holder_name: string | null;
}

export interface PublicTransparencyOfficeholder {
  id: string;
  full_name: string;
  gender: string;
  bio_summary: string;
  academic_qualifications: string[];
  is_active_officeholder: boolean;
}

export interface AppointmentRecord {
  id: string;
  nomination_file_id?: string;
  organization?: string | null;
  organization_name?: string;
  committee?: string | null;
  committee_name?: string;
  position: string;
  office_id?: string;
  position_title?: string;
  office_name?: string;
  nominee: string;
  nominee_name?: string;
  appointment_exercise: string | null;
  appointment_exercise_id?: string | null;
  appointment_exercise_name?: string;
  appointment_route_template_id?: string | null;
  nominated_by_user: string | null;
  nominated_by_display: string;
  nominated_by_org: string;
  nomination_date: string;
  vetting_case: string | null;
  vetting_dossier_id?: string | null;
  vetting_decision?: {
    id: string;
    recommendation_status: string;
    advisory_only: boolean;
    blocking_issues_count: number;
    warnings_count: number;
    has_override: boolean;
    updated_at: string;
  } | null;
  status: AppointmentStatus;
  nomination_file_status?: AppointmentStatus;
  committee_recommendation: string;
  final_decision_by_user: string | null;
  final_decision_by_display: string;
  appointment_date: string | null;
  gazette_number: string;
  gazette_date: string | null;
  exit_date: string | null;
  exit_reason: string;
  is_public: boolean;
  created_at: string;
  updated_at: string;
}






