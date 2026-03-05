from __future__ import annotations

import uuid
from datetime import timedelta

from django.conf import settings
from django.http import HttpResponse
from django.db import transaction
from django.db.models import Q
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.text import slugify
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.video_calls.models import VideoMeeting, VideoMeetingEvent, VideoMeetingParticipant
from apps.video_calls.permissions import IsMeetingCreatorOrReadOnly, is_admin_user, is_hr_or_admin_user
from apps.video_calls.serializers import (
    VideoMeetingExtendSerializer,
    VideoMeetingEventSerializer,
    VideoMeetingJoinTokenSerializer,
    VideoMeetingRescheduleSerializer,
    VideoMeetingSeriesCancelSerializer,
    VideoMeetingSeriesRequestSerializer,
    VideoMeetingSeriesRescheduleSerializer,
    VideoMeetingSeriesResponseSerializer,
    VideoMeetingSerializer,
)
from apps.video_calls.services import (
    build_meeting_ics_content,
    build_livekit_join_token,
    notify_meeting_cancelled,
    notify_meeting_created,
    notify_meeting_time_up,
    notify_meeting_updated,
)

try:
    from drf_spectacular.utils import extend_schema
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    def extend_schema(*args, **kwargs):  # type: ignore[override]
        def decorator(func):
            return func

        return decorator


class VideoMeetingViewSet(viewsets.ModelViewSet):
    serializer_class = VideoMeetingSerializer
    permission_classes = [IsAuthenticated, IsMeetingCreatorOrReadOnly]

    def get_serializer_class(self):
        if self.action == "schedule_series":
            return VideoMeetingSeriesRequestSerializer
        return super().get_serializer_class()

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return VideoMeeting.objects.none()

        queryset = VideoMeeting.objects.select_related("organizer", "case").prefetch_related("participants__user")
        user = self.request.user
        status_filter = self.request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        if is_hr_or_admin_user(user):
            return queryset.order_by("scheduled_start", "-created_at")

        return queryset.filter(
            Q(organizer=user) | Q(participants__user=user)
        ).distinct().order_by("scheduled_start", "-created_at")

    def perform_create(self, serializer):
        meeting = serializer.save()
        self._log_meeting_event(
            meeting=meeting,
            action=VideoMeetingEvent.ACTION_CREATED,
            scope=VideoMeetingEvent.SCOPE_SINGLE,
            detail="Meeting scheduled.",
        )
        notify_meeting_created(meeting)

    def _series_meetings_queryset(self, *, meeting: VideoMeeting, scope: str):
        queryset = VideoMeeting.objects.filter(series_id=meeting.series_id)
        if scope == "future":
            queryset = queryset.filter(scheduled_start__gte=meeting.scheduled_start)
        return queryset.order_by("scheduled_start", "created_at")

    def _log_meeting_event(
        self,
        *,
        meeting: VideoMeeting,
        action: str,
        scope: str = VideoMeetingEvent.SCOPE_SINGLE,
        detail: str = "",
        metadata: dict | None = None,
    ) -> None:
        VideoMeetingEvent.objects.create(
            meeting=meeting,
            actor=self.request.user if getattr(self.request, "user", None) and self.request.user.is_authenticated else None,
            action=action,
            scope=scope,
            detail=detail,
            metadata=metadata or {},
        )

    def _normalize_event_scope(self, scope: str) -> str:
        if scope == "future":
            return VideoMeetingEvent.SCOPE_FUTURE
        if scope == "all":
            return VideoMeetingEvent.SCOPE_ALL
        return VideoMeetingEvent.SCOPE_SINGLE

    @extend_schema(
        request=VideoMeetingSeriesRequestSerializer,
        responses={201: VideoMeetingSeriesResponseSerializer},
    )
    @action(detail=False, methods=["post"], url_path="schedule-series")
    def schedule_series(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated = serializer.validated_data

        recurrence = validated["recurrence"]
        occurrences = int(validated["occurrences"])
        day_step = 0 if recurrence == "none" else (1 if recurrence == "daily" else 7)

        base_start = validated["scheduled_start"]
        base_end = validated["scheduled_end"]

        series_identifier = uuid.uuid4() if recurrence != "none" and occurrences > 1 else None
        meetings: list[VideoMeeting] = []
        create_context = self.get_serializer_context()
        with transaction.atomic():
            for offset_index in range(occurrences):
                offset_days = day_step * offset_index
                payload = {
                    "title": validated["title"],
                    "description": validated.get("description", ""),
                    "case": validated.get("case"),
                    "scheduled_start": base_start + timedelta(days=offset_days),
                    "scheduled_end": base_end + timedelta(days=offset_days),
                    "timezone": validated.get("timezone") or "UTC",
                    "allow_join_before_seconds": validated.get("allow_join_before_seconds", 300),
                    "reminder_before_minutes": validated.get("reminder_before_minutes", 15),
                    "participant_user_ids": validated.get("participant_user_ids", []),
                    "participant_emails": validated.get("participant_emails", []),
                }

                create_serializer = VideoMeetingSerializer(data=payload, context=create_context)
                create_serializer.is_valid(raise_exception=True)
                meeting = create_serializer.save()
                if series_identifier:
                    meeting.series_id = series_identifier
                    meeting.save(update_fields=["series_id", "updated_at"])
                self._log_meeting_event(
                    meeting=meeting,
                    action=VideoMeetingEvent.ACTION_CREATED,
                    scope=VideoMeetingEvent.SCOPE_ALL if series_identifier else VideoMeetingEvent.SCOPE_SINGLE,
                    detail="Meeting created via recurring schedule." if series_identifier else "Meeting scheduled.",
                    metadata={
                        "recurrence": recurrence,
                        "occurrences": occurrences,
                        "index": offset_index + 1,
                    },
                )
                notify_meeting_created(meeting)
                meetings.append(meeting)

        response_payload = {"count": len(meetings), "results": meetings}
        response_serializer = VideoMeetingSeriesResponseSerializer(response_payload, context=create_context)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    @extend_schema(
        request=VideoMeetingSeriesRescheduleSerializer,
        responses={200: VideoMeetingSeriesResponseSerializer},
    )
    @action(detail=True, methods=["post"], url_path="reschedule-series")
    def reschedule_series(self, request, pk=None):
        meeting = self.get_object()
        if not meeting.series_id:
            return Response({"error": "Meeting is not part of a series."}, status=status.HTTP_400_BAD_REQUEST)

        serializer = VideoMeetingSeriesRescheduleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        scope = serializer.validated_data["scope"]
        targets = list(self._series_meetings_queryset(meeting=meeting, scope=scope).filter(status=VideoMeeting.STATUS_SCHEDULED))
        if not targets:
            return Response({"error": "No scheduled meetings found for selected series scope."}, status=status.HTTP_400_BAD_REQUEST)

        base_start = serializer.validated_data["scheduled_start"]
        base_end = serializer.validated_data["scheduled_end"]
        new_timezone = serializer.validated_data.get("timezone")

        updated: list[VideoMeeting] = []
        with transaction.atomic():
            for target in targets:
                previous_start = target.scheduled_start
                previous_end = target.scheduled_end
                delta = target.scheduled_start - meeting.scheduled_start
                target.scheduled_start = base_start + delta
                target.scheduled_end = base_end + delta
                if new_timezone:
                    target.timezone = new_timezone
                target.status = VideoMeeting.STATUS_SCHEDULED
                target.reminder_before_sent_at = None
                target.reminder_before_failure_count = 0
                target.reminder_before_last_failure_at = None
                target.reminder_before_next_retry_at = None
                target.reminder_start_sent_at = None
                target.reminder_start_failure_count = 0
                target.reminder_start_last_failure_at = None
                target.reminder_start_next_retry_at = None
                target.reminder_time_up_sent_at = None
                target.reminder_time_up_failure_count = 0
                target.reminder_time_up_last_failure_at = None
                target.reminder_time_up_next_retry_at = None
                try:
                    target.save(
                        update_fields=[
                            "scheduled_start",
                            "scheduled_end",
                            "timezone",
                            "status",
                            "reminder_before_sent_at",
                            "reminder_before_failure_count",
                            "reminder_before_last_failure_at",
                            "reminder_before_next_retry_at",
                            "reminder_start_sent_at",
                            "reminder_start_failure_count",
                            "reminder_start_last_failure_at",
                            "reminder_start_next_retry_at",
                            "reminder_time_up_sent_at",
                            "reminder_time_up_failure_count",
                            "reminder_time_up_last_failure_at",
                            "reminder_time_up_next_retry_at",
                            "updated_at",
                        ]
                    )
                except DjangoValidationError as exc:
                    return Response(
                        {"error": exc.message_dict if hasattr(exc, "message_dict") else exc.messages},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                self._log_meeting_event(
                    meeting=target,
                    action=VideoMeetingEvent.ACTION_RESCHEDULED,
                    scope=self._normalize_event_scope(scope),
                    detail="Series reschedule applied.",
                    metadata={
                        "previous_start": previous_start.isoformat(),
                        "previous_end": previous_end.isoformat(),
                        "new_start": target.scheduled_start.isoformat(),
                        "new_end": target.scheduled_end.isoformat(),
                        "timezone": target.timezone,
                    },
                )
                notify_meeting_updated(target)
                updated.append(target)

        response_serializer = VideoMeetingSeriesResponseSerializer({"count": len(updated), "results": updated}, context=self.get_serializer_context())
        return Response(response_serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        request=VideoMeetingSeriesCancelSerializer,
        responses={200: VideoMeetingSeriesResponseSerializer},
    )
    @action(detail=True, methods=["post"], url_path="cancel-series")
    def cancel_series(self, request, pk=None):
        meeting = self.get_object()
        if not meeting.series_id:
            return Response({"error": "Meeting is not part of a series."}, status=status.HTTP_400_BAD_REQUEST)

        serializer = VideoMeetingSeriesCancelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        scope = serializer.validated_data["scope"]
        reason = str(serializer.validated_data.get("reason", "")).strip()

        targets = list(
            self._series_meetings_queryset(meeting=meeting, scope=scope).filter(
                status__in=[VideoMeeting.STATUS_SCHEDULED, VideoMeeting.STATUS_ONGOING]
            )
        )
        if not targets:
            return Response({"error": "No open meetings found for selected series scope."}, status=status.HTTP_400_BAD_REQUEST)

        cancelled: list[VideoMeeting] = []
        with transaction.atomic():
            for target in targets:
                try:
                    target.mark_cancelled(reason=reason)
                except DjangoValidationError as exc:
                    return Response(
                        {"error": exc.message_dict if hasattr(exc, "message_dict") else exc.messages},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                self._log_meeting_event(
                    meeting=target,
                    action=VideoMeetingEvent.ACTION_CANCELLED,
                    scope=self._normalize_event_scope(scope),
                    detail=reason or "Series cancellation applied.",
                    metadata={"reason": reason},
                )
                notify_meeting_cancelled(target)
                cancelled.append(target)

        response_serializer = VideoMeetingSeriesResponseSerializer({"count": len(cancelled), "results": cancelled}, context=self.get_serializer_context())
        return Response(response_serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="reschedule")
    def reschedule(self, request, pk=None):
        meeting = self.get_object()
        if meeting.status != VideoMeeting.STATUS_SCHEDULED:
            return Response(
                {"error": "Only scheduled meetings can be rescheduled."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = VideoMeetingRescheduleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        previous_start = meeting.scheduled_start
        previous_end = meeting.scheduled_end
        meeting.scheduled_start = serializer.validated_data["scheduled_start"]
        meeting.scheduled_end = serializer.validated_data["scheduled_end"]
        if serializer.validated_data.get("timezone"):
            meeting.timezone = serializer.validated_data["timezone"]
        meeting.status = VideoMeeting.STATUS_SCHEDULED
        meeting.reminder_before_sent_at = None
        meeting.reminder_before_failure_count = 0
        meeting.reminder_before_last_failure_at = None
        meeting.reminder_before_next_retry_at = None
        meeting.reminder_start_sent_at = None
        meeting.reminder_start_failure_count = 0
        meeting.reminder_start_last_failure_at = None
        meeting.reminder_start_next_retry_at = None
        meeting.reminder_time_up_sent_at = None
        meeting.reminder_time_up_failure_count = 0
        meeting.reminder_time_up_last_failure_at = None
        meeting.reminder_time_up_next_retry_at = None
        try:
            meeting.save(
                update_fields=[
                    "scheduled_start",
                    "scheduled_end",
                    "timezone",
                    "status",
                    "reminder_before_sent_at",
                    "reminder_before_failure_count",
                    "reminder_before_last_failure_at",
                    "reminder_before_next_retry_at",
                    "reminder_start_sent_at",
                    "reminder_start_failure_count",
                    "reminder_start_last_failure_at",
                    "reminder_start_next_retry_at",
                    "reminder_time_up_sent_at",
                    "reminder_time_up_failure_count",
                    "reminder_time_up_last_failure_at",
                    "reminder_time_up_next_retry_at",
                    "updated_at",
                ]
            )
        except DjangoValidationError as exc:
            return Response({"error": exc.message_dict if hasattr(exc, "message_dict") else exc.messages}, status=status.HTTP_400_BAD_REQUEST)
        self._log_meeting_event(
            meeting=meeting,
            action=VideoMeetingEvent.ACTION_RESCHEDULED,
            scope=VideoMeetingEvent.SCOPE_SINGLE,
            detail="Meeting rescheduled.",
            metadata={
                "previous_start": previous_start.isoformat(),
                "previous_end": previous_end.isoformat(),
                "new_start": meeting.scheduled_start.isoformat(),
                "new_end": meeting.scheduled_end.isoformat(),
                "timezone": meeting.timezone,
            },
        )
        notify_meeting_updated(meeting)
        return Response(self.get_serializer(meeting).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="extend")
    def extend(self, request, pk=None):
        meeting = self.get_object()
        if meeting.status in {VideoMeeting.STATUS_CANCELLED, VideoMeeting.STATUS_COMPLETED}:
            return Response(
                {"error": "Cannot extend a closed meeting."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = VideoMeetingExtendSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        minutes = serializer.validated_data["minutes"]

        previous_end = meeting.scheduled_end
        meeting.scheduled_end = meeting.scheduled_end + timedelta(minutes=minutes)
        try:
            meeting.save(update_fields=["scheduled_end", "updated_at"])
        except DjangoValidationError as exc:
            return Response({"error": exc.message_dict if hasattr(exc, "message_dict") else exc.messages}, status=status.HTTP_400_BAD_REQUEST)
        self._log_meeting_event(
            meeting=meeting,
            action=VideoMeetingEvent.ACTION_EXTENDED,
            scope=VideoMeetingEvent.SCOPE_SINGLE,
            detail=f"Meeting extended by {minutes} minutes.",
            metadata={
                "minutes": minutes,
                "previous_end": previous_end.isoformat(),
                "new_end": meeting.scheduled_end.isoformat(),
            },
        )
        notify_meeting_updated(meeting)
        return Response(self.get_serializer(meeting).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, pk=None):
        meeting = self.get_object()
        if meeting.status in {VideoMeeting.STATUS_CANCELLED, VideoMeeting.STATUS_COMPLETED}:
            return Response({"error": "Cannot cancel a closed meeting."}, status=status.HTTP_400_BAD_REQUEST)
        reason = str(request.data.get("reason", "")).strip()
        try:
            meeting.mark_cancelled(reason=reason)
        except DjangoValidationError as exc:
            return Response(
                {"error": exc.message_dict if hasattr(exc, "message_dict") else exc.messages},
                status=status.HTTP_400_BAD_REQUEST,
            )
        self._log_meeting_event(
            meeting=meeting,
            action=VideoMeetingEvent.ACTION_CANCELLED,
            scope=VideoMeetingEvent.SCOPE_SINGLE,
            detail=reason or "Meeting cancelled.",
            metadata={"reason": reason},
        )
        notify_meeting_cancelled(meeting)
        return Response(self.get_serializer(meeting).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="start")
    def start(self, request, pk=None):
        meeting = self.get_object()
        if meeting.status == VideoMeeting.STATUS_ONGOING:
            return Response({"error": "Meeting is already in progress."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            meeting.mark_ongoing()
        except DjangoValidationError as exc:
            return Response(
                {"error": exc.message_dict if hasattr(exc, "message_dict") else exc.messages},
                status=status.HTTP_400_BAD_REQUEST,
            )
        self._log_meeting_event(
            meeting=meeting,
            action=VideoMeetingEvent.ACTION_STARTED,
            scope=VideoMeetingEvent.SCOPE_SINGLE,
            detail="Meeting started.",
        )
        return Response(self.get_serializer(meeting).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="complete")
    def complete(self, request, pk=None):
        meeting = self.get_object()
        if meeting.status == VideoMeeting.STATUS_COMPLETED:
            return Response({"error": "Meeting is already completed."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            meeting.mark_completed()
        except DjangoValidationError as exc:
            return Response(
                {"error": exc.message_dict if hasattr(exc, "message_dict") else exc.messages},
                status=status.HTTP_400_BAD_REQUEST,
            )
        self._log_meeting_event(
            meeting=meeting,
            action=VideoMeetingEvent.ACTION_COMPLETED,
            scope=VideoMeetingEvent.SCOPE_SINGLE,
            detail="Meeting completed.",
        )
        notify_meeting_time_up(meeting)
        return Response(self.get_serializer(meeting).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"], url_path="join-token")
    def join_token(self, request, pk=None):
        meeting = self.get_object()
        user = request.user
        if not meeting.is_joinable:
            return Response({"error": "Meeting is outside join window."}, status=status.HTTP_400_BAD_REQUEST)

        participant = meeting.participants.filter(user=user).first()
        if participant is None and meeting.organizer_id != user.id and not is_hr_or_admin_user(user):
            return Response({"error": "You are not allowed to join this meeting."}, status=status.HTTP_403_FORBIDDEN)

        role = participant.role if participant else VideoMeetingParticipant.ROLE_HOST
        try:
            token = build_livekit_join_token(meeting=meeting, user=user, role=role)
        except RuntimeError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        if participant and participant.status != VideoMeetingParticipant.STATUS_JOINED:
            participant.mark_joined()

        payload = {
            "token": token,
            "ws_url": str(getattr(settings, "LIVEKIT_URL", "")).strip(),
            "room_name": meeting.livekit_room_name,
            "expires_in": int(getattr(settings, "LIVEKIT_TOKEN_TTL_SECONDS", 3600)),
        }
        response_serializer = VideoMeetingJoinTokenSerializer(payload)
        return Response(response_serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"], url_path="calendar-ics")
    def calendar_ics(self, request, pk=None):
        meeting = self.get_object()
        content = build_meeting_ics_content(meeting)
        safe_title = slugify(meeting.title) or "video-meeting"
        filename = f"{safe_title}-{meeting.id}.ics"

        response = HttpResponse(content, content_type="text/calendar; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response

    @action(detail=True, methods=["post"], url_path="leave")
    def leave(self, request, pk=None):
        meeting = self.get_object()
        participant = meeting.participants.filter(user=request.user).first()
        if participant is None:
            return Response({"error": "Participant record not found."}, status=status.HTTP_404_NOT_FOUND)
        participant.mark_left()
        self._log_meeting_event(
            meeting=meeting,
            action=VideoMeetingEvent.ACTION_LEFT,
            scope=VideoMeetingEvent.SCOPE_SINGLE,
            detail="Participant left meeting.",
            metadata={"participant_id": str(participant.id), "role": participant.role},
        )
        return Response({"status": "left"}, status=status.HTTP_200_OK)

    @extend_schema(responses={200: VideoMeetingEventSerializer(many=True)})
    @action(detail=True, methods=["get"], url_path="events")
    def events(self, request, pk=None):
        meeting = self.get_object()
        include_series = str(request.query_params.get("series", "1")).strip().lower() in {"1", "true", "yes"}
        limit_raw = request.query_params.get("limit", "50")
        try:
            limit = max(1, min(int(limit_raw), 200))
        except (TypeError, ValueError):
            limit = 50

        queryset = VideoMeetingEvent.objects.select_related("actor").filter(meeting=meeting)
        if include_series and meeting.series_id:
            queryset = VideoMeetingEvent.objects.select_related("actor").filter(
                meeting__series_id=meeting.series_id
            )
        serializer = VideoMeetingEventSerializer(queryset.order_by("-created_at")[:limit], many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"], url_path="upcoming")
    def upcoming(self, request):
        now = timezone.now()
        queryset = self.get_queryset().filter(
            status=VideoMeeting.STATUS_SCHEDULED,
            scheduled_end__gte=now,
        )
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"], url_path="reminder-health")
    def reminder_health(self, request):
        if not is_admin_user(request.user):
            return Response(
                {"error": "Only admin users can view reminder health metrics."},
                status=status.HTTP_403_FORBIDDEN,
            )

        now = timezone.now()
        try:
            max_retries = int(getattr(settings, "VIDEO_CALLS_REMINDER_RETRY_MAX_ATTEMPTS", 3))
        except (TypeError, ValueError):
            max_retries = 3
        if max_retries < 1:
            max_retries = 1

        queryset = self.get_queryset()

        payload = {
            "generated_at": now.isoformat(),
            "max_retries": max_retries,
            "soon_retry_pending": queryset.filter(
                status=VideoMeeting.STATUS_SCHEDULED,
                reminder_before_sent_at__isnull=True,
                reminder_before_failure_count__gt=0,
                reminder_before_failure_count__lt=max_retries,
                reminder_before_next_retry_at__isnull=False,
                reminder_before_next_retry_at__lte=now,
            ).count(),
            "soon_retry_exhausted": queryset.filter(
                status=VideoMeeting.STATUS_SCHEDULED,
                reminder_before_sent_at__isnull=True,
                reminder_before_failure_count__gte=max_retries,
            ).count(),
            "start_now_retry_pending": queryset.filter(
                status=VideoMeeting.STATUS_ONGOING,
                reminder_start_sent_at__isnull=True,
                reminder_start_failure_count__gt=0,
                reminder_start_failure_count__lt=max_retries,
                reminder_start_next_retry_at__isnull=False,
                reminder_start_next_retry_at__lte=now,
            ).count(),
            "start_now_retry_exhausted": queryset.filter(
                status=VideoMeeting.STATUS_ONGOING,
                reminder_start_sent_at__isnull=True,
                reminder_start_failure_count__gte=max_retries,
            ).count(),
            "time_up_retry_pending": queryset.filter(
                status=VideoMeeting.STATUS_COMPLETED,
                reminder_time_up_sent_at__isnull=True,
                reminder_time_up_failure_count__gt=0,
                reminder_time_up_failure_count__lt=max_retries,
                reminder_time_up_next_retry_at__isnull=False,
                reminder_time_up_next_retry_at__lte=now,
            ).count(),
            "time_up_retry_exhausted": queryset.filter(
                status=VideoMeeting.STATUS_COMPLETED,
                reminder_time_up_sent_at__isnull=True,
                reminder_time_up_failure_count__gte=max_retries,
            ).count(),
        }
        return Response(payload, status=status.HTTP_200_OK)
