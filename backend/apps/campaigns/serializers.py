from rest_framework import serializers

from .models import CampaignRubricVersion, VettingCampaign


class CampaignRubricVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = CampaignRubricVersion
        fields = [
            "id",
            "campaign",
            "version",
            "name",
            "description",
            "weight_document",
            "weight_interview",
            "passing_score",
            "auto_approve_threshold",
            "auto_reject_threshold",
            "rubric_payload",
            "is_active",
            "created_by",
            "created_at",
        ]
        read_only_fields = ["id", "campaign", "version", "created_by", "created_at"]


class VettingCampaignSerializer(serializers.ModelSerializer):
    initiated_by_email = serializers.CharField(source="initiated_by.email", read_only=True)

    class Meta:
        model = VettingCampaign
        fields = [
            "id",
            "name",
            "description",
            "status",
            "starts_at",
            "ends_at",
            "settings_json",
            "initiated_by",
            "initiated_by_email",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "initiated_by", "initiated_by_email", "created_at", "updated_at"]


class CampaignDashboardSerializer(serializers.Serializer):
    total_candidates = serializers.IntegerField()
    invited = serializers.IntegerField()
    registered = serializers.IntegerField()
    in_progress = serializers.IntegerField()
    completed = serializers.IntegerField()
    reviewed = serializers.IntegerField()
    approved = serializers.IntegerField()
    rejected = serializers.IntegerField()
    escalated = serializers.IntegerField()
