from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from rest_framework import serializers

from .models import Invitation


class InvitationSerializer(serializers.ModelSerializer):
    accept_url = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Invitation
        fields = [
            "id",
            "enrollment",
            "token",
            "channel",
            "status",
            "send_to",
            "expires_at",
            "sent_at",
            "accepted_at",
            "attempts",
            "last_error",
            "created_by",
            "created_at",
            "updated_at",
            "accept_url",
        ]
        read_only_fields = [
            "id",
            "token",
            "status",
            "send_to",
            "sent_at",
            "accepted_at",
            "attempts",
            "last_error",
            "created_by",
            "created_at",
            "updated_at",
            "accept_url",
        ]

    def get_accept_url(self, obj):
        frontend_url = getattr(settings, "FRONTEND_URL", "http://localhost:3000")
        return f"{frontend_url.rstrip('/')}/invite/{obj.token}"


class InvitationCreateSerializer(serializers.ModelSerializer):
    expires_in_hours = serializers.IntegerField(min_value=1, max_value=720, default=72, write_only=True)

    class Meta:
        model = Invitation
        fields = ["id", "enrollment", "channel", "expires_in_hours"]
        read_only_fields = ["id"]

    def create(self, validated_data):
        expires_in_hours = validated_data.pop("expires_in_hours", 72)
        enrollment = validated_data["enrollment"]

        if validated_data["channel"] == "sms" and not enrollment.candidate.phone_number:
            raise serializers.ValidationError("Candidate has no phone number for SMS invitation.")

        send_to = enrollment.candidate.phone_number if validated_data["channel"] == "sms" else enrollment.candidate.email
        validated_data["send_to"] = send_to
        validated_data["expires_at"] = timezone.now() + timedelta(hours=expires_in_hours)

        return super().create(validated_data)


class AcceptInvitationSerializer(serializers.Serializer):
    token = serializers.UUIDField()
