# backend/apps/interviews/security.py
from django.conf import settings
from django.core.exceptions import PermissionDenied


class InterviewSecurityMiddleware:
    """Security measures for interview sessions"""

    @staticmethod
    def validate_session_access(user, session):
        """Ensure user can only access their own interview"""
        if session.application.applicant != user:
            raise PermissionDenied("Access denied to this interview session")

    @staticmethod
    def check_recording_environment():
        """Verify recording environment integrity"""
        # Check for:
        # - Screen recording software
        # - Multiple monitors
        # - Virtual cameras
        # Implementation depends on requirements
        pass

    @staticmethod
    def encrypt_video_storage(video_file):
        """Encrypt videos at rest"""
        from cryptography.fernet import Fernet

        key = settings.VIDEO_ENCRYPTION_KEY
        fernet = Fernet(key)

        encrypted_data = fernet.encrypt(video_file.read())
        return encrypted_data


# Privacy settings in settings.py
VIDEO_RETENTION_DAYS = 90  # Delete videos after 90 days
TRANSCRIPT_RETENTION_DAYS = 365  # Keep transcripts longer
ENABLE_VIDEO_WATERMARKING = True
ALLOW_VIDEO_DOWNLOAD = False  # Only HR can download