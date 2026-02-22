"""
Interviews Models
=================
Video interview session and analysis models.

Academic Note:
--------------
Implements simplified interview system without HeyGen avatar.
Uses pre-defined questions with AI-based response evaluation.

Key components:
1. InterviewSession: Main interview entity
2. InterviewQuestion: Question bank
3. InterviewResponse: Candidate responses with analysis
4. VideoAnalysis: Multimodal (audio + video) analysis results
"""

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from apps.authentication.models import User
from apps.applications.models import VettingCase, InterrogationFlag
import uuid


class InterviewSession(models.Model):
    """
    Main interview session model.
    
    Represents a complete interview session for a vetting case.
    Simplified from docs - no HeyGen, just question bank + video responses.
    
    Academic Note:
    --------------
    State machine: created → in_progress → completed/failed
    Tracks timing for performance analysis.
    """
    
    STATUS_CHOICES = [
        ('created', 'Created'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    
    # Identification
    session_id = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        editable=False
    )
    
    # Relationships
    case = models.ForeignKey(
        VettingCase,
        on_delete=models.CASCADE,
        related_name='interview_sessions'
    )
    
    # Session configuration
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='created',
        db_index=True
    )
    
    # Question selection strategy
    use_dynamic_questions = models.BooleanField(
        default=True,
        help_text="Generate questions based on flags vs. use predefined set"
    )
    
    max_questions = models.IntegerField(
        default=10,
        validators=[MinValueValidator(1), MaxValueValidator(50)]
    )
    
    # Progress tracking
    current_question_number = models.IntegerField(default=0)
    total_questions_asked = models.IntegerField(default=0)
    
    # Scores (aggregated from responses)
    overall_score = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    
    communication_score = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    
    consistency_score = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    
    confidence_score = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    
    # Analysis summary
    interview_summary = models.TextField(blank=True)
    key_findings = models.JSONField(default=list)
    red_flags_detected = models.JSONField(default=list)
    
    # Flag resolution tracking
    flags_addressed = models.ManyToManyField(
        InterrogationFlag,
        related_name='addressed_in_sessions',
        blank=True
    )
    
    flags_resolved_count = models.IntegerField(default=0)
    flags_unresolved_count = models.IntegerField(default=0)
    
    # Conversation history (for LLM context)
    conversation_history = models.JSONField(
        default=list,
        help_text="Full Q&A history for context building"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['session_id', 'status']),
            models.Index(fields=['case', 'status']),
            models.Index(fields=['-created_at']),
        ]
        verbose_name = 'Interview Session'
        verbose_name_plural = 'Interview Sessions'
    
    def __str__(self):
        return f"{self.session_id} - {self.case.case_id}"
    
    def save(self, *args, **kwargs):
        # Generate session_id if not exists
        if not self.session_id:
            self.session_id = f"INT-{uuid.uuid4().hex[:10].upper()}"
        
        # Calculate duration if completed
        if self.status == 'completed' and self.completed_at and self.started_at:
            delta = self.completed_at - self.started_at
            self.duration_seconds = int(delta.total_seconds())
        
        super().save(*args, **kwargs)
    
    @property
    def duration_minutes(self):
        """Return duration in minutes."""
        return round(self.duration_seconds / 60, 1) if self.duration_seconds else 0
    
    @property
    def completion_rate(self):
        """Calculate interview completion rate."""
        if self.max_questions > 0:
            return (self.total_questions_asked / self.max_questions) * 100
        return 0
    
    def start_session(self):
        """Mark session as started."""
        self.status = 'in_progress'
        self.started_at = timezone.now()
        self.save()
    
    def complete_session(self):
        """Mark session as completed."""
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.save()


class InterviewQuestion(models.Model):
    """
    Question bank for interviews.
    
    Stores predefined questions with metadata for selection logic.
    Can be generic or case-specific (targeting flags).
    
    Academic Note:
    --------------
    Question classification enables intelligent question selection.
    Difficulty levels allow adaptive interview progression.
    """
    
    QUESTION_TYPE_CHOICES = [
        ('general', 'General Background'),
        ('education', 'Educational Background'),
        ('employment', 'Employment History'),
        ('verification', 'Document Verification'),
        ('flag_specific', 'Flag-Specific Clarification'),
        ('behavioral', 'Behavioral Assessment'),
        ('situational', 'Situational Question'),
    ]
    
    DIFFICULTY_CHOICES = [
        ('easy', 'Easy'),
        ('medium', 'Medium'),
        ('hard', 'Hard'),
    ]
    
    # Question details
    question_text = models.TextField()
    question_type = models.CharField(
        max_length=30,
        choices=QUESTION_TYPE_CHOICES,
        db_index=True
    )
    
    difficulty = models.CharField(
        max_length=20,
        choices=DIFFICULTY_CHOICES,
        default='medium'
    )
    
    # Flag targeting (optional)
    targets_flag_type = models.CharField(
        max_length=50,
        blank=True,
        help_text="Which type of flag this question addresses"
    )
    
    # Evaluation criteria
    evaluation_rubric = models.TextField(
        help_text="Criteria for evaluating responses to this question"
    )
    
    expected_keywords = models.JSONField(
        default=list,
        help_text="Keywords/phrases expected in good answers"
    )
    
    # Usage tracking
    times_used = models.IntegerField(default=0)
    average_response_quality = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    
    # Metadata
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_questions'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['question_type', 'difficulty']
        indexes = [
            models.Index(fields=['question_type', 'is_active']),
            models.Index(fields=['difficulty']),
        ]
        verbose_name = 'Interview Question'
        verbose_name_plural = 'Interview Questions'
    
    def __str__(self):
        return f"{self.get_question_type_display()}: {self.question_text[:50]}..."
    
    def increment_usage(self):
        """Track question usage."""
        self.times_used += 1
        self.save()


class InterviewResponse(models.Model):
    """
    Candidate's response to an interview question.
    
    Stores video, transcript, and AI analysis results.
    
    Academic Note:
    --------------
    Central model for multimodal analysis combining:
    - Speech-to-text (Whisper)
    - Sentiment analysis (Transformers)
    - Video analysis (OpenCV)
    - LLM evaluation (GPT-4/Claude)
    """
    
    # Relationships
    session = models.ForeignKey(
        InterviewSession,
        on_delete=models.CASCADE,
        related_name='responses'
    )
    
    question = models.ForeignKey(
        InterviewQuestion,
        on_delete=models.CASCADE,
        related_name='responses'
    )
    
    # Targeting (if addressing specific flag)
    target_flag = models.ForeignKey(
        InterrogationFlag,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='interview_responses'
    )
    
    # Response content
    sequence_number = models.IntegerField(
        help_text="Order in the interview"
    )
    
    video_file = models.FileField(
        upload_to='interview_videos/',
        null=True,
        blank=True
    )
    
    video_url = models.URLField(
        blank=True,
        help_text="URL if stored externally (S3)"
    )
    
    audio_file = models.FileField(
        upload_to='interview_audio/',
        null=True,
        blank=True
    )
    
    # Transcription
    transcript = models.TextField(blank=True)
    transcript_confidence = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    
    # Analysis results
    sentiment = models.CharField(
        max_length=50,
        blank=True,
        help_text="Overall emotional sentiment"
    )
    
    sentiment_score = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    
    # Quality scores
    response_quality_score = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Overall response quality from LLM evaluation"
    )
    
    relevance_score = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="How relevant the answer is to the question"
    )
    
    completeness_score = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    
    coherence_score = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    
    # LLM evaluation
    llm_evaluation = models.JSONField(
        default=dict,
        help_text="Detailed evaluation from LLM (GPT-4/Claude)"
    )
    
    key_points_extracted = models.JSONField(
        default=list,
        help_text="Main points from the response"
    )
    
    concerns_detected = models.JSONField(
        default=list,
        help_text="Any concerns or red flags in the response"
    )
    
    # Timing
    response_duration_seconds = models.IntegerField(
        default=0,
        help_text="How long the candidate spoke"
    )
    
    answered_at = models.DateTimeField(null=True, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['session', 'sequence_number']
        indexes = [
            models.Index(fields=['session', 'sequence_number']),
        ]
        unique_together = ['session', 'sequence_number']
        verbose_name = 'Interview Response'
        verbose_name_plural = 'Interview Responses'
    
    def __str__(self):
        return f"{self.session.session_id} - Q{self.sequence_number}"
    
    @property
    def has_video(self):
        """Check if video is available."""
        return bool(self.video_file or self.video_url)
    
    @property
    def has_transcript(self):
        """Check if transcript is available."""
        return bool(self.transcript)


class VideoAnalysis(models.Model):
    """
    Non-verbal video analysis results.
    
    Analyzes facial expressions, eye contact, and other visual cues
    using OpenCV and MediaPipe (simplified from docs).
    
    Academic Note:
    --------------
    Multimodal analysis component focusing on non-verbal communication.
    Used for deception detection research (ethical considerations apply).
    """
    
    # Relationship
    response = models.OneToOneField(
        InterviewResponse,
        on_delete=models.CASCADE,
        related_name='video_analysis'
    )
    
    # Face detection
    face_detected = models.BooleanField(default=False)
    face_detection_confidence = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    
    # Eye contact (simplified)
    eye_contact_percentage = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Approximate percentage of time looking at camera"
    )
    
    gaze_direction_changes = models.IntegerField(
        default=0,
        help_text="Number of times gaze direction changed"
    )
    
    # Facial expressions (simplified)
    dominant_emotion = models.CharField(
        max_length=50,
        blank=True,
        help_text="Most common emotion detected"
    )
    
    emotion_distribution = models.JSONField(
        default=dict,
        help_text="Distribution of emotions throughout response"
    )
    
    # Confidence indicators
    confidence_level = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Overall confidence based on visual cues"
    )
    
    stress_level = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Estimated stress level"
    )
    
    # Movement analysis
    head_movement_count = models.IntegerField(
        default=0,
        help_text="Significant head movements"
    )
    
    fidgeting_detected = models.BooleanField(default=False)
    
    # Behavioral indicators
    behavioral_indicators = models.JSONField(
        default=list,
        help_text="List of observed behavioral patterns"
    )
    
    # Raw analysis data
    raw_analysis_data = models.JSONField(
        default=dict,
        help_text="Complete raw analysis from CV models"
    )
    
    # Metadata
    frames_analyzed = models.IntegerField(default=0)
    analysis_duration_seconds = models.FloatField(
        null=True,
        blank=True
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Video Analysis'
        verbose_name_plural = 'Video Analyses'
    
    def __str__(self):
        return f"Video Analysis: {self.response}"
    
    @property
    def has_concerns(self):
        """Check if analysis flagged concerns."""
        return (
            self.eye_contact_percentage and self.eye_contact_percentage < 40 or
            self.stress_level and self.stress_level > 70 or
            len(self.behavioral_indicators) > 3
        )


class InterviewFeedback(models.Model):
    """
    HR manager feedback on interview results.
    
    Allows manual review and override of AI evaluation.
    
    Academic Note:
    --------------
    Human-in-the-loop evaluation for:
    1. Validating AI decisions
    2. Collecting ground truth for model improvement
    3. Ensuring fairness and bias mitigation
    """
    
    # Relationships
    session = models.ForeignKey(
        InterviewSession,
        on_delete=models.CASCADE,
        related_name='feedback'
    )
    
    reviewer = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='interview_reviews'
    )
    
    # Overall evaluation
    rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Overall rating (1-5 stars)"
    )
    
    # Detailed assessment
    communication_rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    
    clarity_rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    
    consistency_rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    
    # Comments
    strengths = models.TextField(blank=True)
    weaknesses = models.TextField(blank=True)
    general_comments = models.TextField()
    
    # Decision
    recommendation = models.CharField(
        max_length=20,
        choices=[
            ('strongly_approve', 'Strongly Approve'),
            ('approve', 'Approve'),
            ('neutral', 'Neutral'),
            ('reject', 'Reject'),
            ('strongly_reject', 'Strongly Reject'),
        ]
    )
    
    decision_rationale = models.TextField()
    
    # AI agreement
    agrees_with_ai = models.BooleanField(
        help_text="Does reviewer agree with AI evaluation?"
    )
    
    ai_override_reason = models.TextField(
        blank=True,
        help_text="If disagreeing with AI, explain why"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Interview Feedback'
        verbose_name_plural = 'Interview Feedback'
    
    def __str__(self):
        return f"Feedback: {self.session.session_id} by {self.reviewer}"


# Legacy aliases kept for backward compatibility with older interview modules.
DynamicInterviewSession = InterviewSession
InterviewExchange = InterviewResponse
NonVerbalAnalysis = VideoAnalysis


