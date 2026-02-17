from rest_framework import serializers

from .models import Candidate, CandidateEnrollment


class CandidateSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField(read_only=True)

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
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "full_name"]

    def get_full_name(self, obj):
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
