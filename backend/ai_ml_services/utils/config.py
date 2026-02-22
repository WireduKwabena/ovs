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
    heygen_api_key: str
    heygen_avatar_id: str
    heygen_voice_id: str


def get_runtime_config() -> AIMLRuntimeConfig:
    """Build config from Django settings with safe defaults."""
    model_dir = Path(getattr(settings, "MODEL_PATH", settings.BASE_DIR / "models"))
    media_dir = Path(getattr(settings, "MEDIA_ROOT", settings.BASE_DIR / "media"))

    return AIMLRuntimeConfig(
        model_dir=model_dir,
        media_dir=media_dir,
        redis_url=getattr(settings, "REDIS_URL", "redis://localhost:6379/0"),
        openai_model=getattr(settings, "OPENAI_MODEL", "gpt-4"),
        heygen_api_key=getattr(settings, "HEYGEN_API_KEY", ""),
        heygen_avatar_id=getattr(
            settings, "HEYGEN_AVATAR_ID", "default_professional_avatar"
        ),
        heygen_voice_id=getattr(settings, "HEYGEN_VOICE_ID", ""),
    )
