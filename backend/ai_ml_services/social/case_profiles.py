"""Helpers for extracting social-profile payloads from case objects."""

from __future__ import annotations

from typing import Any


def extract_case_social_profiles(case: Any) -> tuple[list[dict[str, str]], bool]:
    """
    Build social-profile payload expected by ``check_social_profiles``.

    Returns:
        (profiles, consent_provided)
    """
    profiles: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()

    applicant = getattr(case, "applicant", None)
    display_name = applicant.get_full_name() if applicant else ""

    enrollment = getattr(case, "candidate_enrollment", None)
    candidate = getattr(enrollment, "candidate", None) if enrollment else None
    consent_provided = bool(getattr(candidate, "consent_ai_processing", False)) if candidate else False

    def _append_profile(
        platform: str = "",
        url: str = "",
        username: str = "",
        display: str = "",
    ) -> None:
        platform_norm = str(platform or "").strip().lower()
        url_norm = str(url or "").strip()
        username_norm = str(username or "").strip()
        display_norm = str(display or "").strip()

        if not (url_norm or username_norm):
            return

        key = (platform_norm, url_norm.lower(), username_norm.lower())
        if key in seen:
            return
        seen.add(key)

        payload: dict[str, str] = {}
        if platform_norm:
            payload["platform"] = platform_norm
        if url_norm:
            payload["url"] = url_norm
        if username_norm:
            payload["username"] = username_norm
        if display_norm:
            payload["display_name"] = display_norm
        profiles.append(payload)

    # Legacy applicant profile fallback.
    applicant_profile = getattr(applicant, "profile", None)
    if applicant_profile is not None:
        _append_profile(
            platform="linkedin",
            url=getattr(applicant_profile, "linkedin_url", ""),
            display=display_name,
        )

    # Structured candidate social profiles (preferred source).
    if candidate is not None:
        for profile in candidate.social_profiles.all():
            _append_profile(
                platform=getattr(profile, "platform", ""),
                url=getattr(profile, "url", ""),
                username=getattr(profile, "username", ""),
                display=getattr(profile, "display_name", "") or display_name,
            )

    # Metadata fallback for older enrollments.
    metadata = getattr(enrollment, "metadata", {}) if enrollment else {}
    if isinstance(metadata, dict):
        platform_fields = {
            "linkedin_url": "linkedin",
            "github_url": "github",
            "twitter_url": "x",
            "x_url": "x",
            "facebook_url": "facebook",
            "instagram_url": "instagram",
            "tiktok_url": "tiktok",
        }
        for field_name, platform in platform_fields.items():
            value = metadata.get(field_name)
            if isinstance(value, str):
                _append_profile(platform=platform, url=value, display=display_name)

        raw_profiles = metadata.get("social_profiles")
        if isinstance(raw_profiles, list):
            for item in raw_profiles:
                if isinstance(item, dict):
                    _append_profile(
                        platform=str(item.get("platform", "")),
                        url=str(item.get("url", "")),
                        username=str(item.get("username", "")),
                        display=str(item.get("display_name", "") or display_name),
                    )
                elif isinstance(item, str):
                    _append_profile(url=item, display=display_name)

    return profiles, consent_provided
