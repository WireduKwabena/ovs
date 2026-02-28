from rest_framework import serializers

from .models import Candidate, CandidateEnrollment, CandidateSocialProfile


class CandidateSocialProfileSerializer(serializers.ModelSerializer):
    platform_display = serializers.CharField(source="get_platform_display", read_only=True)

    class Meta:
        model = CandidateSocialProfile
        fields = [
            "id",
            "candidate",
            "platform",
            "platform_display",
            "url",
            "username",
            "display_name",
            "is_primary",
            "metadata",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "platform_display"]


class CandidateSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField(read_only=True)
    social_profiles = CandidateSocialProfileSerializer(many=True, read_only=True)

    class Meta:
        model = Candidate
        fields = [
            "id",
            "first_name",
            "last_name",
            "full_name",
            "email",
            "phone_number",
            "preferred_channel",
            "consent_recording",
            "consent_ai_processing",
            "social_profiles",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "full_name", "social_profiles"]

    def get_full_name(self, obj) -> str:
        return f"{obj.first_name} {obj.last_name}".strip()


class CandidateEnrollmentSerializer(serializers.ModelSerializer):
    candidate_email = serializers.CharField(source="candidate.email", read_only=True)
    campaign_name = serializers.CharField(source="campaign.name", read_only=True)

    class Meta:
        model = CandidateEnrollment
        fields = [
            "id",
            "campaign",
            "campaign_name",
            "candidate",
            "candidate_email",
            "status",
            "invited_at",
            "registered_at",
            "completed_at",
            "reviewed_at",
            "review_notes",
            "decision_by",
            "metadata",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "invited_at",
            "registered_at",
            "completed_at",
            "reviewed_at",
            "created_at",
            "updated_at",
        ]
