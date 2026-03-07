from django.utils import timezone
from rest_framework import serializers

from .models import AppointmentPublication, AppointmentRecord, AppointmentStageAction, ApprovalStage, ApprovalStageTemplate


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
        validators = []
        read_only_fields = ["id", "status", "created_at", "updated_at"]

    def validate_nomination_date(self, value):
        if value > timezone.localdate():
            raise serializers.ValidationError("nomination_date cannot be in the future.")
        return value

    @staticmethod
    def _normalize_text(value) -> str:
        return " ".join(str(value or "").strip().lower().split())

    def validate(self, attrs):
        attrs = super().validate(attrs)

        instance = getattr(self, "instance", None)
        position = attrs.get("position") or getattr(instance, "position", None)
        nominee = attrs.get("nominee") or getattr(instance, "nominee", None)

        if "appointment_exercise" in attrs:
            appointment_exercise = attrs.get("appointment_exercise")
        else:
            appointment_exercise = getattr(instance, "appointment_exercise", None)

        if "vetting_case" in attrs:
            vetting_case = attrs.get("vetting_case")
        else:
            vetting_case = getattr(instance, "vetting_case", None)

        errors: dict[str, list[str]] = {}

        def add_error(field: str, message: str):
            errors.setdefault(field, []).append(message)

        if appointment_exercise is not None and position is not None:
            if appointment_exercise.positions.exists() and not appointment_exercise.positions.filter(id=position.id).exists():
                add_error("position", "Selected position is not linked to the appointment exercise.")

            if appointment_exercise.jurisdiction and appointment_exercise.jurisdiction != position.branch:
                add_error("position", "Appointment exercise jurisdiction does not match selected position branch.")

            if (
                appointment_exercise.appointment_authority
                and position.appointment_authority
                and self._normalize_text(appointment_exercise.appointment_authority)
                != self._normalize_text(position.appointment_authority)
            ):
                add_error(
                    "position",
                    "Appointment exercise appointing authority does not match selected position authority.",
                )

            if appointment_exercise.requires_parliamentary_confirmation and not position.confirmation_required:
                add_error(
                    "position",
                    "Appointment exercise requires parliamentary confirmation but selected position does not.",
                )

            if position.rubric_id:
                active_version = appointment_exercise.rubric_versions.filter(is_active=True).order_by("-version", "-created_at").first()
                if active_version is not None:
                    payload = active_version.rubric_payload if isinstance(active_version.rubric_payload, dict) else {}
                    source_rubric_id = payload.get("source_rubric_id")
                    if source_rubric_id and str(source_rubric_id) != str(position.rubric_id):
                        add_error("position", "Selected position rubric does not match the active campaign rubric source.")

        if vetting_case is not None and appointment_exercise is not None:
            enrollment = getattr(vetting_case, "candidate_enrollment", None)
            if enrollment is not None and enrollment.campaign_id != appointment_exercise.id:
                add_error("vetting_case", "Selected vetting case belongs to a different campaign than appointment exercise.")

        if vetting_case is not None and position is not None:
            if vetting_case.position_applied and self._normalize_text(vetting_case.position_applied) != self._normalize_text(position.title):
                add_error("vetting_case", "Selected vetting case position does not match appointment position.")

            if vetting_case.department and self._normalize_text(vetting_case.department) != self._normalize_text(position.institution[:100]):
                add_error("vetting_case", "Selected vetting case department does not match appointment position institution.")

        if vetting_case is not None and nominee is not None and nominee.linked_candidate_id:
            enrollment = getattr(vetting_case, "candidate_enrollment", None)
            if enrollment is not None and enrollment.candidate_id != nominee.linked_candidate_id:
                add_error("vetting_case", "Selected vetting case candidate does not match nominee linked candidate.")

        if errors:
            raise serializers.ValidationError(errors)

        return attrs


class AppointmentAdvanceStageSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=AppointmentRecord.STATUS_CHOICES)
    stage_id = serializers.UUIDField(required=False)
    reason_note = serializers.CharField(required=False, allow_blank=True)
    evidence_links = serializers.ListField(
        child=serializers.URLField(),
        required=False,
        allow_empty=True,
    )


class AppointmentPublishSerializer(serializers.Serializer):
    publication_reference = serializers.CharField(required=False, allow_blank=True, max_length=150)
    publication_document_hash = serializers.CharField(required=False, allow_blank=True, max_length=128)
    publication_notes = serializers.CharField(required=False, allow_blank=True)
    gazette_number = serializers.CharField(required=False, allow_blank=True, max_length=100)
    gazette_date = serializers.DateField(required=False)

    def validate_publication_document_hash(self, value):
        normalized = (value or "").strip().lower()
        if not normalized:
            return ""
        if len(normalized) not in {64, 128}:
            raise serializers.ValidationError("publication_document_hash must be 64 or 128 hex characters when provided.")
        if any(char not in "0123456789abcdef" for char in normalized):
            raise serializers.ValidationError("publication_document_hash must be hexadecimal.")
        return normalized


class AppointmentRevokePublicationSerializer(serializers.Serializer):
    revocation_reason = serializers.CharField(required=True, allow_blank=False)
    make_private = serializers.BooleanField(required=False, default=True)


class AppointmentPublicationSerializer(serializers.ModelSerializer):
    published_by_email = serializers.EmailField(source="published_by.email", read_only=True)
    revoked_by_email = serializers.EmailField(source="revoked_by.email", read_only=True)

    class Meta:
        model = AppointmentPublication
        fields = [
            "id",
            "appointment",
            "status",
            "publication_reference",
            "publication_document_hash",
            "publication_notes",
            "published_by",
            "published_by_email",
            "published_at",
            "revoked_by",
            "revoked_by_email",
            "revoked_at",
            "revocation_reason",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class PublicAppointmentRecordSerializer(serializers.ModelSerializer):
    position_title = serializers.CharField(source="position.title", read_only=True)
    institution = serializers.CharField(source="position.institution", read_only=True)
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
            "institution",
            "nominee_name",
            "nominated_by_display",
            "nominated_by_org",
            "appointment_date",
            "gazette_number",
            "gazette_date",
            "status",
            "publication_status",
            "publication_reference",
            "published_at",
        ]
