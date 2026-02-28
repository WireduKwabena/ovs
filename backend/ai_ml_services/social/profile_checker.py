"""Consent-gated social profile verification (advisory only)."""

from __future__ import annotations

import logging
import re
from typing import Dict, List, Sequence
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

_PLATFORM_ALIASES = {
    "linkedin": "linkedin",
    "github": "github",
    "twitter": "x",
    "x": "x",
    "xcom": "x",
    "facebook": "facebook",
    "instagram": "instagram",
    "tiktok": "tiktok",
}

_PLATFORM_DOMAINS = {
    "linkedin": ("linkedin.com",),
    "github": ("github.com",),
    "x": ("x.com", "twitter.com"),
    "facebook": ("facebook.com", "fb.com"),
    "instagram": ("instagram.com",),
    "tiktok": ("tiktok.com",),
}

_USERNAME_PATTERNS = {
    "default": re.compile(r"^[A-Za-z0-9._-]{2,64}$"),
    "linkedin": re.compile(r"^[A-Za-z0-9-]{3,100}$"),
}


class SocialProfileChecker:
    """Validate declared social profile identifiers without scraping content."""

    def __init__(
        self,
        verify_urls: bool = False,
        request_timeout: float = 5.0,
        require_consent: bool = True,
        allowed_platforms: Sequence[str] | None = None,
    ) -> None:
        self.verify_urls = bool(verify_urls)
        self.request_timeout = float(request_timeout)
        self.require_consent = bool(require_consent)

        normalized_allowed: set[str] = set()
        for raw in (allowed_platforms or []):
            mapped = self._normalize_platform_name(str(raw))
            if mapped != "unknown":
                normalized_allowed.add(mapped)
        self.allowed_platforms = normalized_allowed or set(_PLATFORM_DOMAINS.keys())

    @staticmethod
    def _normalize_platform_name(value: str) -> str:
        raw = str(value or "").strip().lower().replace(" ", "")
        return _PLATFORM_ALIASES.get(raw, raw if raw in _PLATFORM_DOMAINS else "unknown")

    def _normalize_platform(self, platform: str, url: str) -> str:
        normalized = self._normalize_platform_name(platform)
        if normalized != "unknown":
            return normalized

        parsed = self._parse_url(url)
        if parsed is None:
            return "unknown"

        host = (parsed.netloc or "").lower()
        if host.startswith("www."):
            host = host[4:]

        for name, domains in _PLATFORM_DOMAINS.items():
            if any(host == domain or host.endswith(f".{domain}") for domain in domains):
                return name
        return "unknown"

    @staticmethod
    def _parse_url(url: str):
        cleaned = str(url or "").strip()
        if not cleaned:
            return None
        if "://" not in cleaned:
            cleaned = f"https://{cleaned}"
        return urlparse(cleaned)

    def _validate_url(self, url: str, platform: str) -> tuple[bool, str, str | None]:
        parsed = self._parse_url(url)
        if parsed is None:
            return False, "", "missing_url"

        if parsed.scheme not in {"http", "https"}:
            return False, "", "invalid_scheme"

        host = (parsed.netloc or "").lower().strip()
        if host.startswith("www."):
            host = host[4:]
        if not host:
            return False, "", "missing_host"

        expected_domains = _PLATFORM_DOMAINS.get(platform)
        if expected_domains and not any(host == domain or host.endswith(f".{domain}") for domain in expected_domains):
            return False, "", f"domain_mismatch_expected_{platform}"

        normalized = parsed._replace(scheme=parsed.scheme.lower()).geturl()
        return True, normalized, None

    def _extract_username_from_url(self, url: str, platform: str) -> str:
        parsed = urlparse(url)
        segments = [segment.strip() for segment in (parsed.path or "").split("/") if segment.strip()]
        if not segments:
            return ""

        first = segments[0]
        if first.startswith("@"):
            return first[1:]

        # LinkedIn profile paths commonly use /in/<handle>.
        if platform == "linkedin" and first.lower() in {"in", "pub"} and len(segments) > 1:
            candidate = segments[1]
            if candidate.startswith("@"):
                return candidate[1:]
            return candidate

        return first

    def _validate_username(self, username: str, platform: str) -> tuple[bool, str | None]:
        cleaned = str(username or "").strip()
        if not cleaned:
            return False, "missing_username"

        pattern = _USERNAME_PATTERNS.get(platform, _USERNAME_PATTERNS["default"])
        if not pattern.match(cleaned):
            return False, "invalid_username_format"
        return True, None

    def _probe_url(self, url: str) -> tuple[bool | None, int | None, str | None]:
        if not self.verify_urls:
            return None, None, None
        try:
            import requests
        except Exception:
            return None, None, "requests_not_installed"

        try:
            response = requests.head(url, allow_redirects=True, timeout=self.request_timeout)
            if response.status_code == 405:
                response = requests.get(url, allow_redirects=True, timeout=self.request_timeout, stream=True)
            reachable = response.status_code < 400
            return reachable, int(response.status_code), None
        except Exception as exc:
            return False, None, str(exc)

    @staticmethod
    def _risk_level_from_score(score: float) -> str:
        if score >= 80:
            return "low"
        if score >= 60:
            return "medium"
        return "high"

    def check_profiles(
        self,
        profiles: Sequence[Dict],
        consent_provided: bool,
        case_id: str | None = None,
    ) -> Dict:
        case_id = case_id or "unknown"
        profile_list = list(profiles or [])

        if self.require_consent and not bool(consent_provided):
            return {
                "case_id": case_id,
                "consent_provided": False,
                "profiles_checked": 0,
                "overall_score": 0.0,
                "risk_level": "high",
                "recommendation": "MANUAL_REVIEW",
                "automated_decision_allowed": False,
                "decision_constraints": [
                    {
                        "code": "social_consent_missing",
                        "reason": "Social profile checks require explicit candidate consent.",
                    },
                    {
                        "code": "social_check_advisory_only",
                        "reason": "Social profile checks are advisory and must not be auto-decisive.",
                    },
                ],
                "profiles": [],
            }

        profile_results: List[Dict] = []
        for item in profile_list:
            platform_raw = str(item.get("platform", "") or "")
            url_raw = str(item.get("url", "") or "")
            username_raw = str(item.get("username", "") or "")
            display_name = str(item.get("display_name", "") or "")

            resolved_platform = self._normalize_platform(platform_raw, url_raw)
            findings: List[str] = []
            risk_points = 0

            if resolved_platform not in self.allowed_platforms:
                findings.append("platform_not_allowed")
                risk_points += 20

            url_valid, normalized_url, url_error = self._validate_url(url_raw, resolved_platform)
            if url_raw and not url_valid:
                findings.append(url_error or "invalid_url")
                risk_points += 25

            username = username_raw.strip()
            if not username and normalized_url:
                username = self._extract_username_from_url(normalized_url, resolved_platform)

            username_valid, username_error = self._validate_username(username, resolved_platform)
            if not username_valid:
                findings.append(username_error or "invalid_username")
                risk_points += 15

            reachable, status_code, probe_error = self._probe_url(normalized_url or url_raw)
            if self.verify_urls:
                if reachable is False:
                    findings.append("profile_url_unreachable")
                    risk_points += 20
                if probe_error:
                    findings.append("profile_url_probe_error")
                    risk_points += 10

            score = max(0.0, 100.0 - float(risk_points))
            profile_results.append(
                {
                    "platform": resolved_platform,
                    "provided_platform": platform_raw,
                    "url": normalized_url,
                    "username": username,
                    "display_name": display_name,
                    "score": round(score, 3),
                    "risk_level": self._risk_level_from_score(score),
                    "findings": findings,
                    "url_reachable": reachable,
                    "url_status_code": status_code,
                    "probe_error": probe_error,
                }
            )

        if profile_results:
            overall_score = float(sum(item["score"] for item in profile_results) / len(profile_results))
        else:
            overall_score = 50.0

        decision_constraints = [
            {
                "code": "social_check_advisory_only",
                "reason": "Social profile checks are advisory and must not be auto-decisive.",
            }
        ]
        if not profile_results:
            decision_constraints.append(
                {
                    "code": "social_profiles_missing",
                    "reason": "No social profiles were provided for social-profile checks.",
                }
            )

        result = {
            "case_id": case_id,
            "consent_provided": bool(consent_provided),
            "profiles_checked": len(profile_results),
            "overall_score": round(overall_score, 3),
            "risk_level": self._risk_level_from_score(overall_score),
            "recommendation": "MANUAL_REVIEW",
            "automated_decision_allowed": False,
            "decision_constraints": decision_constraints,
            "profiles": profile_results,
        }
        logger.info(
            "Social profile check completed for case=%s: profiles=%d score=%.2f",
            case_id,
            len(profile_results),
            overall_score,
        )
        return result
