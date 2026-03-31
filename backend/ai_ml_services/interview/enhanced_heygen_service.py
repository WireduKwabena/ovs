"""Legacy shim — replaced by AdaptiveAvatarService (LiveKit + Tavus + Anthropic).

This module is kept to prevent ImportError in code that was not yet updated.
"""

from .adaptive_avatar_service import AdaptiveAvatarService as EmotionalAvatarService

__all__ = ["EmotionalAvatarService"]
