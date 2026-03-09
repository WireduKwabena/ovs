from rest_framework import serializers

from .models import GovernmentPosition


class GovernmentPositionSerializer(serializers.ModelSerializer):
    current_holder_name = serializers.CharField(source="current_holder.full_name", read_only=True)
    rubric_name = serializers.CharField(source="rubric.name", read_only=True)
    organization_name = serializers.CharField(source="organization.name", read_only=True)

    class Meta:
        model = GovernmentPosition
        fields = [
            "id",
            "organization",
            "organization_name",
            "title",
            "branch",
            "institution",
            "appointment_authority",
            "confirmation_required",
            "constitutional_basis",
            "term_length_years",
            "required_qualifications",
            "is_vacant",
            "is_public",
            "current_holder",
            "current_holder_name",
            "rubric",
            "rubric_name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "current_holder_name", "rubric_name", "organization_name"]


class PublicGovernmentPositionSerializer(serializers.ModelSerializer):
    current_holder_name = serializers.CharField(source="current_holder.full_name", read_only=True)

    class Meta:
        model = GovernmentPosition
        fields = [
            "id",
            "title",
            "branch",
            "institution",
            "appointment_authority",
            "confirmation_required",
            "constitutional_basis",
            "term_length_years",
            "is_vacant",
            "current_holder_name",
        ]
