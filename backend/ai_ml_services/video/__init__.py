"""Video analysis and interview intelligence services."""

from ai_ml_services.video.identity_matcher import (
    IdentityMatcher,
    match_candidate_identity,
)

__all__ = [
    "IdentityMatcher",
    "match_candidate_identity",
]
