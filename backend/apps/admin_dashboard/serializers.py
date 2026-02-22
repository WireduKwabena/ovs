from rest_framework import serializers
from apps.applications import VettingCase

class VettingCaseAdminSerializer(serializers.ModelSerializer):
    applicant_name = serializers.SerializerMethodField()
    applicant_email = serializers.CharField(source='applicant.email')
    admin = serializers.SerializerMethodField()

    class Meta:
        model = VettingCase
        fields = [
            'id',
            'case_id',
            'applicant_name',
            'applicant_email',
            'status',
            'application_type',
            'priority',
            'consistency_score',
            'fraud_risk_score',
            'created_at',
            'updated_at',
            'admin',
        ]

    def get_applicant_name(self, obj):
        return (
            obj.applicant.get_full_name()
            if hasattr(obj.applicant, "get_full_name")
            else obj.applicant.email
        )

    def get_admin(self, obj):
        assignee = getattr(obj, "assigned_to", None)
        if not assignee:
            return None
        return assignee.get_full_name() if hasattr(assignee, "get_full_name") else assignee.email
