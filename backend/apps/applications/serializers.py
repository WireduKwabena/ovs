# backend/apps/applications/serializers.py
# From: Development Guide PDF

from rest_framework import serializers
from .models import VettingCase, Document, VerificationResult
from apps.auth_actions.serializers import UserSerializer

class VerificationResultSerializer(serializers.ModelSerializer):
    """Serializer for AI verification results"""
    
    class Meta:
        model = VerificationResult
        fields = [
            'id', 'ocr_text', 'ocr_confidence', 'ocr_method',
            'authenticity_score', 'is_authentic', 'extracted_data',
            'cv_checks', 'details', 'verified_at'
        ]
        read_only_fields = ['id', 'verified_at']


class DocumentSerializer(serializers.ModelSerializer):
    """Serializer for documents with nested verification results"""
    verification_results = VerificationResultSerializer(many=True, read_only=True)
    document_type_display = serializers.CharField(source='get_document_type_display', read_only=True)
    verification_status_display = serializers.CharField(source='get_verification_status_display', read_only=True)
    file_url = serializers.SerializerMethodField()
    
    class Meta:
        model = Document
        fields = [
            'id', 'document_type', 'document_type_display', 'file_name',
            'file_path', 'file_size', 'verification_status', 
            'verification_status_display', 'ai_confidence_score',
            'verification_results', 'upload_date', 'updated_at', 'file_url'
        ]
        read_only_fields = ['id', 'file_path', 'verification_status', 'upload_date']
    
    def get_file_url(self, obj):
        """Generate pre-signed URL for document viewing"""
        from documents.services import DocumentService
        doc_service = DocumentService()
        try:
            return doc_service.get_presigned_url(obj.file_path, expiration=3600)
        except:
            return None


class VettingCaseSerializer(serializers.ModelSerializer):
    """Main serializer for vetting applications"""
    documents = DocumentSerializer(many=True, read_only=True)
    applicant = UserSerializer(read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)
    
    # Related data
    fraud_result = serializers.SerializerMethodField()
    consistency_result = serializers.SerializerMethodField()
    rubric_evaluation = serializers.SerializerMethodField()
    
    class Meta:
        model = VettingCase
        fields = [
            'id', 'case_id', 'applicant', 'status', 'status_display',
            'application_type', 'priority', 'priority_display',
            'consistency_score', 'fraud_risk_score', 'notes',
            'documents', 'fraud_result', 'consistency_result',
            'rubric_evaluation', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'case_id', 'created_at', 'updated_at']
    
    def get_fraud_result(self, obj):
        """Get fraud detection results if available"""
        try:
            fraud = obj.fraud_result
            return {
                'is_fraud': fraud.is_fraud,
                'fraud_probability': fraud.fraud_probability,
                'risk_level': fraud.risk_level,
                'recommendation': fraud.recommendation
            }
        except:
            return None
    
    def get_consistency_result(self, obj):
        """Get consistency check results if available"""
        try:
            consistency = obj.consistency_result
            return {
                'overall_consistent': consistency.overall_consistent,
                'overall_score': consistency.overall_score,
                'recommendation': consistency.recommendation
            }
        except:
            return None
    
    def get_rubric_evaluation(self, obj):
        """Get latest rubric evaluation"""
        evaluation = obj.rubric_evaluations.first()
        if evaluation:
            return {
                'overall_score': evaluation.overall_score,
                'passed': evaluation.passed,
                'recommendation': evaluation.ai_recommendation,
                'rubric_name': evaluation.rubric.name
            }
        return None


class VettingCaseCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating new applications"""
    
    class Meta:
        model = VettingCase
        fields = ['application_type', 'priority', 'notes']
    
    def create(self, validated_data):
        # Applicant is set in view
        validated_data['status'] = 'pending'
        return super().create(validated_data)