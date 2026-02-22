# backend/apps/fraud/models.py
# From: AI/ML Implementation PDF
import uuid
from django.db import models
from apps.applications.models import VettingCase

class FraudDetectionResult(models.Model):
    """Fraud detection results - from AI/ML PDF"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.OneToOneField(VettingCase, on_delete=models.CASCADE, related_name='fraud_result')
    
    is_fraud = models.BooleanField()
    fraud_probability = models.FloatField()  # 0-1
    anomaly_score = models.FloatField()
    
    RISK_LEVELS = [
        ('LOW', 'Low Risk'),
        ('MEDIUM', 'Medium Risk'),
        ('HIGH', 'High Risk'),
    ]
    risk_level = models.CharField(max_length=10, choices=RISK_LEVELS)
    
    RECOMMENDATIONS = [
        ('PROCEED', 'Proceed'),
        ('MANUAL_REVIEW', 'Manual Review'),
        ('REJECT', 'Reject'),
    ]
    recommendation = models.CharField(max_length=20, choices=RECOMMENDATIONS)
    
    # Feature scores for transparency
    feature_scores = models.JSONField(default=dict)
    
    detected_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'fraud_detection_results'
        app_label = 'fraud'


class ConsistencyCheckResult(models.Model):
    """Cross-document consistency - from AI/ML PDF"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.OneToOneField(VettingCase, on_delete=models.CASCADE, related_name='consistency_result')
    
    overall_consistent = models.BooleanField()
    overall_score = models.FloatField()  # 0-100
    
    name_consistency = models.JSONField(default=dict)
    date_consistency = models.JSONField(default=dict)
    entity_consistency = models.JSONField(default=dict)
    
    recommendation = models.CharField(max_length=20)
    
    checked_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'consistency_check_results'
        app_label = 'fraud'
