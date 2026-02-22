"""
Rubrics Models
==============
Dynamic vetting rubric and evaluation models.

Academic Note:
--------------
Implements configurable scoring system allowing HR managers to:
1. Define custom evaluation criteria
2. Assign weights to different components
3. Set thresholds for pass/fail
4. Override AI decisions when necessary

This flexibility is crucial for adapting to different:
- Job positions (senior vs. junior roles)
- Departments (technical vs. non-technical)
- Risk levels (high-security vs. standard positions)
"""

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from apps.authentication.models import User
from apps.applications.models import VettingCase


class VettingRubric(models.Model):
    """
    Main rubric definition model.
    
    Defines evaluation criteria and weights for vetting process.
    Can be reused across multiple cases or created per-case.
    
    Academic Note:
    --------------
    Multi-criteria decision analysis (MCDA) framework.
    Weights must sum to 100 for proper normalization.
    """
    
    RUBRIC_TYPE_CHOICES = [
        ('general', 'General Purpose'),
        ('technical', 'Technical Position'),
        ('executive', 'Executive Level'),
        ('sensitive', 'High-Security Position'),
        ('custom', 'Custom'),
    ]
    
    # Identification
    name = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True)
    rubric_type = models.CharField(
        max_length=20,
        choices=RUBRIC_TYPE_CHOICES,
        default='general'
    )
    
    # Component weights (must sum to 100)
    document_authenticity_weight = models.IntegerField(
        default=25,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Weight for document authenticity (0-100)"
    )
    
    consistency_weight = models.IntegerField(
        default=20,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Weight for cross-document consistency"
    )
    
    fraud_detection_weight = models.IntegerField(
        default=20,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Weight for fraud risk assessment"
    )
    
    interview_weight = models.IntegerField(
        default=25,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Weight for interview performance"
    )
    
    manual_review_weight = models.IntegerField(
        default=10,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Weight for manual HR review"
    )
    
    # Thresholds
    passing_score = models.IntegerField(
        default=70,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Minimum score to pass vetting"
    )
    
    auto_approve_threshold = models.IntegerField(
        default=90,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Score for automatic approval without review"
    )
    
    auto_reject_threshold = models.IntegerField(
        default=40,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Score for automatic rejection"
    )
    
    # Requirements
    minimum_document_score = models.IntegerField(
        default=60,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Minimum acceptable document authenticity score"
    )
    
    maximum_fraud_score = models.IntegerField(
        default=50,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Maximum acceptable fraud risk score"
    )
    
    require_interview = models.BooleanField(
        default=True,
        help_text="Is interview mandatory?"
    )
    
    # Red flag handling
    critical_flags_auto_fail = models.BooleanField(
        default=True,
        help_text="Automatically fail if critical flags detected"
    )
    
    max_unresolved_flags = models.IntegerField(
        default=2,
        help_text="Maximum unresolved flags before manual review required"
    )
    
    # Metadata
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)
    
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_rubrics'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['is_active', 'is_default']),
        ]
        verbose_name = 'Vetting Rubric'
        verbose_name_plural = 'Vetting Rubrics'
    
    def __str__(self):
        return self.name
    
    def clean(self):
        """Validate that weights sum to 100."""
        from django.core.exceptions import ValidationError
        
        total_weight = (
            self.document_authenticity_weight +
            self.consistency_weight +
            self.fraud_detection_weight +
            self.interview_weight +
            self.manual_review_weight
        )
        
        if total_weight != 100:
            raise ValidationError(
                f'Weights must sum to 100. Current sum: {total_weight}'
            )
    
    def save(self, *args, **kwargs):
        # Ensure only one default rubric
        if self.is_default:
            VettingRubric.objects.filter(is_default=True).update(is_default=False)
        
        super().save(*args, **kwargs)


class RubricCriteria(models.Model):
    """
    Individual evaluation criterion within a rubric.
    
    Allows fine-grained control over specific aspects of evaluation.
    
    Academic Note:
    --------------
    Enables hierarchical rubric structure with sub-criteria.
    Each criterion can have its own weight and scoring method.
    """
    
    CRITERIA_TYPE_CHOICES = [
        ('document', 'Document Quality'),
        ('consistency', 'Data Consistency'),
        ('interview', 'Interview Performance'),
        ('behavioral', 'Behavioral Assessment'),
        ('technical', 'Technical Competency'),
        ('custom', 'Custom Criterion'),
    ]
    
    SCORING_METHOD_CHOICES = [
        ('ai_score', 'AI-Generated Score'),
        ('manual_rating', 'Manual Rating'),
        ('binary', 'Pass/Fail'),
        ('calculated', 'Calculated from Sub-Criteria'),
    ]
    
    # Relationship
    rubric = models.ForeignKey(
        VettingRubric,
        on_delete=models.CASCADE,
        related_name='criteria'
    )
    
    # Criteria details
    name = models.CharField(max_length=200)
    description = models.TextField()
    criteria_type = models.CharField(
        max_length=20,
        choices=CRITERIA_TYPE_CHOICES
    )
    
    # Scoring
    scoring_method = models.CharField(
        max_length=20,
        choices=SCORING_METHOD_CHOICES,
        default='ai_score'
    )
    
    weight = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Weight within parent rubric or category"
    )
    
    # Thresholds
    minimum_score = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Minimum required score for this criterion"
    )
    
    is_mandatory = models.BooleanField(
        default=False,
        help_text="Must pass this criterion to pass overall"
    )
    
    # Evaluation guidance
    evaluation_guidelines = models.TextField(
        blank=True,
        help_text="Instructions for manual evaluation"
    )
    
    # Order
    display_order = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['rubric', 'display_order']
        unique_together = ['rubric', 'name']
        verbose_name = 'Rubric Criterion'
        verbose_name_plural = 'Rubric Criteria'
    
    def __str__(self):
        return f"{self.rubric.name} - {self.name}"


class RubricEvaluation(models.Model):
    """
    Evaluation results for a specific case using a rubric.
    
    Stores calculated scores and individual criterion results.
    
    Academic Note:
    --------------
    Links rubric framework to actual case evaluation.
    Enables retrospective analysis of rubric effectiveness.
    """
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('requires_review', 'Requires Manual Review'),
    ]
    
    DECISION_CHOICES = [
        ('auto_approved', 'Automatically Approved'),
        ('auto_rejected', 'Automatically Rejected'),
        ('manual_approved', 'Manually Approved'),
        ('manual_rejected', 'Manually Rejected'),
        ('pending', 'Pending Decision'),
    ]
    
    # Relationships
    case = models.OneToOneField(
        VettingCase,
        on_delete=models.CASCADE,
        related_name='rubric_evaluation'
    )
    
    rubric = models.ForeignKey(
        VettingRubric,
        on_delete=models.PROTECT,
        related_name='evaluations'
    )
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    
    # Component scores (raw from AI)
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
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    
    interview_score = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    
    manual_review_score = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    
    # Weighted scores (after applying rubric weights)
    weighted_document_score = models.FloatField(null=True, blank=True)
    weighted_consistency_score = models.FloatField(null=True, blank=True)
    weighted_fraud_score = models.FloatField(null=True, blank=True)
    weighted_interview_score = models.FloatField(null=True, blank=True)
    weighted_manual_score = models.FloatField(null=True, blank=True)
    
    # Final score
    total_weighted_score = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    
    # Decision
    passes_threshold = models.BooleanField(null=True)
    final_decision = models.CharField(
        max_length=20,
        choices=DECISION_CHOICES,
        default='pending'
    )
    
    # Flags and concerns
    critical_flags_present = models.BooleanField(default=False)
    unresolved_flags_count = models.IntegerField(default=0)
    requires_manual_review = models.BooleanField(default=False)
    review_reasons = models.JSONField(
        default=list,
        help_text="Reasons requiring manual review"
    )
    
    # Detailed results
    criterion_scores = models.JSONField(
        default=dict,
        help_text="Individual criterion scores"
    )
    
    evaluation_summary = models.TextField(blank=True)
    recommendations = models.TextField(blank=True)
    
    # Metadata
    evaluated_at = models.DateTimeField(null=True, blank=True)
    evaluated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='conducted_evaluations'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Rubric Evaluation'
        verbose_name_plural = 'Rubric Evaluations'
    
    def __str__(self):
        return f"Evaluation: {self.case.case_id} using {self.rubric.name}"
    
    def calculate_weighted_scores(self):
        """Calculate weighted scores based on rubric weights."""
        if self.document_authenticity_score is not None:
            self.weighted_document_score = (
                self.document_authenticity_score *
                self.rubric.document_authenticity_weight / 100
            )
        
        if self.consistency_score is not None:
            self.weighted_consistency_score = (
                self.consistency_score *
                self.rubric.consistency_weight / 100
            )
        
        if self.fraud_risk_score is not None:
            # Invert fraud score (lower risk = higher score)
            inverted_fraud = 100 - self.fraud_risk_score
            self.weighted_fraud_score = (
                inverted_fraud *
                self.rubric.fraud_detection_weight / 100
            )
        
        if self.interview_score is not None:
            self.weighted_interview_score = (
                self.interview_score *
                self.rubric.interview_weight / 100
            )
        
        if self.manual_review_score is not None:
            self.weighted_manual_score = (
                self.manual_review_score *
                self.rubric.manual_review_weight / 100
            )
    
    def calculate_total_score(self):
        """Calculate total weighted score."""
        self.calculate_weighted_scores()
        
        scores = [
            self.weighted_document_score,
            self.weighted_consistency_score,
            self.weighted_fraud_score,
            self.weighted_interview_score,
            self.weighted_manual_score,
        ]
        
        # Sum only non-None scores
        valid_scores = [s for s in scores if s is not None]
        
        if valid_scores:
            self.total_weighted_score = sum(valid_scores)
            
            # Determine if passes threshold
            self.passes_threshold = (
                self.total_weighted_score >= self.rubric.passing_score
            )
            
            # Auto-decision logic
            if not self.requires_manual_review:
                if self.total_weighted_score >= self.rubric.auto_approve_threshold:
                    self.final_decision = 'auto_approved'
                elif self.total_weighted_score <= self.rubric.auto_reject_threshold:
                    self.final_decision = 'auto_rejected'
                else:
                    self.final_decision = 'pending'
                    self.requires_manual_review = True
                    self.review_reasons.append('Score in manual review range')
    
    def check_mandatory_requirements(self):
        """Check if mandatory requirements are met."""
        # Check minimum document score
        if self.document_authenticity_score is not None:
            if self.document_authenticity_score < self.rubric.minimum_document_score:
                self.requires_manual_review = True
                self.review_reasons.append(
                    f'Document score below minimum ({self.rubric.minimum_document_score})'
                )
        
        # Check maximum fraud score
        if self.fraud_risk_score is not None:
            if self.fraud_risk_score > self.rubric.maximum_fraud_score:
                self.requires_manual_review = True
                self.review_reasons.append(
                    f'Fraud risk above maximum ({self.rubric.maximum_fraud_score})'
                )
        
        # Check critical flags
        if self.critical_flags_present and self.rubric.critical_flags_auto_fail:
            self.final_decision = 'auto_rejected'
            self.review_reasons.append('Critical flags detected')
        
        # Check unresolved flags
        if self.unresolved_flags_count > self.rubric.max_unresolved_flags:
            self.requires_manual_review = True
            self.review_reasons.append(
                f'Too many unresolved flags ({self.unresolved_flags_count})'
            )
    
    def save(self, *args, **kwargs):
        # Auto-calculate scores before saving
        if self.document_authenticity_score or self.consistency_score:
            self.calculate_total_score()
            self.check_mandatory_requirements()
        
        super().save(*args, **kwargs)


class CriteriaOverride(models.Model):
    """
    Manual override of AI-generated scores.
    
    Allows HR managers to adjust scores with justification.
    Important for bias mitigation and human oversight.
    
    Academic Note:
    --------------
    Tracks human-in-the-loop interventions for:
    1. Bias analysis (which AI decisions get overridden?)
    2. Model improvement (ground truth labeling)
    3. Audit trail (accountability and transparency)
    """
    
    # Relationships
    evaluation = models.ForeignKey(
        RubricEvaluation,
        on_delete=models.CASCADE,
        related_name='overrides'
    )
    
    criteria = models.ForeignKey(
        RubricCriteria,
        on_delete=models.CASCADE,
        related_name='overrides'
    )
    
    # Override details
    original_score = models.FloatField(
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    
    overridden_score = models.FloatField(
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    
    justification = models.TextField(
        help_text="Explanation for the override"
    )
    
    # Metadata
    overridden_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='score_overrides'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Criteria Override'
        verbose_name_plural = 'Criteria Overrides'
    
    def __str__(self):
        return f"Override: {self.criteria.name} ({self.original_score} → {self.overridden_score})"
    
    @property
    def score_change(self):
        """Calculate score change."""
        return self.overridden_score - self.original_score
