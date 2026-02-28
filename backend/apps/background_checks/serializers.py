from rest_framework import serializers

from .models import BackgroundCheck, BackgroundCheckEvent
from .services import available_provider_keys


class BackgroundCheckEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = BackgroundCheckEvent
        fields = [
            "id",
            "event_type",
            "status_before",
            "status_after",
            "payload",
            "message",
            "created_at",
        ]


class BackgroundCheckSerializer(serializers.ModelSerializer):
    case_id = serializers.CharField(source="case.case_id", read_only=True)
    applicant_email = serializers.CharField(source="case.applicant.email", read_only=True)
    submitted_by_email = serializers.CharField(source="submitted_by.email", read_only=True)

    class Meta:
        model = BackgroundCheck
        fields = [
            "id",
            "case",
            "case_id",
            "applicant_email",
            "check_type",
            "provider_key",
            "status",
            "external_reference",
            "score",
            "risk_level",
            "recommendation",
            "request_payload",
            "response_payload",
            "result_summary",
            "consent_evidence",
            "submitted_by",
            "submitted_by_email",
            "error_code",
            "error_message",
            "submitted_at",
            "last_polled_at",
            "webhook_received_at",
            "completed_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "case_id",
            "applicant_email",
            "submitted_by_email",
            "status",
            "external_reference",
            "score",
            "risk_level",
            "recommendation",
            "response_payload",
            "result_summary",
            "submitted_by",
            "error_code",
            "error_message",
            "submitted_at",
            "last_polled_at",
            "webhook_received_at",
            "completed_at",
            "created_at",
            "updated_at",
        ]


class BackgroundCheckCreateSerializer(serializers.ModelSerializer):
    run_async = serializers.BooleanField(default=False, required=False, write_only=True)

    class Meta:
        model = BackgroundCheck
        fields = [
            "case",
            "check_type",
            "provider_key",
            "request_payload",
            "consent_evidence",
            "run_async",
        ]

    def validate_provider_key(self, value):
        providers = set(available_provider_keys())
        if value and value not in providers:
            raise serializers.ValidationError(
                f"Unsupported provider '{value}'. Allowed: {', '.join(sorted(providers))}."
            )
        return value


class ProviderWebhookSerializer(serializers.Serializer):
    external_reference = serializers.CharField(required=False, allow_blank=False)
    reference = serializers.CharField(required=False, allow_blank=False)
    status = serializers.CharField(required=False, allow_blank=True)
    score = serializers.FloatField(required=False)
    risk_level = serializers.CharField(required=False, allow_blank=True)
    recommendation = serializers.CharField(required=False, allow_blank=True)
    completed_at = serializers.DateTimeField(required=False)
