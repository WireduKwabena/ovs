"""Dedicated public transparency serializers.

These serializers intentionally expose only public-safe fields.
Do not include internal vetting notes, committee deliberations, or risk traces.
"""

from rest_framework import serializers

from apps.personnel.models import PersonnelRecord
from apps.positions.models import GovernmentPosition

from .models import AppointmentRecord


class PublicAppointmentRecordSerializer(serializers.ModelSerializer):
    position_title = serializers.CharField(source="position.title", read_only=True)
    position_branch = serializers.CharField(source="position.branch", read_only=True)
    institution = serializers.CharField(source="position.institution", read_only=True)
    appointment_authority = serializers.CharField(source="position.appointment_authority", read_only=True)
    nominee_name = serializers.CharField(source="nominee.full_name", read_only=True)
    publication_status = serializers.SerializerMethodField()
    publication_reference = serializers.SerializerMethodField()
    published_at = serializers.SerializerMethodField()

    @staticmethod
    def _publication(obj):
        return getattr(obj, "publication", None)

    def get_publication_status(self, obj):
        publication = self._publication(obj)
        return publication.status if publication is not None else "draft"

    def get_publication_reference(self, obj):
        publication = self._publication(obj)
        if publication is not None and publication.publication_reference:
            return publication.publication_reference
        return obj.gazette_number

    def get_published_at(self, obj):
        publication = self._publication(obj)
        return publication.published_at if publication is not None else None

    class Meta:
        model = AppointmentRecord
        fields = [
            "id",
            "position_title",
            "position_branch",
            "institution",
            "appointment_authority",
            "nominee_name",
            "nominated_by_display",
            "nominated_by_org",
            "status",
            "nomination_date",
            "appointment_date",
            "gazette_number",
            "gazette_date",
            "publication_status",
            "publication_reference",
            "published_at",
        ]


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


class PublicTransparencySummarySerializer(serializers.Serializer):
    published_appointments = serializers.IntegerField(min_value=0)
    open_public_appointments = serializers.IntegerField(min_value=0)
    public_positions = serializers.IntegerField(min_value=0)
    vacant_public_positions = serializers.IntegerField(min_value=0)
    active_public_officeholders = serializers.IntegerField(min_value=0)
    last_published_at = serializers.DateTimeField(allow_null=True)

