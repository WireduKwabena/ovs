"""Playback data builder for interview review flows."""

from __future__ import annotations

import uuid
from typing import Dict, List

from django.db.models import Prefetch

from apps.interviews.models import InterviewResponse, InterviewSession


class InterviewPlaybackService:
    """Build a normalized timeline payload for one interview session."""

    @classmethod
    def get_playback_data(cls, session_identifier: str | int) -> Dict:
        session = cls._load_session(session_identifier)
        timeline = cls._build_timeline(session)
        highlights = cls._build_highlights(timeline)

        applicant = session.case.applicant
        full_name = applicant.get_full_name().strip() if hasattr(applicant, "get_full_name") else ""

        return {
            "session": {
                "id": session.id,
                "session_id": session.session_id,
                "status": session.status,
                "applicant_name": full_name or getattr(applicant, "email", ""),
                "applicant_email": getattr(applicant, "email", ""),
                "started_at": session.started_at.isoformat() if session.started_at else None,
                "completed_at": session.completed_at.isoformat() if session.completed_at else None,
                "duration_seconds": session.duration_seconds,
                "overall_score": session.overall_score,
                "communication_score": session.communication_score,
                "consistency_score": session.consistency_score,
                "confidence_score": session.confidence_score,
                "summary": session.interview_summary,
                "key_findings": session.key_findings,
                "red_flags_detected": session.red_flags_detected,
            },
            "timeline": timeline,
            "highlights": highlights,
            "flags": list(
                session.case.interrogation_flags.values(
                    "id",
                    "flag_type",
                    "severity",
                    "status",
                    "title",
                    "description",
                    "resolution_summary",
                )
            ),
        }

    @staticmethod
    def _load_session(session_identifier: str | int) -> InterviewSession:
        queryset = InterviewSession.objects.prefetch_related(
            Prefetch(
                "responses",
                queryset=InterviewResponse.objects.select_related(
                    "question",
                    "target_flag",
                    "video_analysis",
                ).order_by("sequence_number"),
            ),
            "case__interrogation_flags",
        )
        identifier = str(session_identifier).strip()
        try:
            uuid.UUID(identifier)
            return queryset.get(id=identifier)
        except (ValueError, InterviewSession.DoesNotExist):
            return queryset.get(session_id=identifier)

    @classmethod
    def _build_timeline(cls, session: InterviewSession) -> List[Dict]:
        timeline: List[Dict] = []
        cursor = 0

        for response in session.responses.all():
            duration = int(response.response_duration_seconds or 0)
            start_at = cursor
            end_at = cursor + duration
            cursor = end_at

            video_analysis = getattr(response, "video_analysis", None)
            identity_payload = {}
            if video_analysis and isinstance(video_analysis.raw_analysis_data, dict):
                identity_payload = video_analysis.raw_analysis_data.get("identity_match", {}) or {}

            entry = {
                "sequence_number": response.sequence_number,
                "start_second": start_at,
                "end_second": end_at,
                "duration_seconds": duration,
                "question": {
                    "id": response.question_id,
                    "text": response.question.question_text,
                    "type": response.question.question_type,
                },
                "response": {
                    "id": response.id,
                    "transcript": response.transcript,
                    "video_url": response.video_url,
                    "video_file_url": cls._safe_file_url(response.video_file),
                    "answered_at": response.answered_at.isoformat() if response.answered_at else None,
                },
                "analysis": {
                    "sentiment": response.sentiment,
                    "sentiment_score": response.sentiment_score,
                    "response_quality_score": response.response_quality_score,
                    "relevance_score": response.relevance_score,
                    "completeness_score": response.completeness_score,
                    "coherence_score": response.coherence_score,
                    "concerns_detected": response.concerns_detected,
                    "key_points_extracted": response.key_points_extracted,
                    "video": {
                        "face_detected": getattr(video_analysis, "face_detected", False),
                        "eye_contact_percentage": getattr(
                            video_analysis, "eye_contact_percentage", None
                        ),
                        "confidence_level": getattr(video_analysis, "confidence_level", None),
                        "stress_level": getattr(video_analysis, "stress_level", None),
                        "behavioral_indicators": getattr(
                            video_analysis, "behavioral_indicators", []
                        ),
                    },
                    "identity_match": identity_payload,
                },
            }
            entry["critical"] = cls._critical_markers(entry)
            timeline.append(entry)

        return timeline

    @staticmethod
    def _safe_file_url(file_field) -> str | None:
        if not file_field:
            return None
        try:
            return file_field.url
        except (AttributeError, OSError, NotImplementedError, TypeError, ValueError):
            return None

    @staticmethod
    def _critical_markers(entry: Dict) -> Dict:
        reasons: List[str] = []
        quality = entry["analysis"].get("response_quality_score")
        stress = entry["analysis"]["video"].get("stress_level")
        confidence = entry["analysis"]["video"].get("confidence_level")
        identity = entry["analysis"].get("identity_match") or {}

        if quality is not None and quality < 40:
            reasons.append("low_response_quality")
        if stress is not None and stress > 70:
            reasons.append("high_stress")
        if confidence is not None and confidence < 35:
            reasons.append("low_visual_confidence")
        if identity.get("enabled") and identity.get("success") and not identity.get("is_match"):
            reasons.append("identity_mismatch")
        if entry["analysis"].get("concerns_detected"):
            reasons.append("concerns_detected")

        return {
            "is_critical": bool(reasons),
            "reasons": reasons,
        }

    @staticmethod
    def _build_highlights(timeline: List[Dict]) -> List[Dict]:
        highlights: List[Dict] = []
        for item in timeline:
            if not item["critical"]["is_critical"]:
                continue
            highlights.append(
                {
                    "sequence_number": item["sequence_number"],
                    "time_second": item["start_second"],
                    "title": f"Q{item['sequence_number']} critical segment",
                    "reasons": item["critical"]["reasons"],
                }
            )
        return highlights
