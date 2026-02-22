"""HeyGen streaming avatar integration."""

from __future__ import annotations

import json
import logging
from typing import Optional, Protocol

from django.conf import settings

try:
    import aiohttp
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    aiohttp = None


logger = logging.getLogger(__name__)


class WebSocketProtocol(Protocol):
    async def send_bytes(self, data: bytes) -> None: ...
    async def send_json(self, data: dict) -> None: ...


class HeyGenAvatarService:
    """HeyGen streaming avatar wrapper for interview sessions."""

    BASE_URL = "https://api.heygen.com/v2"

    def __init__(
        self,
        api_key: Optional[str] = None,
        avatar_id: Optional[str] = None,
        voice_id: Optional[str] = None,
    ):
        self.api_key = api_key or settings.HEYGEN_API_KEY
        self.avatar_id = avatar_id or settings.HEYGEN_AVATAR_ID
        self.voice_id = voice_id or settings.HEYGEN_VOICE_ID
        self.session_id = None
        self.headers = {
            "X-Api-Key": self.api_key,
            "Content-Type": "application/json",
        }

    @staticmethod
    def _ensure_http_client() -> None:
        if aiohttp is None:
            raise RuntimeError("aiohttp is required for HeyGen streaming integration.")

    async def create_streaming_session(
        self, knowledge_base: str | None = None, flags: list | None = None
    ) -> dict:
        self._ensure_http_client()

        url = f"{self.BASE_URL}/video/stream/new"
        kb_prompt = knowledge_base or (
            f"Interrogation flags: {json.dumps(flags)}. Probe inconsistencies naturally."
        )
        payload = {
            "quality": "high",
            "avatar_name": self.avatar_id,
            "voice": {
                "voice_id": self.voice_id,
                "rate": 1.0,
                "emotion": "Serious",
            },
            "video_encoding": "H264",
            "session_timeout": 1800,
            "knowledge_base": kb_prompt,
            "activity_idle_timeout": 300,
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=self.headers, json=payload) as response:
                if response.status != 200:
                    error = await response.text()
                    raise RuntimeError(f"HeyGen session creation failed: {error}")
                data = await response.json()
                self.session_id = data["data"]["session_id"]
                logger.info("HeyGen session created: %s", self.session_id)
                return data["data"]

    async def start_session_connection(self, websocket: WebSocketProtocol) -> dict:
        del websocket  # Connection info is fetched by API call only.
        self._ensure_http_client()

        if not self.session_id:
            await self.create_streaming_session()

        url = f"{self.BASE_URL}/video/stream/{self.session_id}/start"
        payload = {"sdp": {"type": "offer", "sdp": ""}}

        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=self.headers, json=payload) as response:
                if response.status != 200:
                    error = await response.text()
                    raise RuntimeError(f"Failed to start HeyGen session: {error}")
                data = await response.json()
                return data["data"]

    async def stream_avatar_speech(
        self,
        text: str,
        websocket: WebSocketProtocol,
        emotion: str = "Serious",
        flags: list | None = None,
        rate: float = 1.0,
    ) -> None:
        del flags  # reserved for future prompt shaping
        self._ensure_http_client()

        if not self.session_id:
            await self.create_streaming_session()

        url = f"{self.BASE_URL}/video/stream/{self.session_id}/task"
        payload = {
            "text": text,
            "task_type": "repeat",
            "task_mode": "sync",
            "voice": {"emotion": emotion, "rate": rate},
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=self.headers, json=payload) as response:
                if response.status != 200:
                    error = await response.text()
                    raise RuntimeError(f"HeyGen speech task failed: {error}")

            stream_url = f"{self.BASE_URL}/video/stream/{self.session_id}/stream"
            await websocket.send_json({"type": "avatar_stream_start", "text": text})

            async with session.get(stream_url, headers=self.headers) as stream_response:
                async for chunk in stream_response.content.iter_chunked(8192):
                    if chunk:
                        await websocket.send_bytes(chunk)

            await websocket.send_json({"type": "avatar_stream_end"})

    async def send_ice_candidate(self, candidate: dict) -> None:
        self._ensure_http_client()
        if not self.session_id:
            raise ValueError("No active HeyGen session.")

        url = f"{self.BASE_URL}/video/stream/{self.session_id}/ice"
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=self.headers, json=candidate) as response:
                if response.status != 200:
                    error = await response.text()
                    logger.error("Failed to send ICE candidate: %s", error)

    async def close_session(self) -> None:
        if not self.session_id:
            return
        self._ensure_http_client()

        url = f"{self.BASE_URL}/video/stream/{self.session_id}/stop"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=self.headers) as response:
                    if response.status != 200:
                        error = await response.text()
                        logger.warning("Error closing HeyGen session: %s", error)
        finally:
            logger.info("HeyGen session closed: %s", self.session_id)
            self.session_id = None
