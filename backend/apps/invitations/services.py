import hashlib
import json
import logging
import secrets
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import CandidateAccessPass, CandidateAccessSession, Invitation

logger = logging.getLogger(__name__)


class CandidateAccessError(Exception):
    def __init__(self, message: str, code: str = "invalid"):
        super().__init__(message)
        self.code = code


def _json_sanitize(value):
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        normalized = {}
        for key, item in value.items():
            if not isinstance(key, str):
                key = str(key)
            normalized[key] = _json_sanitize(item)
        return normalized
    if isinstance(value, (list, tuple, set)):
        return [_json_sanitize(item) for item in value]
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            return str(value)
    try:
        json.dumps(value)
        return value
    except Exception:
        return str(value)


def _normalize_metadata(metadata):
    if metadata is None:
        return {}
    if isinstance(metadata, dict):
        return _json_sanitize(metadata)
    return {"value": _json_sanitize(metadata)}


def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def _token_hint(raw_token: str) -> str:
    return raw_token[-8:] if len(raw_token) >= 8 else raw_token


def build_candidate_access_url(raw_token: str) -> str:
    frontend = getattr(settings, "FRONTEND_URL", "http://localhost:3000").rstrip("/")
    path = getattr(settings, "CANDIDATE_ACCESS_FRONTEND_PATH", "/candidate/access")
    if not path.startswith("/"):
        path = f"/{path}"
    return f"{frontend}{path}?token={raw_token}"


def issue_candidate_access_pass(
    *,
    enrollment,
    invitation: Invitation | None = None,
    pass_type: str = "portal",
    issued_by=None,
    expires_at=None,
    max_uses: int | None = None,
    metadata: dict | None = None,
    revoke_existing: bool = True,
) -> tuple[CandidateAccessPass, str]:
    now = timezone.now()
    max_uses = max_uses or int(getattr(settings, "CANDIDATE_ACCESS_MAX_USES", 50))
    if expires_at is None:
        ttl_hours = int(getattr(settings, "CANDIDATE_ACCESS_PASS_TTL_HOURS", 72))
        expires_at = now + timedelta(hours=ttl_hours)

    with transaction.atomic():
        if revoke_existing:
            CandidateAccessPass.objects.filter(
                enrollment=enrollment,
                pass_type=pass_type,
                status="issued",
            ).update(status="revoked", revoked_at=now, revoked_reason="superseded", updated_at=now)

        for _ in range(5):
            raw_token = secrets.token_urlsafe(32)
            token_hash = _hash_token(raw_token)
            if not CandidateAccessPass.objects.filter(token_hash=token_hash).exists():
                access_pass = CandidateAccessPass.objects.create(
                    enrollment=enrollment,
                    invitation=invitation,
                    pass_type=pass_type,
                    token_hash=token_hash,
                    token_hint=_token_hint(raw_token),
                    max_uses=max_uses,
                    expires_at=expires_at,
                    issued_by=issued_by,
                    metadata=_normalize_metadata(metadata),
                )
                return access_pass, raw_token

    raise CandidateAccessError("Failed to issue candidate access pass.", code="issue_failed")


def consume_candidate_access_token(
    *,
    raw_token: str,
    ip_address: str | None = None,
    user_agent: str = "",
    begin_vetting: bool = True,
) -> tuple[CandidateAccessSession, CandidateAccessPass]:
    token_hash = _hash_token(raw_token)
    now = timezone.now()

    with transaction.atomic():
        access_pass = (
            CandidateAccessPass.objects.select_for_update()
            .select_related("enrollment__campaign", "enrollment__candidate")
            .filter(token_hash=token_hash)
            .first()
        )
        if access_pass is None:
            raise CandidateAccessError("Invalid access token.", code="invalid")

        if access_pass.status != "issued":
            raise CandidateAccessError("Access token is not active.", code="inactive")

        if access_pass.is_expired:
            access_pass.status = "expired"
            access_pass.save(update_fields=["status", "updated_at"])
            raise CandidateAccessError("Access token has expired.", code="expired")

        if access_pass.use_count >= access_pass.max_uses:
            access_pass.status = "revoked"
            access_pass.revoked_at = now
            access_pass.revoked_reason = "usage_limit_reached"
            access_pass.save(update_fields=["status", "revoked_at", "revoked_reason", "updated_at"])
            raise CandidateAccessError("Access token usage limit reached.", code="exhausted")

        access_pass.use_count += 1
        access_pass.first_used_at = access_pass.first_used_at or now
        access_pass.last_used_at = now
        access_pass.save(update_fields=["use_count", "first_used_at", "last_used_at", "updated_at"])

        session_ttl = int(getattr(settings, "CANDIDATE_ACCESS_SESSION_TTL_HOURS", 12))
        candidate_session = CandidateAccessSession.objects.create(
            access_pass=access_pass,
            enrollment=access_pass.enrollment,
            ip_address=ip_address,
            user_agent=user_agent[:2000] if user_agent else "",
            expires_at=now + timedelta(hours=session_ttl),
            last_seen_at=now,
        )

        invitation = access_pass.invitation
        if invitation and invitation.status in {"pending", "sent", "failed"} and not invitation.is_expired:
            invitation.status = "accepted"
            invitation.accepted_at = now
            invitation.save(update_fields=["status", "accepted_at", "updated_at"])

        enrollment = access_pass.enrollment
        enrollment_fields = []
        if enrollment.status == "invited":
            enrollment.status = "registered"
            enrollment_fields.append("status")
            if not enrollment.registered_at:
                enrollment.registered_at = now
                enrollment_fields.append("registered_at")
        if begin_vetting and enrollment.status == "registered":
            enrollment.status = "in_progress"
            if "status" not in enrollment_fields:
                enrollment_fields.append("status")
        if enrollment_fields:
            enrollment.save(update_fields=[*enrollment_fields, "updated_at"])

        _ensure_vetting_case_for_enrollment(enrollment)

        return candidate_session, access_pass


def _resolve_case_applicant_user(enrollment):
    from apps.authentication.models import User

    candidate = enrollment.candidate
    existing_user = User.objects.filter(email__iexact=candidate.email).first()
    if existing_user:
        if existing_user.user_type != "applicant":
            logger.warning(
                "Candidate email is linked to non-applicant user_type='%s' for enrollment_id=%s.",
                existing_user.user_type,
                enrollment.id,
            )
        return existing_user

    try:
        return User.objects.create_user(
            email=candidate.email,
            password=None,
            first_name=candidate.first_name or "",
            last_name=candidate.last_name or "",
            user_type="applicant",
        )
    except IntegrityError:
        recovered = User.objects.filter(email__iexact=candidate.email).first()
        if recovered:
            return recovered
        raise CandidateAccessError("Unable to create candidate user profile.", code="user_create_failed")


def _derive_case_status_from_enrollment(enrollment_status: str) -> str:
    mapping = {
        "invited": "document_upload",
        "registered": "document_upload",
        "in_progress": "document_upload",
        "completed": "under_review",
        "reviewed": "under_review",
        "approved": "approved",
        "rejected": "rejected",
        "escalated": "under_review",
    }
    return mapping.get(enrollment_status, "document_upload")


def _derive_case_position(campaign) -> str:
    settings_json = campaign.settings_json if isinstance(campaign.settings_json, dict) else {}
    position = (
        settings_json.get("position_applied")
        or settings_json.get("position")
        or settings_json.get("role")
        or settings_json.get("job_title")
        or ""
    )
    if position:
        return str(position)[:200]
    return f"{campaign.name} Candidate Vetting"[:200]


def _ensure_vetting_case_for_enrollment(enrollment):
    from apps.applications.models import VettingCase

    existing_case = (
        VettingCase.objects.select_related("candidate_enrollment")
        .filter(candidate_enrollment_id=enrollment.id)
        .order_by("-created_at")
        .first()
    )
    if existing_case:
        return existing_case

    applicant = _resolve_case_applicant_user(enrollment)
    campaign = enrollment.campaign
    settings_json = campaign.settings_json if isinstance(campaign.settings_json, dict) else {}

    return VettingCase.objects.create(
        applicant=applicant,
        candidate_enrollment=enrollment,
        assigned_to=campaign.initiated_by,
        position_applied=_derive_case_position(campaign),
        department=str(settings_json.get("department", "") or "")[:100],
        job_description=campaign.description or "",
        priority="medium",
        status=_derive_case_status_from_enrollment(enrollment.status),
    )


def resolve_candidate_access_session(session_key: str | None) -> CandidateAccessSession | None:
    if not session_key:
        return None

    session = (
        CandidateAccessSession.objects.select_related("enrollment__campaign", "enrollment__candidate", "access_pass")
        .filter(session_key=session_key, status="active")
        .first()
    )
    if session is None:
        return None

    if session.is_expired:
        session.status = "expired"
        session.closed_at = timezone.now()
        session.closed_reason = "expired"
        session.save(update_fields=["status", "closed_at", "closed_reason"])
        return None

    try:
        _ensure_vetting_case_for_enrollment(session.enrollment)
    except Exception:
        logger.exception(
            "Failed to ensure vetting case for active candidate session enrollment_id=%s",
            session.enrollment_id,
        )
    return session


def touch_candidate_access_session(candidate_session: CandidateAccessSession) -> None:
    candidate_session.last_seen_at = timezone.now()
    candidate_session.save(update_fields=["last_seen_at"])


def close_candidate_access_session(candidate_session: CandidateAccessSession, reason: str = "logout") -> None:
    if candidate_session.status != "active":
        return
    candidate_session.status = "closed"
    candidate_session.closed_reason = reason
    candidate_session.closed_at = timezone.now()
    candidate_session.save(update_fields=["status", "closed_reason", "closed_at"])


def send_invitation(invitation: Invitation) -> None:
    """Send an invitation through the requested channel.

    SMS integration is left as a provider adapter and currently logs as sent.
    """
    if invitation.channel not in {"email", "sms"}:
        raise CandidateAccessError(
            f"Unsupported invitation channel '{invitation.channel}'.",
            code="unsupported_channel",
        )

    accept_url = f"{getattr(settings, 'FRONTEND_URL', 'http://localhost:3000').rstrip('/')}/invite/{invitation.token}"
    access_pass, raw_access_token = issue_candidate_access_pass(
        enrollment=invitation.enrollment,
        invitation=invitation,
        pass_type="portal",
        issued_by=invitation.created_by,
    )
    access_url = build_candidate_access_url(raw_access_token)

    if invitation.channel == "email":
        subject = f"Invitation: {invitation.enrollment.campaign.name}"
        message = (
            f"You have been invited to a vetting process.\n\n"
            f"Campaign: {invitation.enrollment.campaign.name}\n"
            f"Candidate: {invitation.enrollment.candidate.first_name} {invitation.enrollment.candidate.last_name}\n"
            f"Start vetting / view results: {access_url}\n\n"
            f"Legacy invitation URL: {accept_url}\n"
        )
        send_mail(
            subject=subject,
            message=message,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@example.com"),
            recipient_list=[invitation.send_to],
            fail_silently=False,
        )
        logger.info("Invitation email sent for invitation_id=%s", invitation.id)
        return

    # Placeholder for SMS provider integration.
    if invitation.channel == "sms":
        access_pass.metadata = {
            **_normalize_metadata(access_pass.metadata),
            "delivery_channel": "sms",
            "delivery_target": invitation.send_to,
            "access_url": access_url,
        }
        access_pass.save(update_fields=["metadata", "updated_at"])
        logger.warning(
            "SMS delivery adapter is not configured. Marking invitation_id=%s as sent placeholder.",
            invitation.id,
        )
        return
