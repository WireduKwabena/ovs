# backend/apps/ml_monitoring/models.py
# From: AI/ML Implementation PDF
import uuid
from django.db import models

class MLModelMetrics(models.Model):
    """Track ML model performance - from Training PDF"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    model_name = models.CharField(max_length=100)
    model_version = models.CharField(max_length=50)
    
    accuracy = models.FloatField()
    precision = models.FloatField()
    recall = models.FloatField()
    f1_score = models.FloatField()
    
    confusion_matrix = models.JSONField(default=dict)
    
    trained_at = models.DateTimeField()
    evaluated_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'ml_model_metrics'
        ordering = ['-evaluated_at']
        app_label = 'ml_monitoring'
