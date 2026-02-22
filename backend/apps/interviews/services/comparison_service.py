"""Side-by-side comparison service for completed interview sessions."""

from __future__ import annotations

from statistics import mean
from typing import Dict, Iterable, List

from django.db.models import Q

from apps.interviews.models import InterviewSession


class ApplicantComparisonService:
    """Compare completed interview sessions across normalized metrics."""

    RANK_METRICS = (
        ("overall_score", "desc", 0.35),
        ("avg_response_quality", "desc", 0.20),
        ("avg_confidence_level", "desc", 0.15),
        ("avg_eye_contact", "desc", 0.10),
        ("avg_stress_level", "asc", 0.10),
        ("open_concerns", "asc", 0.10),
    )

    @classmethod
    def compare_sessions(cls, session_identifiers: Iterable[str | int]) -> Dict:
        sessions = cls._load_sessions(session_identifiers)
        if not sessions:
            return {"error": "No completed sessions found for supplied identifiers."}

        profiles = [cls._build_profile(session) for session in sessions]
        cls._add_rankings(profiles)
        recommendation = cls._build_recommendation(profiles)

        return {
            "sessions": profiles,
            "recommendation": recommendation,
        }

    @staticmethod
    def _load_sessions(session_identifiers: Iterable[str | int]) -> List[InterviewSession]:
        raw_values = [str(value).strip() for value in session_identifiers if str(value).strip()]
        if not raw_values:
            return []

        numeric_ids = [int(value) for value in raw_values if value.isdigit()]
        string_ids = [value for value in raw_values if not value.isdigit()]

        query = Q(status="completed")
        id_filter = Q()
        if numeric_ids:
            id_filter |= Q(id__in=numeric_ids)
        if string_ids:
            id_filter |= Q(session_id__in=string_ids)

        queryset = (
            InterviewSession.objects.filter(query & id_filter)
            .select_related("case", "case__applicant")
            .prefetch_related("responses__video_analysis", "case__interrogation_flags")
        )
        return list(queryset)

    @staticmethod
    def _build_profile(session: InterviewSession) -> Dict:
        responses = list(session.responses.all())
        analyses = [response.video_analysis for response in responses if hasattr(response, "video_analysis")]

        quality_scores = [
            float(response.response_quality_score)
            for response in responses
            if response.response_quality_score is not None
        ]
        confidence_levels = [
            float(analysis.confidence_level)
            for analysis in analyses
            if analysis.confidence_level is not None
        ]
        eye_contact_scores = [
            float(analysis.eye_contact_percentage)
            for analysis in analyses
            if analysis.eye_contact_percentage is not None
        ]
        stress_scores = [
            float(analysis.stress_level)
            for analysis in analyses
            if analysis.stress_level is not None
        ]

        concerns = sum(len(response.concerns_detected or []) for response in responses)
        open_flags = session.case.interrogation_flags.exclude(
            status__in=["resolved", "dismissed"]
        ).count()

        applicant = session.case.applicant
        full_name = applicant.get_full_name().strip() if hasattr(applicant, "get_full_name") else ""
        applicant_name = full_name or getattr(applicant, "email", "")

        return {
            "session_id": session.session_id,
            "session_pk": session.id,
            "applicant_name": applicant_name,
            "applicant_email": getattr(applicant, "email", ""),
            "overall_score": float(session.overall_score or 0.0),
            "avg_response_quality": mean(quality_scores) if quality_scores else 0.0,
            "avg_confidence_level": mean(confidence_levels) if confidence_levels else 0.0,
            "avg_eye_contact": mean(eye_contact_scores) if eye_contact_scores else 0.0,
            "avg_stress_level": mean(stress_scores) if stress_scores else 0.0,
            "questions_asked": int(session.total_questions_asked or 0),
            "open_concerns": int(concerns + open_flags),
            "duration_seconds": int(session.duration_seconds or 0),
            "flags_resolved_count": int(session.flags_resolved_count or 0),
            "flags_unresolved_count": int(session.flags_unresolved_count or 0),
        }

    @classmethod
    def _add_rankings(cls, profiles: List[Dict]) -> None:
        for metric, direction, _weight in cls.RANK_METRICS:
            sorted_profiles = sorted(
                profiles,
                key=lambda row: row.get(metric, 0.0),
                reverse=(direction == "desc"),
            )
            for rank, row in enumerate(sorted_profiles, start=1):
                row[f"{metric}_rank"] = rank

        for row in profiles:
            score = 0.0
            for metric, _direction, weight in cls.RANK_METRICS:
                score += row.get(f"{metric}_rank", len(profiles)) * weight
            row["weighted_rank_score"] = round(score, 4)

    @staticmethod
    def _build_recommendation(profiles: List[Dict]) -> Dict:
        best = min(profiles, key=lambda row: row["weighted_rank_score"])
        ordered = sorted(profiles, key=lambda row: row["weighted_rank_score"])
        runner_up = ordered[1] if len(ordered) > 1 else None

        confidence = 100.0
        if runner_up is not None:
            gap = runner_up["weighted_rank_score"] - best["weighted_rank_score"]
            confidence = max(0.0, min(100.0, gap * 50.0))

        return {
            "top_session_id": best["session_id"],
            "top_applicant_name": best["applicant_name"],
            "top_applicant_email": best["applicant_email"],
            "confidence": round(confidence, 2),
            "reasoning": (
                f"{best['applicant_name']} ranked highest on weighted interview quality, "
                "confidence, behavioral stability, and concern minimization."
            ),
        }

