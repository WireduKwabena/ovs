"""Interview video analysis pipeline helpers."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, Optional

from ai_ml_services.video.transcription import TranscriptionService
from ai_ml_services.video.sentiment_analyzer import SentimentAnalyzer
from ai_ml_services.video.face_analyzer import FaceAnalyzer
from ai_ml_services.video.identity_matcher import IdentityMatcher

logger = logging.getLogger(__name__)


def run_interview_pipeline(
    video_path: str,
    document_path: Optional[str] = None,
    transcriber: Optional[TranscriptionService] = None,
    sentiment_analyzer: Optional[SentimentAnalyzer] = None,
    face_analyzer: Optional[FaceAnalyzer] = None,
    identity_matcher: Optional[IdentityMatcher] = None,
) -> Dict:
    """
    Run transcription + transcript sentiment + face engagement on one interview file.

    If `document_path` is provided, identity matching is also performed:
    document face vs interview face.
    """
    if not Path(video_path).exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")
    if document_path and not Path(document_path).exists():
        raise FileNotFoundError(f"Document file not found: {document_path}")

    transcriber = transcriber or TranscriptionService(model_size="base")
    sentiment_analyzer = sentiment_analyzer or SentimentAnalyzer()
    face_analyzer = face_analyzer or FaceAnalyzer()

    transcription = transcriber.transcribe_video(video_path)
    sentiment = sentiment_analyzer.comprehensive_analysis(
        transcription.get("transcript", "")
    )
    face_metrics = face_analyzer.analyze_video(video_path)
    identity_metrics = None
    if document_path:
        try:
            identity_matcher = identity_matcher or IdentityMatcher()
            identity_metrics = identity_matcher.match_document_to_interview(
                document_path=document_path,
                interview_video_path=video_path,
            )
        except Exception as exc:
            logger.exception("Identity matching failed during interview pipeline: %s", exc)
            identity_metrics = {
                "enabled": True,
                "success": False,
                "error": str(exc),
                "is_match": False,
            }

    return {
        "transcription": transcription,
        "sentiment": sentiment,
        "face": face_metrics,
        "identity_match": identity_metrics,
    }
