"""Avatar service compatibility wrapper for interview flows."""

from __future__ import annotations

from typing import Optional, Protocol

from ai_ml_services.interview.heygen_service import HeyGenAvatarService


class WebSocketProtocol(Protocol):
    async def send_bytes(self, data: bytes) -> None: ...
    async def send_json(self, data: dict) -> None: ...


class AIAvatarService:
    """
    Backward-compatible wrapper around HeyGen avatar streaming.

    This keeps historical imports stable while centralizing runtime behavior in
    `ai_ml_services.interview.heygen_service.HeyGenAvatarService`.
    """

    def __init__(
        self,
        provider: str = "heygen",
        api_key: Optional[str] = None,
        avatar_id: Optional[str] = None,
        voice_id: Optional[str] = None,
    ):
        if provider != "heygen":
            raise ValueError("Only provider='heygen' is supported in the Django runtime.")
        self.provider = provider
        self._service = HeyGenAvatarService(
            api_key=api_key,
            avatar_id=avatar_id,
            voice_id=voice_id,
        )

    @property
    def session_id(self) -> Optional[str]:
        return self._service.session_id

    async def create_streaming_session(self, *args, **kwargs):
        return await self._service.create_streaming_session(*args, **kwargs)

    async def stream_avatar_response(self, text: str, websocket: WebSocketProtocol):
        await self._service.stream_avatar_speech(text=text, websocket=websocket)

    async def stream_avatar_speech(self, text: str, websocket: WebSocketProtocol, **kwargs):
        await self._service.stream_avatar_speech(text=text, websocket=websocket, **kwargs)

    async def send_ice_candidate(self, candidate: dict):
        await self._service.send_ice_candidate(candidate)

    async def close_session(self):
        await self._service.close_session()

