"""
Applications Models
===================
Core vetting case and document models.

Academic Note:
--------------
Central models for the document vetting pipeline. Implements:
1. VettingCase: Main application/case entity
2. Document: Uploaded documents with metadata
3. VerificationResult: AI analysis results
4. ConsistencyCheck: Cross-document validation
5. InterrogationFlag: Inconsistencies requiring interview follow-up
"""

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator, FileExtensionValidator
from django.utils import timezone
from apps.users.models import User
from apps.candidates.models import CandidateEnrollment
import uuid
import os


def document_upload_path(instance, filename):
    """Generate upload path for documents."""
    ext = filename.split('.')[-1]
    filename = f"{uuid.uuid4()}.{ext}"
    return os.path.join('documents', instance.case.case_id, filename)


class VettingCase(models.Model):
    """
    Main vetting case model.
    
    Represents a complete background verification case for an applicant.
    Contains all documents, analysis results, and final decision.
    
    Academic Note:
    --------------
    State machine pattern: pending → processing → completed/failed
    Tracks entire vetting lifecycle with timestamps for performance analysis.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('document_upload', 'Document Upload'),
        ('document_analysis', 'Document Analysis'),
        ('interview_scheduled', 'Interview Scheduled'),
        ('interview_in_progress', 'Interview In Progress'),
        ('under_review', 'Under Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('on_hold', 'On Hold'),
    ]
    
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]
    
    # Identification
    case_id = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        editable=False
    )
    
    # Relationships
    applicant = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='vetting_cases',
        limit_choices_to={'user_type': 'applicant'},
        db_constraint=False,
    )

    candidate_enrollment = models.ForeignKey(
        CandidateEnrollment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='vetting_cases'
    )
    
    assigned_to = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_cases',
        limit_choices_to={'user_type__in': ['internal', 'admin']},
        db_constraint=False,
    )
    
    # Case details
    position_applied = models.CharField(max_length=200)
    department = models.CharField(max_length=100, blank=True)
    job_description = models.TextField(blank=True)
    
    # Status tracking
    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default='pending',
        db_index=True
    )
    priority = models.CharField(
        max_length=20,
        choices=PRIORITY_CHOICES,
        default='medium'
    )
    
    # Scores (calculated from AI analysis)
    overall_score = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Overall vetting score (0-100)"
    )
    
    document_authenticity_score = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    
    consistency_score = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    
    fraud_risk_score = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Higher score = higher fraud risk"
    )
    
    interview_score = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    
    # Flags and notes
    red_flags_count = models.IntegerField(default=0)
    requires_manual_review = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    internal_comments = models.TextField(blank=True)
    
    # Completion tracking
    documents_uploaded = models.BooleanField(default=False)
    documents_verified = models.BooleanField(default=False)
    interview_completed = models.BooleanField(default=False)
    
    # Final decision
    final_decision = models.CharField(
        max_length=20,
        choices=[
            ('approved', 'Approved'),
            ('rejected', 'Rejected'),
            ('pending', 'Pending'),
        ],
        default='pending'
    )
    decision_rationale = models.TextField(blank=True)
    decided_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='decided_cases',
        db_constraint=False,
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # SLA tracking
    expected_completion_date = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['case_id', 'status']),
            models.Index(fields=['applicant', 'status']),
            models.Index(fields=['assigned_to', 'status']),
            models.Index(fields=['-created_at']),
            models.Index(fields=['status', 'priority']),
        ]
        verbose_name = 'Vetting Case'
        verbose_name_plural = 'Vetting Cases'
    
    def __str__(self):
        return f"{self.case_id} - {self.applicant.get_full_name()}"
    
    def save(self, *args, **kwargs):
        # Generate case_id if not exists
        if not self.case_id:
            self.case_id = self._generate_case_id()
        
        # Auto-calculate overall score
        if self.document_authenticity_score and self.consistency_score:
            self._calculate_overall_score()
        
        # Auto-set completion date
        if self.status in ['approved', 'rejected'] and not self.completed_at:
            self.completed_at = timezone.now()
        
        super().save(*args, **kwargs)
    
    def _generate_case_id(self):
        """Generate unique case ID."""
        prefix = 'VET'
        timestamp = timezone.now().strftime('%Y%m%d')
        random_suffix = uuid.uuid4().hex[:6].upper()
        return f"{prefix}-{timestamp}-{random_suffix}"
    
    def _calculate_overall_score(self):
        """Calculate weighted overall score."""
        weights = {
            'authenticity': 0.35,
            'consistency': 0.25,
            'fraud': 0.20,
            'interview': 0.20,
        }
        
        score = 0
        total_weight = 0
        
        if self.document_authenticity_score is not None:
            score += self.document_authenticity_score * weights['authenticity']
            total_weight += weights['authenticity']
        
        if self.consistency_score is not None:
            score += self.consistency_score * weights['consistency']
            total_weight += weights['consistency']
        
        if self.fraud_risk_score is not None:
            # Invert fraud score (lower risk = higher score)
            score += (100 - self.fraud_risk_score) * weights['fraud']
            total_weight += weights['fraud']
        
        if self.interview_score is not None:
            score += self.interview_score * weights['interview']
            total_weight += weights['interview']
        
        if total_weight > 0:
            self.overall_score = score / total_weight
    
    @property
    def processing_time_days(self):
        """Calculate processing time in days."""
        if self.completed_at and self.created_at:
            delta = self.completed_at - self.created_at
            return delta.days
        return None
    
    @property
    def is_overdue(self):
        """Check if case is overdue."""
        if self.expected_completion_date and self.status not in ['approved', 'rejected']:
            return timezone.now() > self.expected_completion_date
        return False


class Document(models.Model):
    """
    Uploaded document model.
    
    Stores documents with metadata and processing status.
    Links to verification results and analysis.
    
    Academic Note:
    --------------
    Supports multiple document types commonly used in personnel vetting.
    Tracks processing pipeline stages for performance metrics.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    DOCUMENT_TYPE_CHOICES = [
        ('id_card', 'National ID Card'),
        ('passport', 'Passport'),
        ('drivers_license', 'Driver\'s License'),
        ('birth_certificate', 'Birth Certificate'),
        ('degree', 'Educational Degree/Certificate'),
        ('transcript', 'Academic Transcript'),
        ('employment_letter', 'Employment Letter'),
        ('reference_letter', 'Reference Letter'),
        ('pay_slip', 'Pay Slip'),
        ('bank_statement', 'Bank Statement'),
        ('utility_bill', 'Utility Bill'),
        ('other', 'Other'),
    ]
    
    STATUS_CHOICES = [
        ('uploaded', 'Uploaded'),
        ('queued', 'Queued for Processing'),
        ('processing', 'Processing'),
        ('verified', 'Verified'),
        ('failed', 'Verification Failed'),
        ('flagged', 'Flagged for Review'),
    ]
    
    # Relationships
    case = models.ForeignKey(
        VettingCase,
        on_delete=models.CASCADE,
        related_name='documents'
    )
    
    # Document information
    document_type = models.CharField(
        max_length=50,
        choices=DOCUMENT_TYPE_CHOICES,
        db_index=True
    )
    
    file = models.FileField(
        upload_to=document_upload_path,
        validators=[
            FileExtensionValidator(
                allowed_extensions=['pdf', 'jpg', 'jpeg', 'png', 'tiff']
            )
        ]
    )
    
    original_filename = models.CharField(max_length=255)
    file_size = models.IntegerField(help_text="File size in bytes")
    mime_type = models.CharField(max_length=100)
    
    # Processing status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='uploaded',
        db_index=True
    )
    
    # Processing metadata
    ocr_completed = models.BooleanField(default=False)
    authenticity_check_completed = models.BooleanField(default=False)
    fraud_check_completed = models.BooleanField(default=False)
    
    # Error tracking
    processing_error = models.TextField(blank=True)
    retry_count = models.IntegerField(default=0)
    
    # Extracted information (from OCR)
    extracted_text = models.TextField(blank=True)
    extracted_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Structured data extracted from document"
    )
    
    # Timestamps
    uploaded_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['case', 'uploaded_at']
        indexes = [
            models.Index(fields=['case', 'document_type']),
            models.Index(fields=['status']),
            models.Index(fields=['-uploaded_at']),
        ]
        verbose_name = 'Document'
        verbose_name_plural = 'Documents'
    
    def __str__(self):
        return f"{self.get_document_type_display()} - {self.case.case_id}"
    
    def save(self, *args, **kwargs):
        # Extract metadata on first save
        if not self.pk and self.file:
            self.file_size = self.file.size
            self.original_filename = self.file.name
        
        super().save(*args, **kwargs)
    
    @property
    def file_url(self):
        """Get URL for file access."""
        if self.file:
            return self.file.url
        return None


class VerificationResult(models.Model):
    """
    AI verification results for a document.
    
    Stores detailed results from AI/ML analysis including:
    - OCR text extraction
    - Authenticity detection
    - Fraud risk assessment
    
    Academic Note:
    --------------
    Central model for storing ML model predictions and confidence scores.
    Used for model performance evaluation and result auditing.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Relationship
    document = models.OneToOneField(
        Document,
        on_delete=models.CASCADE,
        related_name='verification_result'
    )
    
    # OCR Results
    ocr_text = models.TextField(blank=True)
    ocr_confidence = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    ocr_language = models.CharField(max_length=10, default='en')
    
    # Authenticity Detection (CNN model)
    authenticity_score = models.FloatField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Likelihood document is authentic (0-100)"
    )
    authenticity_confidence = models.FloatField(
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    is_authentic = models.BooleanField()
    
    # Authenticity sub-checks
    metadata_check_passed = models.BooleanField(default=False)
    visual_check_passed = models.BooleanField(default=False)
    tampering_detected = models.BooleanField(default=False)
    
    # Fraud Detection (ML classifier)
    fraud_risk_score = models.FloatField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Probability of fraud (0-100)"
    )
    fraud_prediction = models.CharField(
        max_length=20,
        choices=[
            ('legitimate', 'Legitimate'),
            ('suspicious', 'Suspicious'),
            ('fraudulent', 'Fraudulent'),
        ]
    )
    
    # Fraud indicators
    fraud_indicators = models.JSONField(
        default=list,
        help_text="List of detected fraud indicators"
    )
    
    # Detailed results (full model output)
    detailed_results = models.JSONField(
        default=dict,
        help_text="Complete analysis results from AI models"
    )
    
    # Model versions (for tracking)
    ocr_model_version = models.CharField(max_length=50, blank=True)
    authenticity_model_version = models.CharField(max_length=50, blank=True)
    fraud_model_version = models.CharField(max_length=50, blank=True)
    
    # Timing
    created_at = models.DateTimeField(auto_now_add=True)
    processing_time_seconds = models.FloatField(
        null=True,
        blank=True,
        help_text="Time taken for analysis"
    )
    
    class Meta:
        verbose_name = 'Verification Result'
        verbose_name_plural = 'Verification Results'

    def clean(self):
        from django.core.exceptions import ValidationError as DjangoValidationError
        errors = {}
        # is_authentic should align with authenticity_score
        if self.is_authentic and self.authenticity_score is not None and self.authenticity_score < 50:
            errors['authenticity_score'] = (
                "is_authentic=True is inconsistent with authenticity_score < 50."
            )
        if not self.is_authentic and self.authenticity_score is not None and self.authenticity_score > 90:
            errors['authenticity_score'] = (
                "is_authentic=False is inconsistent with authenticity_score > 90."
            )
        # fraud_prediction should align with fraud_risk_score
        if self.fraud_prediction == 'fraudulent' and self.fraud_risk_score is not None and self.fraud_risk_score < 30:
            errors['fraud_risk_score'] = (
                "fraud_prediction='fraudulent' is inconsistent with fraud_risk_score < 30."
            )
        if self.fraud_prediction == 'legitimate' and self.fraud_risk_score is not None and self.fraud_risk_score > 70:
            errors['fraud_risk_score'] = (
                "fraud_prediction='legitimate' is inconsistent with fraud_risk_score > 70."
            )
        if errors:
            raise DjangoValidationError(errors)

    def __str__(self):
        return f"Results: {self.document}"
    
    @property
    def requires_review(self):
        """Determine if results require manual review."""
        return (
            self.authenticity_score < 70 or
            self.fraud_risk_score > 50 or
            not self.is_authentic or
            self.fraud_prediction in ['suspicious', 'fraudulent']
        )


class ConsistencyCheck(models.Model):
    """
    Cross-document consistency validation.
    
    Compares information across multiple documents to detect
    inconsistencies (e.g., different names, dates, IDs).
    
    Academic Note:
    --------------
    Implements entity resolution and consistency checking algorithms.
    Key for detecting forged documents with conflicting information.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    SEVERITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]
    
    # Relationship
    case = models.ForeignKey(
        VettingCase,
        on_delete=models.CASCADE,
        related_name='consistency_checks'
    )
    
    # Check details
    field_name = models.CharField(
        max_length=100,
        help_text="Field being checked (e.g., 'name', 'date_of_birth')"
    )
    
    documents_compared = models.ManyToManyField(
        Document,
        related_name='consistency_checks'
    )
    
    # Results
    is_consistent = models.BooleanField()
    severity = models.CharField(
        max_length=20,
        choices=SEVERITY_CHOICES
    )
    
    discrepancy_description = models.TextField()
    conflicting_values = models.JSONField(
        default=list,
        help_text="List of conflicting values found"
    )
    
    # Resolution
    resolved = models.BooleanField(default=False)
    resolution_notes = models.TextField(blank=True)
    resolved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resolved_checks',
        db_constraint=False,
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-severity', 'created_at']
        indexes = [
            models.Index(fields=['case', 'is_consistent']),
            models.Index(fields=['severity']),
        ]
        verbose_name = 'Consistency Check'
        verbose_name_plural = 'Consistency Checks'
    
    def __str__(self):
        status = "Consistent" if self.is_consistent else "Inconsistent"
        return f"{self.field_name} - {status}"


class InterrogationFlag(models.Model):
    """
    Flags requiring clarification in interview.
    
    Generated from document analysis inconsistencies or suspicious findings.
    Used to generate interview questions dynamically.
    
    Academic Note:
    --------------
    Bridge between document analysis and interview components.
    Enables adaptive questioning based on detected issues.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    FLAG_TYPE_CHOICES = [
        ('consistency_mismatch', 'Consistency Mismatch'),
        ('missing_information', 'Missing Information'),
        ('suspicious_document', 'Suspicious Document'),
        ('timeline_conflict', 'Timeline Conflict'),
        ('credential_issue', 'Credential Issue'),
        ('employment_gap', 'Employment Gap'),
        ('reference_discrepancy', 'Reference Discrepancy'),
        ('authenticity_concern', 'Authenticity Concern'),
        ('fraud_indicator', 'Fraud Indicator'),
        ('other', 'Other'),
    ]
    
    SEVERITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('addressed', 'Addressed in Interview'),
        ('resolved', 'Resolved'),
        ('unresolved', 'Unresolved'),
        ('dismissed', 'Dismissed'),
    ]
    
    # Relationships
    case = models.ForeignKey(
        VettingCase,
        on_delete=models.CASCADE,
        related_name='interrogation_flags'
    )
    
    related_documents = models.ManyToManyField(
        Document,
        related_name='flags',
        blank=True
    )
    
    related_consistency_check = models.ForeignKey(
        ConsistencyCheck,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='generated_flags'
    )
    
    # Flag details
    flag_type = models.CharField(
        max_length=50,
        choices=FLAG_TYPE_CHOICES,
        db_index=True
    )
    
    severity = models.CharField(
        max_length=20,
        choices=SEVERITY_CHOICES,
        db_index=True
    )
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    
    # Context and description
    title = models.CharField(max_length=200)
    description = models.TextField(
        help_text="Detailed description of the issue"
    )
    
    data_point = models.CharField(
        max_length=200,
        blank=True,
        help_text="Specific data point causing the flag"
    )
    
    evidence = models.JSONField(
        default=dict,
        help_text="Supporting evidence for the flag"
    )
    
    # Interview integration
    suggested_questions = models.JSONField(
        default=list,
        help_text="Suggested interview questions to address this flag"
    )
    
    # Resolution
    resolution_summary = models.TextField(blank=True)
    resolution_confidence = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    
    resolved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resolved_flags',
        db_constraint=False,
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    addressed_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-severity', 'created_at']
        indexes = [
            models.Index(fields=['case', 'status']),
            models.Index(fields=['severity', 'status']),
            models.Index(fields=['flag_type']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['case', 'title'],
                name='uniq_flag_case_title',
            )
        ]
        verbose_name = 'Interrogation Flag'
        verbose_name_plural = 'Interrogation Flags'

    def __str__(self):
        return f"{self.get_flag_type_display()} - {self.case.case_id}"

    # Valid state machine transitions
    _VALID_TRANSITIONS: dict[str, set[str]] = {
        'pending':    {'addressed', 'resolved', 'unresolved', 'dismissed'},
        'addressed':  {'resolved', 'unresolved', 'dismissed'},
        'resolved':   {'unresolved'},          # allow re-opening
        'unresolved': {'resolved', 'dismissed'},
        'dismissed':  set(),                   # terminal
    }

    def _transition_to(self, new_status: str) -> None:
        allowed = self._VALID_TRANSITIONS.get(self.status, set())
        if new_status not in allowed:
            raise ValueError(
                f"Cannot transition flag from '{self.status}' to '{new_status}'. "
                f"Allowed: {sorted(allowed) or 'none (terminal state)'}."
            )
        self.status = new_status

    def mark_addressed(self) -> None:
        """Mark flag as addressed in interview."""
        self._transition_to('addressed')
        self.addressed_at = timezone.now()
        self.save(update_fields=['status', 'addressed_at'])

    def mark_resolved(self, summary: str, confidence: float, resolved_by=None) -> None:
        """Mark flag as resolved."""
        self._transition_to('resolved')
        self.resolved_at = timezone.now()
        self.resolution_summary = summary
        self.resolution_confidence = confidence
        if resolved_by is not None:
            self.resolved_by = resolved_by
        self.save(update_fields=['status', 'resolved_at', 'resolution_summary', 'resolution_confidence', 'resolved_by'])

    def mark_unresolved(self, summary: str) -> None:
        """Mark flag as unresolved (re-open)."""
        self._transition_to('unresolved')
        self.resolution_summary = summary
        self.save(update_fields=['status', 'resolution_summary'])


class VerificationSource(models.Model):
    """
    Configured external evidence source for inter-agency verification.

    This model stores source metadata only. It does not imply autonomous decision authority.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    SOURCE_CATEGORY_CHOICES = [
        ("national_identity", "National Identity Registry"),
        ("civil_service", "Civil Service / Employment Registry"),
        ("academic_credentials", "Academic Credential Registry"),
        ("sanctions", "Sanctions / Disciplinary Registry"),
        ("prior_appointments", "Prior Appointment Registry"),
        ("organization_legitimacy", "Organization Legitimacy Registry"),
        ("other", "Other"),
    ]

    INTEGRATION_MODE_CHOICES = [
        ("manual", "Manual Upload / Officer Entry"),
        ("mock", "Mock Provider"),
        ("api", "API Integration"),
        ("batch", "Batch Import"),
    ]

    key = models.CharField(max_length=80, unique=True, db_index=True)
    name = models.CharField(max_length=200)
    source_category = models.CharField(max_length=40, choices=SOURCE_CATEGORY_CHOICES, default="other", db_index=True)
    integration_mode = models.CharField(max_length=20, choices=INTEGRATION_MODE_CHOICES, default="manual")
    advisory_only = models.BooleanField(
        default=True,
        help_text="External source outputs remain advisory evidence and never final authority.",
    )
    is_active = models.BooleanField(default=True, db_index=True)
    description = models.TextField(blank=True)
    configuration = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_verification_sources",
        db_constraint=False,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["source_category", "is_active"]),
        ]
        verbose_name = "Verification Source"
        verbose_name_plural = "Verification Sources"

    def __str__(self):
        return f"{self.name} ({self.key})"


class VerificationRequest(models.Model):
    """
    Verification request sent to an external/inter-agency source.

    Tracks request lifecycle and idempotency for retried submissions.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("submitted", "Submitted"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
        ("failed", "Failed"),
        ("unavailable", "Unavailable"),
        ("cancelled", "Cancelled"),
    ]

    case = models.ForeignKey(
        VettingCase,
        on_delete=models.CASCADE,
        related_name="verification_requests",
    )
    source = models.ForeignKey(
        VerificationSource,
        on_delete=models.PROTECT,
        related_name="verification_requests",
    )
    requested_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="verification_requests",
        db_constraint=False,
    )

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending", db_index=True)
    purpose = models.CharField(max_length=100, default="vetting_evidence", blank=True)
    idempotency_key = models.CharField(max_length=120, blank=True, db_index=True)
    subject_identifiers = models.JSONField(default=dict, blank=True)
    request_payload = models.JSONField(default=dict, blank=True)
    external_reference = models.CharField(max_length=255, blank=True, db_index=True)
    error_code = models.CharField(max_length=100, blank=True)
    error_message = models.TextField(blank=True)

    requested_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    last_polled_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-requested_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["case", "source", "idempotency_key"],
                condition=models.Q(idempotency_key__gt=""),
                name="uniq_verif_req_case_source_idempotency",
            ),
        ]
        indexes = [
            models.Index(fields=["case", "status"]),
            models.Index(fields=["source", "status"]),
        ]
        verbose_name = "Verification Request"
        verbose_name_plural = "Verification Requests"

    def __str__(self):
        return f"{self.case.case_id}::{self.source.key}::{self.status}"


class ExternalVerificationResult(models.Model):
    """
    Normalized result from an external verification source.

    Evidence is advisory-only and feeds human-centric rubric/decision support.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    RESULT_STATUS_CHOICES = [
        ("verified", "Verified"),
        ("mismatch", "Mismatch"),
        ("not_found", "Not Found"),
        ("inconclusive", "Inconclusive"),
        ("error", "Error"),
        ("unavailable", "Unavailable"),
    ]

    RECOMMENDATION_CHOICES = [
        ("clear", "Clear"),
        ("review", "Manual Review"),
        ("escalate", "Escalate"),
        ("reject", "Reject"),
        ("unavailable", "Unavailable"),
    ]

    case = models.ForeignKey(
        VettingCase,
        on_delete=models.CASCADE,
        related_name="external_verification_results",
    )
    source = models.ForeignKey(
        VerificationSource,
        on_delete=models.PROTECT,
        related_name="external_verification_results",
    )
    verification_request = models.OneToOneField(
        VerificationRequest,
        on_delete=models.CASCADE,
        related_name="external_result",
    )

    result_status = models.CharField(max_length=20, choices=RESULT_STATUS_CHOICES, db_index=True)
    recommendation = models.CharField(
        max_length=20,
        choices=RECOMMENDATION_CHOICES,
        default="review",
        help_text="Advisory recommendation only; final decision remains human.",
    )
    confidence_score = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    advisory_flags = models.JSONField(default=list, blank=True)
    evidence_summary = models.JSONField(default=dict, blank=True)
    normalized_evidence = models.JSONField(default=dict, blank=True)
    raw_payload = models.JSONField(default=dict, blank=True)
    raw_payload_redacted = models.BooleanField(
        default=True,
        help_text="True when payload is already redacted/sanitized for internal storage.",
    )
    provider_reference = models.CharField(max_length=255, blank=True)
    received_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-received_at"]
        indexes = [
            models.Index(fields=["case", "result_status"]),
            models.Index(fields=["source", "result_status"]),
        ]
        verbose_name = "External Verification Result"
        verbose_name_plural = "External Verification Results"

    def __str__(self):
        return f"{self.case.case_id}::{self.source.key}::{self.result_status}"

