"""
Core Models & Utilities
========================
Shared abstract base models and common utilities.

Academic Note:
--------------
DRY (Don't Repeat Yourself) principle implementation.
Provides reusable components across all apps.
"""

import uuid

from django.db import models
from django.utils import timezone


class TimeStampedModel(models.Model):
    """
    Abstract base model with timestamp fields.
    
    Inherit from this for automatic created/updated tracking.
    
    Academic Note:
    --------------
    Audit trail pattern for temporal data tracking.
    Essential for debugging and performance analysis.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        abstract = True
        ordering = ['-created_at']
    
    @property
    def age_days(self):
        """Calculate age in days."""
        if self.created_at:
            delta = timezone.now() - self.created_at
            return delta.days
        return None


class SoftDeleteModel(models.Model):
    """
    Abstract base model with soft delete functionality.
    
    Items are marked as deleted rather than removed from database.
    
    Academic Note:
    --------------
    Implements soft delete pattern for data recovery and audit trail.
    Important for compliance with data retention policies.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    is_deleted = models.BooleanField(default=False, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(
        'authentication.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(class)s_deleted'
    )
    
    class Meta:
        abstract = True
    
    def soft_delete(self, user=None):
        """Soft delete the object."""
        self.is_deleted = True
        self.deleted_at = timezone.now()
        if user:
            self.deleted_by = user
        self.save()
    
    def restore(self):
        """Restore soft-deleted object."""
        self.is_deleted = False
        self.deleted_at = None
        self.deleted_by = None
        self.save()


class AuditModel(models.Model):
    """
    Abstract base model with comprehensive audit trail.
    
    Tracks who created/modified records and when.
    
    Academic Note:
    --------------
    Comprehensive audit logging for compliance and security.
    Enables forensic analysis of data changes.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    created_by = models.ForeignKey(
        'authentication.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(class)s_created'
    )
    
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        'authentication.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(class)s_updated'
    )
    
    class Meta:
        abstract = True


class ProcessingStatusModel(models.Model):
    """
    Abstract base model for items that go through processing pipeline.
    
    Common pattern for async processing workflows.
    
    Academic Note:
    --------------
    State machine pattern for pipeline processing.
    Enables monitoring and troubleshooting of async workflows.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('queued', 'Queued'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        db_index=True
    )
    
    processing_started_at = models.DateTimeField(null=True, blank=True)
    processing_completed_at = models.DateTimeField(null=True, blank=True)
    processing_duration_seconds = models.FloatField(null=True, blank=True)
    
    error_message = models.TextField(blank=True)
    retry_count = models.IntegerField(default=0)
    
    class Meta:
        abstract = True
    
    def start_processing(self):
        """Mark as processing started."""
        self.status = 'processing'
        self.processing_started_at = timezone.now()
        self.save()
    
    def complete_processing(self):
        """Mark as processing completed."""
        self.status = 'completed'
        self.processing_completed_at = timezone.now()
        
        if self.processing_started_at:
            delta = self.processing_completed_at - self.processing_started_at
            self.processing_duration_seconds = delta.total_seconds()
        
        self.save()
    
    def fail_processing(self, error_message):
        """Mark as processing failed."""
        self.status = 'failed'
        self.error_message = error_message
        self.retry_count += 1
        self.save()
    
    @property
    def can_retry(self, max_retries=3):
        """Check if can retry after failure."""
        return self.status == 'failed' and self.retry_count < max_retries


class ScoreModel(models.Model):
    """
    Abstract base model for entities with scores.
    
    Common scoring pattern with confidence tracking.
    
    Academic Note:
    --------------
    Standardized scoring interface for ML model outputs.
    Always include confidence scores for uncertainty quantification.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    score = models.FloatField(
        null=True,
        blank=True,
        help_text="Primary score (0-100)"
    )
    
    confidence = models.FloatField(
        null=True,
        blank=True,
        help_text="Confidence in score (0-100)"
    )
    
    class Meta:
        abstract = True
    
    @property
    def is_high_confidence(self, threshold=80):
        """Check if score has high confidence."""
        return self.confidence and self.confidence >= threshold
    
    @property
    def is_low_confidence(self, threshold=50):
        """Check if score has low confidence."""
        return self.confidence and self.confidence < threshold


class FileUploadModel(models.Model):
    """
    Abstract base model for file uploads.
    
    Common fields for file handling.
    
    Academic Note:
    --------------
    Standardized file metadata tracking.
    Important for storage management and security auditing.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    file = models.FileField(upload_to='uploads/')
    original_filename = models.CharField(max_length=255)
    file_size = models.IntegerField(help_text="Size in bytes")
    mime_type = models.CharField(max_length=100)
    checksum = models.CharField(
        max_length=64,
        blank=True,
        help_text="SHA256 checksum for integrity verification"
    )
    
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        abstract = True
    
    @property
    def file_size_mb(self):
        """Return file size in MB."""
        return round(self.file_size / (1024 * 1024), 2) if self.file_size else 0
    
    @property
    def file_extension(self):
        """Extract file extension."""
        if self.original_filename:
            return self.original_filename.split('.')[-1].lower()
        return None
