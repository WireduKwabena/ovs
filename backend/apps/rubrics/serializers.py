# backend/apps/rubrics/serializers.py
# From: Dynamic Vetting Rubrics PDF

from rest_framework import serializers
from .models import VettingRubric, RubricCriteria, RubricEvaluation, CriteriaOverride

class RubricCriteriaSerializer(serializers.ModelSerializer):
    """Serializer for rubric criteria"""
    criteria_type_display = serializers.CharField(source='get_criteria_type_display', read_only=True)
    
    class Meta:
        model = RubricCriteria
        fields = [
            'id', 'name', 'description', 'criteria_type', 
            'criteria_type_display', 'weight', 'minimum_score',
            'is_mandatory', 'scoring_rules', 'order'
        ]
        read_only_fields = ['id']
    
    def validate_weight(self, value):
        """Ensure weight is between 0-100"""
        if value < 0 or value > 100:
            raise serializers.ValidationError("Weight must be between 0 and 100")
        return value


class VettingRubricSerializer(serializers.ModelSerializer):
    """Serializer for vetting rubrics"""
    criteria = RubricCriteriaSerializer(many=True, read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    rubric_type_display = serializers.CharField(source='get_rubric_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    total_weight = serializers.SerializerMethodField()
    
    class Meta:
        model = VettingRubric
        fields = [
            'id', 'rubric_id', 'name', 'description', 'rubric_type',
            'rubric_type_display', 'department', 'position_level',
            'status', 'status_display', 'passing_score',
            'auto_approve_threshold', 'auto_reject_threshold',
            'criteria', 'created_by_name', 'total_weight',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'rubric_id', 'created_at', 'updated_at']
    
    def get_total_weight(self, obj):
        """Calculate total weight of all criteria"""
        return sum(c.weight for c in obj.criteria.all())
    
    def validate(self, data):
        """Ensure thresholds are logical"""
        passing = data.get('passing_score')
        auto_approve = data.get('auto_approve_threshold')
        auto_reject = data.get('auto_reject_threshold')
        
        if auto_approve and auto_approve <= passing:
            raise serializers.ValidationError(
                "Auto-approve threshold must be higher than passing score"
            )
        
        if auto_reject and auto_reject >= passing:
            raise serializers.ValidationError(
                "Auto-reject threshold must be lower than passing score"
            )
        
        return data


class VettingRubricCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating rubrics with criteria"""
    criteria = RubricCriteriaSerializer(many=True, write_only=True)
    
    class Meta:
        model = VettingRubric
        fields = [
            'name', 'description', 'rubric_type', 'department',
            'position_level', 'passing_score', 'auto_approve_threshold',
            'auto_reject_threshold', 'criteria'
        ]
    
    def validate_criteria(self, criteria_data):
        """Validate that criteria weights sum to 100"""
        total_weight = sum(c['weight'] for c in criteria_data)
        if total_weight != 100:
            raise serializers.ValidationError(
                f"Criteria weights must sum to 100 (currently {total_weight})"
            )
        return criteria_data
    
    def create(self, validated_data):
        criteria_data = validated_data.pop('criteria')
        
        # Generate rubric ID
        import uuid
        validated_data['rubric_id'] = f"RUB-{uuid.uuid4().hex[:8].upper()}"
        
        # Create rubric
        rubric = VettingRubric.objects.create(**validated_data)
        
        # Create criteria
        for i, criterion_data in enumerate(criteria_data):
            RubricCriteria.objects.create(
                rubric=rubric,
                order=i,
                **criterion_data
            )
        
        return rubric


class CriteriaOverrideSerializer(serializers.ModelSerializer):
    """Serializer for criteria overrides"""
    overridden_by_name = serializers.CharField(source='overridden_by.username', read_only=True)
    criteria_name = serializers.CharField(source='criteria.name', read_only=True)
    
    class Meta:
        model = CriteriaOverride
        fields = [
            'id', 'criteria', 'criteria_name', 'original_score',
            'override_score', 'reason', 'overridden_by',
            'overridden_by_name', 'overridden_at'
        ]
        read_only_fields = ['id', 'overridden_by', 'overridden_at']


class RubricEvaluationSerializer(serializers.ModelSerializer):
    """Serializer for rubric evaluation results"""
    rubric_name = serializers.CharField(source='rubric.name', read_only=True)
    application_case_id = serializers.CharField(source='application.case_id', read_only=True)
    overrides = CriteriaOverrideSerializer(many=True, read_only=True)
    
    class Meta:
        model = RubricEvaluation
        fields = [
            'id', 'application', 'application_case_id', 'rubric',
            'rubric_name', 'overall_score', 'criteria_scores',
            'passed', 'ai_recommendation', 'evaluation_details',
            'flags', 'warnings', 'overrides', 'evaluated_at'
        ]
        read_only_fields = ['id', 'evaluated_at']