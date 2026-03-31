"""LiveKit token generation and Tavus conversation management for interview sessions."""

from __future__ import annotations

import logging
from typing import Any

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)

TAVUS_API_BASE = "https://tavusapi.com/v2"


# ---------------------------------------------------------------------------
# Feature flag
# ---------------------------------------------------------------------------

def livekit_interview_enabled() -> bool:
    """Return True when LiveKit + Tavus interview provider is configured."""
    return bool(
        getattr(settings, "LIVEKIT_API_KEY", "")
        and getattr(settings, "LIVEKIT_API_SECRET", "")
        and getattr(settings, "TAVUS_API_KEY", "")
    )


# ---------------------------------------------------------------------------
# LiveKit token generation
# ---------------------------------------------------------------------------

def _create_livekit_token(
    *,
    room_name: str,
    participant_identity: str,
    participant_name: str,
) -> str:
    """Generate a signed LiveKit access token for a room participant."""
    try:
        from livekit.api import AccessToken, VideoGrants  # type: ignore[import]
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "livekit-api package is required. Add it to requirements."
        ) from exc

    api_key = str(getattr(settings, "LIVEKIT_API_KEY", "")).strip()
    api_secret = str(getattr(settings, "LIVEKIT_API_SECRET", "")).strip()
    ttl = int(getattr(settings, "LIVEKIT_TOKEN_TTL_SECONDS", 3600))

    if not api_key or not api_secret:
        raise RuntimeError("LIVEKIT_API_KEY and LIVEKIT_API_SECRET must be configured.")

    token = (
        AccessToken(api_key=api_key, api_secret=api_secret)
        .with_identity(participant_identity)
        .with_name(participant_name)
        .with_grants(VideoGrants(room_join=True, room=room_name))
        .with_ttl(ttl)
        .to_jwt()
    )
    return token


# ---------------------------------------------------------------------------
# Tavus conversation management
# ---------------------------------------------------------------------------

def _tavus_headers() -> dict[str, str]:
    api_key = str(getattr(settings, "TAVUS_API_KEY", "")).strip()
    if not api_key:
        raise RuntimeError("TAVUS_API_KEY is not configured.")
    return {"x-api-key": api_key, "Content-Type": "application/json"}


def create_tavus_conversation(
    *,
    session_id: str,
    conversational_context: str,
    custom_greeting: str,
    callback_url: str = "",
    timeout: float = 30.0,
) -> dict[str, Any]:
    """
    Create a Tavus conversation for an interview session.

    Returns the Tavus response dict containing:
      - conversation_id
      - conversation_url  (the candidate joins via this URL)
      - status
    """
    replica_id = str(getattr(settings, "TAVUS_REPLICA_ID", "")).strip()
    persona_id = str(getattr(settings, "TAVUS_PERSONA_ID", "")).strip()
    max_duration = int(getattr(settings, "TAVUS_MAX_CALL_DURATION", 3600))
    left_timeout = int(getattr(settings, "TAVUS_PARTICIPANT_LEFT_TIMEOUT", 60))
    language = str(getattr(settings, "TAVUS_LANGUAGE", "english"))
    enable_recording = bool(getattr(settings, "TAVUS_ENABLE_RECORDING", False))

    if not replica_id:
        raise RuntimeError("TAVUS_REPLICA_ID is not configured.")

    payload: dict[str, Any] = {
        "conversation_name": f"Interview-{session_id}",
        "conversational_context": conversational_context,
        "custom_greeting": custom_greeting,
        "properties": {
            "max_call_duration": max_duration,
            "participant_left_timeout": left_timeout,
            "participant_absent_timeout": left_timeout * 5,
            "enable_recording": enable_recording,
            "language": language,
            "apply_greenscreen": False,
        },
    }
    if replica_id:
        payload["replica_id"] = replica_id
    if persona_id:
        payload["persona_id"] = persona_id
    if callback_url:
        payload["callback_url"] = callback_url

    try:
        response = httpx.post(
            f"{TAVUS_API_BASE}/conversations",
            headers=_tavus_headers(),
            json=payload,
            timeout=timeout,
        )
    except httpx.HTTPError as exc:
        raise RuntimeError("Unable to reach Tavus API.") from exc

    if response.status_code not in (200, 201):
        raise RuntimeError(
            f"Tavus conversation creation failed ({response.status_code}): {response.text}"
        )

    try:
        data = response.json()
    except ValueError as exc:
        raise RuntimeError("Invalid response from Tavus API.") from exc

    logger.info("Tavus conversation created: %s", data.get("conversation_id"))
    return data


def end_tavus_conversation(conversation_id: str, timeout: float = 10.0) -> None:
    """Gracefully end an active Tavus conversation."""
    if not conversation_id:
        return
    try:
        response = httpx.post(
            f"{TAVUS_API_BASE}/conversations/{conversation_id}/end",
            headers=_tavus_headers(),
            timeout=timeout,
        )
        if response.status_code not in (200, 204):
            logger.warning(
                "Tavus end conversation returned %s: %s",
                response.status_code,
                response.text,
            )
    except httpx.HTTPError as exc:
        logger.error("Error ending Tavus conversation %s: %s", conversation_id, exc)


# ---------------------------------------------------------------------------
# Combined session payload — called by the avatar-session API view
# ---------------------------------------------------------------------------

def build_interview_session_payload(
    *,
    session_id: str,
    case_title: str = "",
    flags_summary: str = "",
    callback_url: str = "",
) -> dict[str, Any]:
    """
    Build the full payload returned to the frontend for joining an interview.

    When LiveKit + Tavus is not enabled returns {"enabled": False}.
    On success returns:
      {
        "enabled": True,
        "livekit_url": "wss://...",
        "livekit_token": "<jwt>",
        "room_name": "interview-<session_id>",
        "conversation_id": "<tavus id>",
        "conversation_url": "https://tavus.daily.co/...",
      }
    """
    if not livekit_interview_enabled():
        return {"enabled": False}

    room_name = f"interview-{session_id}"
    livekit_url = str(getattr(settings, "LIVEKIT_URL", "")).strip()

    # Generate a LiveKit token for the candidate
    livekit_token = _create_livekit_token(
        room_name=room_name,
        participant_identity=f"candidate-{session_id}",
        participant_name="Candidate",
    )

    # Build context string for the Tavus persona
    context_parts = [
        "You are a professional government vetting interviewer conducting a formal assessment.",
        "Maintain a serious, respectful tone throughout the interview.",
        "Ask one question at a time and wait for the candidate to finish before continuing.",
    ]
    if case_title:
        context_parts.append(f"This interview is for the position: {case_title}.")
    if flags_summary:
        context_parts.append(
            f"Key areas requiring clarification: {flags_summary}. "
            "Probe these areas with specific follow-up questions if the candidate's answers are vague."
        )
    conversational_context = " ".join(context_parts)

    greeting = (
        "Good day. I am your interviewer for today's vetting session. "
        "Please ensure you are in a quiet environment. When you are ready, I will begin."
    )

    tavus_data = create_tavus_conversation(
        session_id=session_id,
        conversational_context=conversational_context,
        custom_greeting=greeting,
        callback_url=callback_url,
    )

    return {
        "enabled": True,
        "livekit_url": livekit_url,
        "livekit_token": livekit_token,
        "room_name": room_name,
        "conversation_id": tavus_data.get("conversation_id", ""),
        "conversation_url": tavus_data.get("conversation_url", ""),
    }
