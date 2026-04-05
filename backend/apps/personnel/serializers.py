from rest_framework import serializers

from .models import PersonnelRecord


class PersonnelRecordSerializer(serializers.ModelSerializer):
    linked_candidate_email = serializers.EmailField(source="linked_candidate.email", read_only=True)

    class Meta:
        model = PersonnelRecord
        fields = [
            "id",
            "full_name",
            "date_of_birth",
            "nationality",
            "national_id_hash",
            "national_id_encrypted",
            "gender",
            "contact_email",
            "contact_phone",
            "bio_summary",
            "academic_qualifications",
            "professional_history",
            "is_active_officeholder",
            "is_public",
            "linked_candidate",
            "linked_candidate_email",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "linked_candidate_email"]


class PublicPersonnelRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = PersonnelRecord
        fields = [
            "id",
            "full_name",
            "gender",
            "bio_summary",
            "academic_qualifications",
            "is_active_officeholder",
        ]
