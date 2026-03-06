from django.utils import timezone
from rest_framework import serializers

from .models import AppointmentRecord, AppointmentStageAction, ApprovalStage, ApprovalStageTemplate


class ApprovalStageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ApprovalStage
        fields = [
            "id",
            "template",
            "order",
            "name",
            "required_role",
            "is_required",
            "maps_to_status",
        ]
        read_only_fields = ["id"]


class ApprovalStageTemplateSerializer(serializers.ModelSerializer):
    stages = ApprovalStageSerializer(many=True, read_only=True)

    class Meta:
        model = ApprovalStageTemplate
        fields = ["id", "name", "exercise_type", "created_by", "created_at", "stages"]
        read_only_fields = ["id", "created_by", "created_at", "stages"]


class AppointmentStageActionSerializer(serializers.ModelSerializer):
    actor_email = serializers.EmailField(source="actor.email", read_only=True)
    stage_name = serializers.CharField(source="stage.name", read_only=True)

    class Meta:
        model = AppointmentStageAction
        fields = [
            "id",
            "appointment",
            "stage",
            "stage_name",
            "actor",
            "actor_email",
            "actor_role",
            "action",
            "reason_note",
            "evidence_links",
            "previous_status",
            "new_status",
            "acted_at",
        ]
        read_only_fields = fields


class AppointmentRecordSerializer(serializers.ModelSerializer):
    position_title = serializers.CharField(source="position.title", read_only=True)
    nominee_name = serializers.CharField(source="nominee.full_name", read_only=True)

    class Meta:
        model = AppointmentRecord
        fields = [
            "id",
            "position",
            "position_title",
            "nominee",
            "nominee_name",
            "appointment_exercise",
            "nominated_by_user",
            "nominated_by_display",
            "nominated_by_org",
            "nomination_date",
            "vetting_case",
            "status",
            "committee_recommendation",
            "final_decision_by_user",
            "final_decision_by_display",
            "appointment_date",
            "gazette_number",
            "gazette_date",
            "exit_date",
            "exit_reason",
            "is_public",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "status", "created_at", "updated_at"]

    def validate_nomination_date(self, value):
        if value > timezone.localdate():
            raise serializers.ValidationError("nomination_date cannot be in the future.")
        return value


class AppointmentAdvanceStageSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=AppointmentRecord.STATUS_CHOICES)
    stage_id = serializers.UUIDField(required=False)
    reason_note = serializers.CharField(required=False, allow_blank=True)
    evidence_links = serializers.ListField(
        child=serializers.URLField(),
        required=False,
        allow_empty=True,
    )


class PublicAppointmentRecordSerializer(serializers.ModelSerializer):
    position_title = serializers.CharField(source="position.title", read_only=True)
    institution = serializers.CharField(source="position.institution", read_only=True)
    nominee_name = serializers.CharField(source="nominee.full_name", read_only=True)

    class Meta:
        model = AppointmentRecord
        fields = [
            "id",
            "position_title",
            "institution",
            "nominee_name",
            "nominated_by_display",
            "nominated_by_org",
            "appointment_date",
            "gazette_number",
            "gazette_date",
            "status",
        ]
