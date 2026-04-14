"""Avatar service compatibility wrapper for interview flows.

Thin wrapper around LiveKitTavusService so existing call-sites that import
AIAvatarService continue to work without modification.
"""

from __future__ import annotations

from typing import Optional, Protocol

from ai_ml_services.interview.livekit_tavus_service import LiveKitTavusService


class WebSocketProtocol(Protocol):
    async def send_bytes(self, data: bytes) -> None: ...
    async def send_json(self, data: dict) -> None: ...


class AIAvatarService:
    """
    Backward-compatible wrapper around the LiveKit + Tavus avatar stack.

    Mirrors the interface of the former HeyGen-based AIAvatarService so that
    code importing this class does not need to change.
    """

    def __init__(
        self,
        session_id: str,
        provider: str = "livekit_tavus",
        **kwargs,
    ):
        if provider != "livekit_tavus":
            raise ValueError(f"Unknown avatar provider: {provider!r}")
        self.provider = "livekit_tavus"
        self._service = LiveKitTavusService(session_id)

    @property
    def session_id(self) -> Optional[str]:
        return self._service.session_id

    @property
    def conversation_id(self) -> Optional[str]:
        return self._service.conversation_id

    @property
    def conversation_url(self) -> Optional[str]:
        return self._service.conversation_url

    async def create_streaming_session(self, **kwargs) -> dict:
        return await self._service.create_session(**kwargs)

    async def stream_avatar_response(self, text: str, websocket: WebSocketProtocol) -> None:
        await self._service.deliver_interviewer_text(text=text, websocket=websocket)

    async def stream_avatar_speech(self, text: str, websocket: WebSocketProtocol, **kwargs) -> None:
        await self._service.deliver_interviewer_text(text=text, websocket=websocket)

    async def close_session(self) -> None:
        await self._service.close_session()
