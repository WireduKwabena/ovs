from django.contrib import admin

from apps.video_calls.models import VideoMeeting, VideoMeetingEvent, VideoMeetingParticipant


@admin.register(VideoMeeting)
class VideoMeetingAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "organizer",
        "status",
        "scheduled_start",
        "scheduled_end",
        "reminder_before_minutes",
        "livekit_room_name",
    )
    list_filter = ("status", "scheduled_start", "timezone")
    search_fields = ("title", "organizer__email", "livekit_room_name")
    readonly_fields = ("id", "livekit_room_name", "created_at", "updated_at")


@admin.register(VideoMeetingParticipant)
class VideoMeetingParticipantAdmin(admin.ModelAdmin):
    list_display = ("meeting", "user", "role", "status", "invited_at", "joined_at")
    list_filter = ("role", "status")
    search_fields = ("meeting__title", "user__email", "meeting__livekit_room_name")
    readonly_fields = ("id", "invited_at")


@admin.register(VideoMeetingEvent)
class VideoMeetingEventAdmin(admin.ModelAdmin):
    list_display = ("meeting", "action", "scope", "actor", "created_at")
    list_filter = ("action", "scope", "created_at")
    search_fields = ("meeting__title", "meeting__livekit_room_name", "actor__email", "detail")
    readonly_fields = ("id", "meeting", "actor", "action", "scope", "detail", "metadata", "created_at")
