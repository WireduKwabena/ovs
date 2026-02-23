"""Helpers for using HeyGen's frontend streaming SDK safely."""

from __future__ import annotations

from typing import Any

import httpx
from django.conf import settings


TOKEN_URL = "https://api.heygen.com/v1/streaming.create_token"
VALID_QUALITIES = {"low", "medium", "high"}


def heygen_frontend_sdk_enabled() -> bool:
    return bool(getattr(settings, "HEYGEN_FRONTEND_SDK_ENABLED", False))


def _normalized_quality() -> str:
    quality = str(getattr(settings, "HEYGEN_AVATAR_QUALITY", "medium")).strip().lower()
    if quality in VALID_QUALITIES:
        return quality
    return "medium"


def _normalized_idle_timeout() -> int:
    value = int(getattr(settings, "HEYGEN_AVATAR_ACTIVITY_IDLE_TIMEOUT", 300))
    return max(30, min(3600, value))


def _extract_token(payload: dict[str, Any]) -> str:
    data = payload.get("data")
    if isinstance(data, dict):
        token = data.get("token")
        if isinstance(token, str) and token.strip():
            return token.strip()
    token = payload.get("token")
    if isinstance(token, str) and token.strip():
        return token.strip()
    return ""


def request_streaming_access_token(timeout: float = 20.0) -> str:
    api_key = str(getattr(settings, "HEYGEN_API_KEY", "")).strip()
    if not api_key:
        raise RuntimeError("HEYGEN_API_KEY is not configured.")

    try:
        response = httpx.post(
            TOKEN_URL,
            headers={"x-api-key": api_key},
            timeout=timeout,
        )
    except httpx.HTTPError as exc:
        raise RuntimeError("Unable to reach HeyGen token endpoint.") from exc

    if response.status_code != 200:
        raise RuntimeError("HeyGen token request failed.")

    try:
        payload = response.json()
    except ValueError as exc:
        raise RuntimeError("Invalid token response from HeyGen.") from exc

    token = _extract_token(payload if isinstance(payload, dict) else {})
    if not token:
        raise RuntimeError("HeyGen token response did not contain a token.")
    return token


def build_avatar_session_payload() -> dict[str, Any]:
    if not heygen_frontend_sdk_enabled():
        return {"enabled": False}

    token = request_streaming_access_token()
    return {
        "enabled": True,
        "token": token,
        "avatar_name": str(getattr(settings, "HEYGEN_AVATAR_ID", "")),
        "voice_id": str(getattr(settings, "HEYGEN_VOICE_ID", "")),
        "quality": _normalized_quality(),
        "language": str(getattr(settings, "HEYGEN_AVATAR_LANGUAGE", "en")),
        "activity_idle_timeout": _normalized_idle_timeout(),
    }
