from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, PermissionDenied

from .permissions import is_hr_admin_user


def can_access_session(user, session) -> bool:
    """Check whether a user is allowed to access an interview session."""
    if not getattr(user, "is_authenticated", False):
        return False
    if is_hr_admin_user(user):
        return True
    return bool(
        session.case.applicant_id == user.id
        or session.case.assigned_to_id == user.id
    )


class InterviewSecurityMiddleware:
    """
    Backward-compatible security utility wrapper.

    Note: this is not a Django request middleware class; it is an interview
    security helper kept for compatibility with legacy imports.
    """

    @staticmethod
    def validate_session_access(user, session):
        if not can_access_session(user, session):
            raise PermissionDenied("Access denied to this interview session.")

    @staticmethod
    def check_recording_environment():
        return {
            "supported": False,
            "checks": [],
            "message": "Client-side recording environment checks are not configured on the backend.",
        }

    @staticmethod
    def encrypt_video_storage(video_file):
        try:
            from cryptography.fernet import Fernet
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise ImproperlyConfigured(
                "cryptography is required to encrypt interview media."
            ) from exc

        key = getattr(settings, "VIDEO_ENCRYPTION_KEY", "")
        if not key:
            raise ImproperlyConfigured("VIDEO_ENCRYPTION_KEY is not configured.")
        data = video_file.read() if hasattr(video_file, "read") else bytes(video_file)
        return Fernet(key).encrypt(data)
