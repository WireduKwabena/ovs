# backend/apps/ml_monitoring/serializers.py

from rest_framework import serializers
from .models import MLModelMetrics

class MLModelMetricsSerializer(serializers.ModelSerializer):
    """Serializer for ML model metrics"""
    
    class Meta:
        model = MLModelMetrics
        fields = [
            'id', 'model_name', 'model_version',
            'accuracy', 'precision', 'recall', 'f1_score',
            'confusion_matrix', 'trained_at', 'evaluated_at'
        ]
        read_only_fields = ['id', 'evaluated_at']