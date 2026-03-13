from django.utils import timezone
from rest_framework import serializers

from .models import AppointmentPublication, AppointmentRecord, AppointmentStageAction, ApprovalStage, ApprovalStageTemplate
from .public_serializers import PublicAppointmentRecordSerializer


class ApprovalStageSerializer(serializers.ModelSerializer):
    committee_name = serializers.CharField(source="committee.name", read_only=True)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        instance = getattr(self, "instance", None)
        template = attrs.get("template") or getattr(instance, "template", None)
        committee = attrs.get("committee") if "committee" in attrs else getattr(instance, "committee", None)

        if committee is None:
            return attrs
        if not committee.is_active:
            raise serializers.ValidationError({"committee": "Assigned committee must be active."})

        if template is not None and template.organization_id and committee.organization_id:
            if str(template.organization_id) != str(committee.organization_id):
                raise serializers.ValidationError({"committee": "Committee organization must match template organization."})
        return attrs

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
            "committee",
            "committee_name",
        ]
        read_only_fields = ["id", "committee_name"]


class ApprovalStageTemplateSerializer(serializers.ModelSerializer):
    stages = ApprovalStageSerializer(many=True, read_only=True)
    organization_name = serializers.CharField(source="organization.name", read_only=True)

    class Meta:
        model = ApprovalStageTemplate
        fields = ["id", "organization", "organization_name", "name", "exercise_type", "created_by", "created_at", "stages"]
        read_only_fields = ["id", "organization_name", "created_by", "created_at", "stages"]


class AppointmentStageActionSerializer(serializers.ModelSerializer):
    actor_email = serializers.EmailField(source="actor.email", read_only=True)
    stage_name = serializers.CharField(source="stage.name", read_only=True)
    committee_membership_id = serializers.UUIDField(source="committee_membership.id", read_only=True)
    committee_name = serializers.CharField(source="committee_membership.committee.name", read_only=True)
    committee_role = serializers.CharField(source="committee_membership.committee_role", read_only=True)

    class Meta:
        model = AppointmentStageAction
        fields = [
            "id",
            "appointment",
            "stage",
            "stage_name",
            "actor",
            "actor_email",
            "committee_membership",
            "committee_membership_id",
            "committee_name",
            "committee_role",
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
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    committee_name = serializers.CharField(source="committee.name", read_only=True)
    position_title = serializers.CharField(source="position.title", read_only=True)
    nominee_name = serializers.CharField(source="nominee.full_name", read_only=True)
    nomination_file_id = serializers.UUIDField(source="id", read_only=True)
    nomination_file_status = serializers.CharField(source="status", read_only=True)
    office_id = serializers.UUIDField(source="position_id", read_only=True)
    office_name = serializers.CharField(source="position.title", read_only=True)
    appointment_exercise_id = serializers.UUIDField(read_only=True, allow_null=True)
    appointment_exercise_name = serializers.CharField(source="appointment_exercise.name", read_only=True, allow_null=True)
    vetting_dossier_id = serializers.UUIDField(source="vetting_case_id", read_only=True, allow_null=True)
    appointment_route_template_id = serializers.UUIDField(
        source="appointment_exercise.approval_template_id",
        read_only=True,
        allow_null=True,
    )
    vetting_decision = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = AppointmentRecord
        fields = [
            "id",
            "nomination_file_id",
            "organization",
            "organization_name",
            "committee",
            "committee_name",
            "position",
            "position_title",
            "office_id",
            "office_name",
            "nominee",
            "nominee_name",
            "appointment_exercise",
            "appointment_exercise_id",
            "appointment_exercise_name",
            "appointment_route_template_id",
            "nominated_by_user",
            "nominated_by_display",
            "nominated_by_org",
            "nomination_date",
            "vetting_case",
            "vetting_dossier_id",
            "vetting_decision",
            "status",
            "nomination_file_status",
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
        read_only_fields = ["id", "organization_name", "committee_name", "status", "created_at", "updated_at"]

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
        organization = attrs.get("organization") or getattr(instance, "organization", None)
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
        committee = attrs.get("committee") if "committee" in attrs else getattr(instance, "committee", None)

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

        if organization is not None and position is not None and position.organization_id:
            if str(position.organization_id) != str(organization.id):
                add_error("organization", "Organization must match selected position organization.")

        if organization is not None and appointment_exercise is not None and appointment_exercise.organization_id:
            if str(appointment_exercise.organization_id) != str(organization.id):
                add_error("organization", "Organization must match selected appointment exercise organization.")

        if vetting_case is not None and appointment_exercise is not None:
            enrollment = getattr(vetting_case, "candidate_enrollment", None)
            if enrollment is not None and enrollment.campaign_id != appointment_exercise.id:
                add_error("vetting_case", "Selected vetting case belongs to a different campaign than appointment exercise.")

        if organization is not None and vetting_case is not None and vetting_case.organization_id:
            if str(vetting_case.organization_id) != str(organization.id):
                add_error("organization", "Organization must match selected vetting case organization.")

        if committee is not None:
            if not committee.is_active:
                add_error("committee", "Assigned committee must be active.")
            if organization is not None and committee.organization_id:
                if str(committee.organization_id) != str(organization.id):
                    add_error("committee", "Assigned committee organization must match appointment organization.")
            if appointment_exercise is not None and appointment_exercise.organization_id and committee.organization_id:
                if str(appointment_exercise.organization_id) != str(committee.organization_id):
                    add_error("committee", "Assigned committee organization must match appointment exercise organization.")

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

    def get_vetting_decision(self, obj):
        linked_case = getattr(obj, "vetting_case", None)
        if linked_case is None:
            return None
        evaluation = getattr(linked_case, "rubric_evaluation", None)
        if evaluation is None:
            return None
        recommendation = (
            evaluation.decision_recommendations.filter(is_latest=True)
            .order_by("-created_at")
            .first()
        )
        if recommendation is None:
            return None
        blocking_issues = recommendation.blocking_issues if isinstance(recommendation.blocking_issues, list) else []
        warnings = recommendation.warnings if isinstance(recommendation.warnings, list) else []
        return {
            "id": recommendation.id,
            "recommendation_status": recommendation.recommendation_status,
            "advisory_only": recommendation.advisory_only,
            "blocking_issues_count": len(blocking_issues),
            "warnings_count": len(warnings),
            "has_override": recommendation.overrides.exists(),
            "updated_at": recommendation.updated_at,
        }


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
