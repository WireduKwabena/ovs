"""
Rubrics Models
==============
Dynamic vetting rubric and evaluation models.

Academic Note:
--------------
Implements configurable scoring system allowing internal reviewers to:
1. Define custom evaluation criteria
2. Assign weights to different components
3. Set thresholds for pass/fail
4. Override AI decisions when necessary

This flexibility is crucial for adapting to different:
- Job positions (senior vs. junior roles)
- Departments (technical vs. non-technical)
- Risk levels (high-security vs. standard positions)
"""

import uuid

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from apps.users.models import User
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
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

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
        help_text="Weight for manual reviewer assessment"
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
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

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
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

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

    COMPONENT_SPECS = (
        {
            "key": "document_authenticity",
            "raw_field": "document_authenticity_score",
            "weighted_field": "weighted_document_score",
            "rubric_weight_field": "document_authenticity_weight",
            "invert": False,
            "label": "Document authenticity",
        },
        {
            "key": "consistency",
            "raw_field": "consistency_score",
            "weighted_field": "weighted_consistency_score",
            "rubric_weight_field": "consistency_weight",
            "invert": False,
            "label": "Cross-document consistency",
        },
        {
            "key": "fraud_detection",
            "raw_field": "fraud_risk_score",
            "weighted_field": "weighted_fraud_score",
            "rubric_weight_field": "fraud_detection_weight",
            "invert": True,
            "label": "Fraud risk (inverted)",
        },
        {
            "key": "interview",
            "raw_field": "interview_score",
            "weighted_field": "weighted_interview_score",
            "rubric_weight_field": "interview_weight",
            "invert": False,
            "label": "Interview",
        },
        {
            "key": "manual_review",
            "raw_field": "manual_review_score",
            "weighted_field": "weighted_manual_score",
            "rubric_weight_field": "manual_review_weight",
            "invert": False,
            "label": "Manual review",
        },
    )
    
    def __str__(self):
        return f"Evaluation: {self.case.case_id} using {self.rubric.name}"

    def _add_review_reason(self, reason: str) -> None:
        """Append reason once to maintain concise traceability."""
        if not reason:
            return
        reasons = list(self.review_reasons or [])
        if reason not in reasons:
            reasons.append(reason)
        self.review_reasons = reasons

    def get_component_breakdown(self):
        """Return transparent component-level scoring details."""
        components = {}
        available_weight = 0
        weighted_total = 0.0

        for spec in self.COMPONENT_SPECS:
            raw_score = getattr(self, spec["raw_field"])
            rubric_weight = getattr(self.rubric, spec["rubric_weight_field"])
            adjusted_score = None
            weighted_score = getattr(self, spec["weighted_field"])

            if raw_score is not None:
                adjusted_score = 100 - raw_score if spec["invert"] else raw_score
                available_weight += rubric_weight
                weighted_total += weighted_score or 0.0

            components[spec["key"]] = {
                "label": spec["label"],
                "raw_field": spec["raw_field"],
                "weighted_field": spec["weighted_field"],
                "rubric_weight_field": spec["rubric_weight_field"],
                "raw_score": raw_score,
                "adjusted_score": adjusted_score,
                "weight": rubric_weight,
                "weighted_score": weighted_score,
                "missing": raw_score is None,
            }

        normalized_score = None
        if available_weight > 0:
            normalized_score = (weighted_total * 100) / available_weight

        return {
            "components": components,
            "available_weight": available_weight,
            "weighted_total": weighted_total,
            "normalized_score": normalized_score,
        }
    
    def calculate_weighted_scores(self):
        """Calculate weighted scores based on rubric weights."""
        for spec in self.COMPONENT_SPECS:
            raw_score = getattr(self, spec["raw_field"])
            weighted_field = spec["weighted_field"]
            if raw_score is None:
                setattr(self, weighted_field, None)
                continue

            rubric_weight = getattr(self.rubric, spec["rubric_weight_field"])
            adjusted_score = 100 - raw_score if spec["invert"] else raw_score
            setattr(self, weighted_field, adjusted_score * rubric_weight / 100)
    
    def calculate_total_score(self):
        """Calculate total weighted score."""
        self.calculate_weighted_scores()

        scores = [getattr(self, spec["weighted_field"]) for spec in self.COMPONENT_SPECS]
        valid_scores = [score for score in scores if score is not None]

        if not valid_scores:
            self.total_weighted_score = None
            self.passes_threshold = None
            if self.final_decision in {"auto_approved", "auto_rejected"}:
                self.final_decision = "pending"
            return

        self.total_weighted_score = sum(valid_scores)
        self.passes_threshold = self.total_weighted_score >= self.rubric.passing_score

        # Preserve explicit manual decisions and hard auto-fail decisions.
        if self.final_decision in {"manual_approved", "manual_rejected"}:
            return
        if self.final_decision == "auto_rejected" and self.critical_flags_present and self.rubric.critical_flags_auto_fail:
            return
        if self.requires_manual_review:
            self.final_decision = "pending"
            return

        if self.total_weighted_score >= self.rubric.auto_approve_threshold:
            self.final_decision = "auto_approved"
        elif self.total_weighted_score <= self.rubric.auto_reject_threshold:
            self.final_decision = "auto_rejected"
        else:
            self.final_decision = "pending"
            self.requires_manual_review = True
            self._add_review_reason("Score in manual review range")
    
    def check_mandatory_requirements(self):
        """Check if mandatory requirements are met."""
        # Check minimum document score
        if self.document_authenticity_score is not None:
            if self.document_authenticity_score < self.rubric.minimum_document_score:
                self.requires_manual_review = True
                self._add_review_reason(
                    f'Document score below minimum ({self.rubric.minimum_document_score})'
                )
        
        # Check maximum fraud score
        if self.fraud_risk_score is not None:
            if self.fraud_risk_score > self.rubric.maximum_fraud_score:
                self.requires_manual_review = True
                self._add_review_reason(
                    f'Fraud risk above maximum ({self.rubric.maximum_fraud_score})'
                )

        if self.rubric.require_interview and self.interview_score is None:
            self.requires_manual_review = True
            self._add_review_reason('Interview score missing for interview-required rubric')
        
        # Check critical flags
        if self.critical_flags_present and self.rubric.critical_flags_auto_fail:
            self.final_decision = 'auto_rejected'
            self.passes_threshold = False
            self.requires_manual_review = True
            self._add_review_reason('Critical flags detected')
        
        # Check unresolved flags
        if self.unresolved_flags_count > self.rubric.max_unresolved_flags:
            self.requires_manual_review = True
            self._add_review_reason(
                f'Too many unresolved flags ({self.unresolved_flags_count})'
            )
    
    def save(self, *args, **kwargs):
        update_fields = kwargs.get("update_fields")
        recalc_trigger_fields = {
            "document_authenticity_score",
            "consistency_score",
            "fraud_risk_score",
            "interview_score",
            "manual_review_score",
            "critical_flags_present",
            "unresolved_flags_count",
            "rubric_id",
            "rubric",
        }

        has_any_input_score = any(
            getattr(self, spec["raw_field"]) is not None
            for spec in self.COMPONENT_SPECS
        )
        should_recalculate = (
            has_any_input_score
            or bool(self.critical_flags_present)
            or int(self.unresolved_flags_count or 0) > 0
            or bool(getattr(self.rubric, "require_interview", False))
        )
        if update_fields is not None:
            normalized_update_fields = set(update_fields)
            should_recalculate = bool(recalc_trigger_fields.intersection(normalized_update_fields))

        # Auto-calculate scores only when scoring inputs change.
        if should_recalculate:
            self.check_mandatory_requirements()
            self.calculate_total_score()
        
        super().save(*args, **kwargs)


class VettingDecisionRecommendation(models.Model):
    """
    Advisory recommendation generated from rubric + policy/evidence signals.

    This sits above rubric scoring and remains decision-support only.
    Human decision-makers retain final authority.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    RECOMMENDATION_CHOICES = [
        ("recommend_approve", "Recommend Approve"),
        ("recommend_reject", "Recommend Reject"),
        ("recommend_manual_review", "Recommend Manual Review"),
    ]

    case = models.ForeignKey(
        VettingCase,
        on_delete=models.CASCADE,
        related_name="decision_recommendations",
    )
    rubric_evaluation = models.ForeignKey(
        RubricEvaluation,
        on_delete=models.CASCADE,
        related_name="decision_recommendations",
    )
    recommendation_status = models.CharField(
        max_length=30,
        choices=RECOMMENDATION_CHOICES,
        default="recommend_manual_review",
        db_index=True,
    )
    blocking_issues = models.JSONField(default=list, blank=True)
    warnings = models.JSONField(default=list, blank=True)
    decision_basis = models.JSONField(default=dict, blank=True)
    explanation = models.JSONField(default=dict, blank=True)
    policy_snapshot = models.JSONField(default=dict, blank=True)
    evidence_snapshot = models.JSONField(default=dict, blank=True)
    ai_signal_snapshot = models.JSONField(default=dict, blank=True)

    advisory_only = models.BooleanField(default=True)
    engine_version = models.CharField(max_length=20, default="v1")
    generated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="generated_vetting_decision_recommendations",
    )
    is_latest = models.BooleanField(default=True, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["case"],
                condition=models.Q(is_latest=True),
                name="uniq_vetting_decision_latest_per_case",
            ),
        ]
        indexes = [
            models.Index(fields=["case", "is_latest"], name="idx_vdr_case_latest"),
            models.Index(fields=["rubric_evaluation", "is_latest"], name="idx_vdr_eval_latest"),
            models.Index(fields=["recommendation_status", "created_at"], name="idx_vdr_status_created"),
        ]
        verbose_name = "Vetting Decision Recommendation"
        verbose_name_plural = "Vetting Decision Recommendations"

    def __str__(self):
        return f"Decision recommendation for {self.case.case_id}: {self.recommendation_status}"


class VettingDecisionOverride(models.Model):
    """
    Tracks explicit human overrides to advisory recommendation output.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    recommendation = models.ForeignKey(
        VettingDecisionRecommendation,
        on_delete=models.CASCADE,
        related_name="overrides",
    )
    previous_recommendation_status = models.CharField(max_length=30)
    overridden_recommendation_status = models.CharField(
        max_length=30,
        choices=VettingDecisionRecommendation.RECOMMENDATION_CHOICES,
    )
    rationale = models.TextField()
    overridden_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="vetting_decision_overrides",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recommendation", "created_at"], name="idx_vdo_rec_created"),
        ]
        verbose_name = "Vetting Decision Override"
        verbose_name_plural = "Vetting Decision Overrides"

    def __str__(self):
        return (
            f"Decision override {self.previous_recommendation_status} -> "
            f"{self.overridden_recommendation_status}"
        )


class CriteriaOverride(models.Model):
    """
    Manual override of AI-generated scores.
    
    Allows internal reviewers to adjust scores with justification.
    Important for bias mitigation and human oversight.
    
    Academic Note:
    --------------
    Tracks human-in-the-loop interventions for:
    1. Bias analysis (which AI decisions get overridden?)
    2. Model improvement (ground truth labeling)
    3. Audit trail (accountability and transparency)
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

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
