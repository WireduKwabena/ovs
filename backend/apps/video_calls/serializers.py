from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import serializers

from apps.video_calls.models import VideoMeeting, VideoMeetingEvent, VideoMeetingParticipant

User = get_user_model()


class VideoMeetingParticipantSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source="user.email", read_only=True)
    user_full_name = serializers.SerializerMethodField()
    user_type = serializers.CharField(source="user.user_type", read_only=True)

    class Meta:
        model = VideoMeetingParticipant
        fields = [
            "id",
            "user",
            "user_email",
            "user_full_name",
            "user_type",
            "role",
            "status",
            "invited_at",
            "joined_at",
            "left_at",
        ]
        read_only_fields = [
            "id",
            "status",
            "invited_at",
            "joined_at",
            "left_at",
        ]

    def get_user_full_name(self, obj) -> str:
        return obj.user.get_full_name() or obj.user.email


class VideoMeetingSerializer(serializers.ModelSerializer):
    participants = VideoMeetingParticipantSerializer(many=True, read_only=True)
    participant_user_ids = serializers.ListField(
        child=serializers.UUIDField(),
        write_only=True,
        required=False,
        allow_empty=True,
    )
    participant_emails = serializers.ListField(
        child=serializers.EmailField(),
        write_only=True,
        required=False,
        allow_empty=True,
    )
    organizer_email = serializers.EmailField(source="organizer.email", read_only=True)
    organizer_name = serializers.SerializerMethodField()

    class Meta:
        model = VideoMeeting
        fields = [
            "id",
            "series_id",
            "organizer",
            "organizer_email",
            "organizer_name",
            "case",
            "title",
            "description",
            "status",
            "scheduled_start",
            "scheduled_end",
            "timezone",
            "livekit_room_name",
            "allow_join_before_seconds",
            "reminder_before_minutes",
            "cancellation_reason",
            "reminder_before_sent_at",
            "reminder_start_sent_at",
            "created_at",
            "updated_at",
            "participants",
            "participant_user_ids",
            "participant_emails",
        ]
        read_only_fields = [
            "id",
            "series_id",
            "organizer",
            "organizer_email",
            "organizer_name",
            "status",
            "livekit_room_name",
            "reminder_before_sent_at",
            "reminder_start_sent_at",
            "created_at",
            "updated_at",
            "participants",
        ]

    def get_organizer_name(self, obj) -> str:
        return obj.organizer.get_full_name() or obj.organizer.email

    def validate(self, attrs):
        scheduled_start = attrs.get("scheduled_start", getattr(self.instance, "scheduled_start", None))
        scheduled_end = attrs.get("scheduled_end", getattr(self.instance, "scheduled_end", None))
        if scheduled_start and scheduled_end and scheduled_end <= scheduled_start:
            raise serializers.ValidationError("scheduled_end must be after scheduled_start.")
        if scheduled_start and scheduled_end and (scheduled_end - scheduled_start) > timedelta(hours=8):
            raise serializers.ValidationError("Meeting duration cannot exceed 8 hours.")
        if scheduled_start and scheduled_start < timezone.now() - timedelta(minutes=1):
            raise serializers.ValidationError("scheduled_start cannot be in the past.")
        if self.instance is None:
            case = attrs.get("case")
            participant_user_ids = attrs.get("participant_user_ids")
            participant_emails = attrs.get("participant_emails")
            if case is None and not participant_user_ids and not participant_emails:
                raise serializers.ValidationError(
                    "Provide a vetting case or explicit participants (ids/emails) when scheduling a meeting."
                )
        return attrs

    def _resolve_participants(
        self,
        *,
        meeting: VideoMeeting,
        user_ids: list[str] | None,
        emails: list[str] | None,
        organizer,
    ):
        unique_user_ids = {str(user_id) for user_id in (user_ids or []) if str(user_id).strip()}
        normalized_emails = {
            str(email).strip().lower() for email in (emails or []) if str(email).strip()
        }

        unique_user_ids.add(str(organizer.id))
        normalized_emails.add(str(organizer.email).strip().lower())

        if meeting.case_id and getattr(meeting.case, "applicant_id", None):
            unique_user_ids.add(str(meeting.case.applicant_id))
            candidate_email = str(getattr(meeting.case.applicant, "email", "")).strip().lower()
            if candidate_email:
                normalized_emails.add(candidate_email)

        users_by_id = User.objects.filter(id__in=unique_user_ids)
        users_by_email = User.objects.filter(email__in=normalized_emails)
        users = list(users_by_id) + list(users_by_email)
        deduped_users: dict[str, User] = {str(user.id): user for user in users}

        found_ids = {str(user.id) for user in deduped_users.values()}
        missing_ids = unique_user_ids - found_ids
        if missing_ids:
            raise serializers.ValidationError(
                {"participant_user_ids": f"Unknown users: {', '.join(sorted(missing_ids))}"}
            )

        found_emails = {str(user.email).strip().lower() for user in deduped_users.values()}
        missing_emails = normalized_emails - found_emails
        if missing_emails:
            raise serializers.ValidationError(
                {"participant_emails": f"Unknown users: {', '.join(sorted(missing_emails))}"}
            )

        return list(deduped_users.values())

    def _sync_participants(
        self,
        meeting: VideoMeeting,
        user_ids: list[str] | None,
        emails: list[str] | None,
        organizer,
    ):
        users = self._resolve_participants(
            meeting=meeting,
            user_ids=user_ids,
            emails=emails,
            organizer=organizer,
        )

        # Remove users no longer invited, but keep organizer.
        found_ids = {str(user.id) for user in users}
        meeting.participants.exclude(user_id__in=found_ids).exclude(user=organizer).delete()

        for user in users:
            role = VideoMeetingParticipant.ROLE_HOST if str(user.id) == str(organizer.id) else VideoMeetingParticipant.ROLE_CANDIDATE
            VideoMeetingParticipant.objects.update_or_create(
                meeting=meeting,
                user=user,
                defaults={"role": role},
            )

    def create(self, validated_data):
        participant_user_ids = validated_data.pop("participant_user_ids", None)
        participant_emails = validated_data.pop("participant_emails", None)
        organizer = self.context["request"].user
        meeting = VideoMeeting.objects.create(organizer=organizer, **validated_data)
        self._sync_participants(
            meeting,
            participant_user_ids,
            participant_emails,
            organizer,
        )
        return meeting

    def update(self, instance, validated_data):
        participant_user_ids = validated_data.pop("participant_user_ids", None)
        participant_emails = validated_data.pop("participant_emails", None)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        self._sync_participants(
            instance,
            participant_user_ids,
            participant_emails,
            instance.organizer,
        )
        return instance


class VideoMeetingRescheduleSerializer(serializers.Serializer):
    scheduled_start = serializers.DateTimeField()
    scheduled_end = serializers.DateTimeField()
    timezone = serializers.CharField(required=False, allow_blank=True, max_length=64)

    def validate(self, attrs):
        if attrs["scheduled_end"] <= attrs["scheduled_start"]:
            raise serializers.ValidationError("scheduled_end must be after scheduled_start.")
        if attrs["scheduled_start"] < timezone.now() - timedelta(minutes=1):
            raise serializers.ValidationError("scheduled_start cannot be in the past.")
        if (attrs["scheduled_end"] - attrs["scheduled_start"]) > timedelta(hours=8):
            raise serializers.ValidationError("Meeting duration cannot exceed 8 hours.")
        return attrs


class VideoMeetingExtendSerializer(serializers.Serializer):
    minutes = serializers.IntegerField(min_value=1, max_value=240)


class VideoMeetingJoinTokenSerializer(serializers.Serializer):
    token = serializers.CharField()
    ws_url = serializers.CharField()
    room_name = serializers.CharField()
    expires_in = serializers.IntegerField()


class VideoMeetingSeriesRequestSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, allow_blank=True)
    case = serializers.UUIDField(required=False, allow_null=True)
    scheduled_start = serializers.DateTimeField()
    scheduled_end = serializers.DateTimeField()
    timezone = serializers.CharField(required=False, allow_blank=True, max_length=64, default="UTC")
    allow_join_before_seconds = serializers.IntegerField(required=False, min_value=0, default=300)
    reminder_before_minutes = serializers.IntegerField(required=False, min_value=1, max_value=120, default=15)
    participant_user_ids = serializers.ListField(
        child=serializers.UUIDField(),
        write_only=True,
        required=False,
        allow_empty=True,
    )
    participant_emails = serializers.ListField(
        child=serializers.EmailField(),
        write_only=True,
        required=False,
        allow_empty=True,
    )
    recurrence = serializers.ChoiceField(
        choices=[("none", "None"), ("daily", "Daily"), ("weekly", "Weekly")],
        default="weekly",
    )
    occurrences = serializers.IntegerField(min_value=1, max_value=12, default=2)

    def validate(self, attrs):
        start = attrs["scheduled_start"]
        end = attrs["scheduled_end"]
        if end <= start:
            raise serializers.ValidationError("scheduled_end must be after scheduled_start.")
        if (end - start) > timedelta(hours=8):
            raise serializers.ValidationError("Meeting duration cannot exceed 8 hours.")
        if start < timezone.now() - timedelta(minutes=1):
            raise serializers.ValidationError("scheduled_start cannot be in the past.")

        recurrence = attrs.get("recurrence", "none")
        occurrences = int(attrs.get("occurrences", 1))
        if recurrence == "none" and occurrences != 1:
            raise serializers.ValidationError({"occurrences": "Set occurrences=1 when recurrence is 'none'."})

        case = attrs.get("case")
        if case is None and not attrs.get("participant_user_ids") and not attrs.get("participant_emails"):
            raise serializers.ValidationError(
                "Provide a vetting case or explicit participants (ids/emails) when scheduling a meeting."
            )

        return attrs


class VideoMeetingSeriesResponseSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    results = VideoMeetingSerializer(many=True)


class VideoMeetingSeriesRescheduleSerializer(serializers.Serializer):
    scheduled_start = serializers.DateTimeField()
    scheduled_end = serializers.DateTimeField()
    timezone = serializers.CharField(required=False, allow_blank=True, max_length=64)
    scope = serializers.ChoiceField(choices=[("future", "Future"), ("all", "All")], default="future")

    def validate(self, attrs):
        if attrs["scheduled_end"] <= attrs["scheduled_start"]:
            raise serializers.ValidationError("scheduled_end must be after scheduled_start.")
        if attrs["scheduled_start"] < timezone.now() - timedelta(minutes=1):
            raise serializers.ValidationError("scheduled_start cannot be in the past.")
        if (attrs["scheduled_end"] - attrs["scheduled_start"]) > timedelta(hours=8):
            raise serializers.ValidationError("Meeting duration cannot exceed 8 hours.")
        return attrs


class VideoMeetingSeriesCancelSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, max_length=2000)
    scope = serializers.ChoiceField(choices=[("future", "Future"), ("all", "All")], default="future")


class VideoMeetingEventSerializer(serializers.ModelSerializer):
    actor_email = serializers.EmailField(source="actor.email", read_only=True)
    actor_name = serializers.SerializerMethodField()
    actor_user_type = serializers.CharField(source="actor.user_type", read_only=True)

    class Meta:
        model = VideoMeetingEvent
        fields = [
            "id",
            "meeting",
            "actor",
            "actor_email",
            "actor_name",
            "actor_user_type",
            "action",
            "scope",
            "detail",
            "metadata",
            "created_at",
        ]
        read_only_fields = fields

    def get_actor_name(self, obj) -> str:
        if obj.actor is None:
            return "System"
        return obj.actor.get_full_name() or obj.actor.email
