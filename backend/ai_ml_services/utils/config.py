"""Django-backed runtime configuration helpers for AI/ML services."""

from dataclasses import dataclass
from pathlib import Path

from django.conf import settings


@dataclass(frozen=True)
class AIMLRuntimeConfig:
    """Resolved runtime settings for AI/ML modules."""

    model_dir: Path
    media_dir: Path
    redis_url: str
    openai_model: str
    # Anthropic (Claude) — interview question generation
    anthropic_api_key: str
    anthropic_interview_model: str
    # LiveKit — WebRTC room management
    livekit_url: str
    livekit_api_key: str
    livekit_api_secret: str
    # Tavus — AI video avatar
    tavus_api_key: str
    tavus_replica_id: str
    tavus_persona_id: str


def get_runtime_config() -> AIMLRuntimeConfig:
    """Build config from Django settings with safe defaults."""
    model_dir = Path(getattr(settings, "MODEL_PATH", settings.BASE_DIR / "models"))
    media_dir = Path(getattr(settings, "MEDIA_ROOT", settings.BASE_DIR / "media"))

    return AIMLRuntimeConfig(
        model_dir=model_dir,
        media_dir=media_dir,
        redis_url=getattr(settings, "REDIS_URL", "redis://localhost:6379/0"),
        openai_model=getattr(settings, "OPENAI_MODEL", "gpt-4"),
        anthropic_api_key=getattr(settings, "ANTHROPIC_API_KEY", ""),
        anthropic_interview_model=getattr(settings, "ANTHROPIC_INTERVIEW_MODEL", "claude-sonnet-4-6"),
        livekit_url=getattr(settings, "LIVEKIT_URL", ""),
        livekit_api_key=getattr(settings, "LIVEKIT_API_KEY", ""),
        livekit_api_secret=getattr(settings, "LIVEKIT_API_SECRET", ""),
        tavus_api_key=getattr(settings, "TAVUS_API_KEY", ""),
        tavus_replica_id=getattr(settings, "TAVUS_REPLICA_ID", ""),
        tavus_persona_id=getattr(settings, "TAVUS_PERSONA_ID", ""),
    )
