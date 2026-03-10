"""Video analysis and interview intelligence services.

Optional CV dependencies are loaded lazily so package import remains safe in
environments without ML extras installed.
"""

__all__ = [
    "IdentityMatcher",
    "match_candidate_identity",
]


def __getattr__(name):
    if name in {"IdentityMatcher", "match_candidate_identity"}:
        from ai_ml_services.video.identity_matcher import (
            IdentityMatcher,
            match_candidate_identity,
        )

        exports = {
            "IdentityMatcher": IdentityMatcher,
            "match_candidate_identity": match_candidate_identity,
        }
        return exports[name]
    raise AttributeError(name)
