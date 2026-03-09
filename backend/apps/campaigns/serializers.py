from rest_framework import serializers

from apps.applications.models import Document

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
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    position_ids = serializers.PrimaryKeyRelatedField(source="positions", many=True, read_only=True)
    required_document_types = serializers.ListField(
        child=serializers.ChoiceField(choices=[choice[0] for choice in Document.DOCUMENT_TYPE_CHOICES]),
        required=False,
        allow_empty=True,
        help_text="Explicit document types required for this campaign.",
    )

    def validate_required_document_types(self, value):
        normalized = []
        for item in value:
            if item not in normalized:
                normalized.append(item)
        return normalized

    def validate(self, attrs):
        attrs = super().validate(attrs)
        instance = getattr(self, "instance", None)
        organization = attrs.get("organization") or getattr(instance, "organization", None)
        approval_template = attrs.get("approval_template") if "approval_template" in attrs else getattr(
            instance, "approval_template", None
        )
        if organization is not None and approval_template is not None and approval_template.organization_id:
            if str(approval_template.organization_id) != str(organization.id):
                raise serializers.ValidationError(
                    {"approval_template": "Approval template organization must match campaign organization."}
                )
        return attrs

    def _merge_required_document_types(self, validated_data, required_document_types):
        if required_document_types is None:
            return
        settings_json = validated_data.get("settings_json")
        if not isinstance(settings_json, dict):
            settings_json = {}
        else:
            settings_json = dict(settings_json)
        settings_json["required_document_types"] = required_document_types
        validated_data["settings_json"] = settings_json

    def create(self, validated_data):
        required_document_types = validated_data.pop("required_document_types", None)
        self._merge_required_document_types(validated_data, required_document_types)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        required_document_types = validated_data.pop("required_document_types", None)
        if required_document_types is not None:
            instance_settings = instance.settings_json if isinstance(instance.settings_json, dict) else {}
            incoming_settings = validated_data.get("settings_json")
            merged_settings = dict(instance_settings)
            if isinstance(incoming_settings, dict):
                merged_settings.update(incoming_settings)
            merged_settings["required_document_types"] = required_document_types
            validated_data["settings_json"] = merged_settings
        return super().update(instance, validated_data)

    def to_representation(self, instance):
        payload = super().to_representation(instance)
        settings_json = instance.settings_json if isinstance(instance.settings_json, dict) else {}
        raw_required_types = settings_json.get("required_document_types")
        if not isinstance(raw_required_types, list):
            payload["required_document_types"] = []
            return payload

        allowed_types = {choice[0] for choice in Document.DOCUMENT_TYPE_CHOICES}
        normalized = []
        for item in raw_required_types:
            value = str(item)
            if value in allowed_types and value not in normalized:
                normalized.append(value)
        payload["required_document_types"] = normalized
        return payload

    class Meta:
        model = VettingCampaign
        fields = [
            "id",
            "organization",
            "organization_name",
            "name",
            "description",
            "status",
            "starts_at",
            "ends_at",
            "settings_json",
            "exercise_type",
            "jurisdiction",
            "positions",
            "position_ids",
            "approval_template",
            "appointment_authority",
            "requires_parliamentary_confirmation",
            "gazette_reference",
            "required_document_types",
            "initiated_by",
            "initiated_by_email",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "initiated_by", "initiated_by_email", "organization_name", "created_at", "updated_at"]


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
