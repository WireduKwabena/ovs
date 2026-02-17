# backend/apps/fraud/serializers.py

from rest_framework import serializers
from .models import FraudDetectionResult, ConsistencyCheckResult

class FraudDetectionResultSerializer(serializers.ModelSerializer):
    """Serializer for fraud detection results"""
    application_case_id = serializers.CharField(
        source='application.case_id',
        read_only=True
    )
    risk_level_display = serializers.CharField(
        source='get_risk_level_display',
        read_only=True
    )
    recommendation_display = serializers.CharField(
        source='get_recommendation_display',
        read_only=True
    )
    
    class Meta:
        model = FraudDetectionResult
        fields = [
            'id', 'application', 'application_case_id',
            'is_fraud', 'fraud_probability', 'anomaly_score',
            'risk_level', 'risk_level_display',
            'recommendation', 'recommendation_display',
            'feature_scores', 'detected_at'
        ]
        read_only_fields = ['id', 'detected_at']


class ConsistencyCheckResultSerializer(serializers.ModelSerializer):
    """Serializer for consistency check results"""
    application_case_id = serializers.CharField(
        source='application.case_id',
        read_only=True
    )
    
    class Meta:
        model = ConsistencyCheckResult
        fields = [
            'id', 'application', 'application_case_id',
            'overall_consistent', 'overall_score',
            'name_consistency', 'date_consistency',
            'entity_consistency', 'recommendation',
            'checked_at'
        ]
        read_only_fields = ['id', 'checked_at']