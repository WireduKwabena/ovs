"""Legacy shim — HeyGen has been replaced by LiveKit + Tavus + Anthropic.

This module is kept to prevent ImportError in code that was not yet updated.
All symbols delegate to the new implementation.
"""

from .livekit_tavus_service import LiveKitTavusService as HeyGenAvatarService, WebSocketProtocol

__all__ = ["HeyGenAvatarService", "WebSocketProtocol"]
