"""Analytics services aligned with current interview/applications models."""

from __future__ import annotations

from datetime import timedelta
from typing import Dict, List

from django.db.models import Avg, Count, Q, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from apps.applications.models import InterrogationFlag
from apps.interviews.models import InterviewResponse, InterviewSession, VideoAnalysis


class InterviewAnalytics:
    """Aggregate analytics for interviews and related case flags."""

    @staticmethod
    def _window_start(days: int) -> timezone.datetime:
        return timezone.now() - timedelta(days=max(1, int(days)))

    @classmethod
    def get_dashboard_metrics(cls, days: int = 30) -> Dict:
        start_date = cls._window_start(days)
        sessions = InterviewSession.objects.filter(created_at__gte=start_date)
        responses = InterviewResponse.objects.filter(session__created_at__gte=start_date)
        analyses = VideoAnalysis.objects.filter(response__session__created_at__gte=start_date)
        flags = InterrogationFlag.objects.filter(
            case__interview_sessions__created_at__gte=start_date
        ).distinct()

        total_interviews = sessions.count()
        completed_sessions = sessions.filter(status="completed")
        completed_interviews = completed_sessions.count()

        completion_rate = (
            (completed_interviews / total_interviews) * 100 if total_interviews else 0.0
        )
        avg_duration_seconds = (
            completed_sessions.aggregate(v=Avg("duration_seconds")).get("v") or 0.0
        )
        total_duration_seconds = sessions.aggregate(v=Sum("duration_seconds")).get("v") or 0.0

        avg_questions = completed_sessions.aggregate(v=Avg("total_questions_asked")).get("v") or 0.0
        avg_overall = sessions.aggregate(v=Avg("overall_score")).get("v") or 0.0
        avg_response_quality = responses.aggregate(v=Avg("response_quality_score")).get("v") or 0.0
        avg_eye_contact = analyses.aggregate(v=Avg("eye_contact_percentage")).get("v") or 0.0
        avg_stress = analyses.aggregate(v=Avg("stress_level")).get("v") or 0.0

        resolved_flags = flags.filter(status="resolved").count()
        total_flags = flags.count()
        unresolved_flags = flags.exclude(status__in=["resolved", "dismissed"]).count()
        flag_resolution_rate = ((resolved_flags / total_flags) * 100) if total_flags else 0.0

        estimated_cost = (total_duration_seconds / 60.0) * 0.50

        return {
            "window_days": int(days),
            "overview": {
                "total_interviews": total_interviews,
                "completed_interviews": completed_interviews,
                "completion_rate": round(completion_rate, 2),
                "in_progress": sessions.filter(status="in_progress").count(),
                "failed": sessions.filter(status="failed").count(),
                "cancelled": sessions.filter(status="cancelled").count(),
            },
            "performance": {
                "avg_duration_minutes": round(avg_duration_seconds / 60.0, 2),
                "avg_questions_asked": round(avg_questions, 2),
                "avg_overall_score": round(avg_overall, 2),
                "avg_response_quality": round(avg_response_quality, 2),
                "avg_eye_contact_percentage": round(avg_eye_contact, 2),
                "avg_stress_level": round(avg_stress, 2),
            },
            "flags": {
                "total_flags": total_flags,
                "resolved_flags": resolved_flags,
                "unresolved_flags": unresolved_flags,
                "resolution_rate": round(flag_resolution_rate, 2),
                "critical_flags": flags.filter(severity="critical").count(),
            },
            "cost": {
                "total_minutes": round(total_duration_seconds / 60.0, 2),
                "estimated_cost": round(estimated_cost, 2),
                "cost_per_interview": round(
                    estimated_cost / total_interviews, 2
                )
                if total_interviews
                else 0.0,
            },
        }

    @classmethod
    def get_trend_data(cls, days: int = 30) -> Dict:
        start_date = cls._window_start(days)
        rows = (
            InterviewSession.objects.filter(created_at__gte=start_date)
            .annotate(day=TruncDate("created_at"))
            .values("day")
            .annotate(
                interviews=Count("id"),
                completed=Count("id", filter=Q(status="completed")),
                avg_score=Avg("overall_score"),
            )
            .order_by("day")
        )

        return {
            "dates": [row["day"].isoformat() for row in rows],
            "interviews": [int(row["interviews"]) for row in rows],
            "completed": [int(row["completed"]) for row in rows],
            "avg_scores": [round(float(row["avg_score"] or 0.0), 2) for row in rows],
        }

    @classmethod
    def get_flag_breakdown(cls, days: int = 30) -> List[Dict]:
        start_date = cls._window_start(days)
        rows = (
            InterrogationFlag.objects.filter(
                case__interview_sessions__created_at__gte=start_date
            )
            .values("flag_type")
            .annotate(
                count=Count("id", distinct=True),
                resolved=Count("id", filter=Q(status="resolved"), distinct=True),
                critical=Count("id", filter=Q(severity="critical"), distinct=True),
            )
            .order_by("-count")
        )
        return list(rows)

    @classmethod
    def get_behavioral_analysis(cls, days: int = 30) -> Dict:
        start_date = cls._window_start(days)
        analyses = VideoAnalysis.objects.filter(response__session__created_at__gte=start_date)

        low_stress = analyses.filter(stress_level__lt=30).count()
        medium_stress = analyses.filter(stress_level__gte=30, stress_level__lt=70).count()
        high_stress = analyses.filter(stress_level__gte=70).count()
        fidget_count = analyses.filter(fidgeting_detected=True).count()
        total = analyses.count()

        return {
            "stress_distribution": {
                "low": low_stress,
                "medium": medium_stress,
                "high": high_stress,
            },
            "fidgeting_rate": round((fidget_count / total) * 100, 2) if total else 0.0,
            "average_confidence_level": round(
                float(analyses.aggregate(v=Avg("confidence_level")).get("v") or 0.0), 2
            ),
        }

    @classmethod
    def get_interview_quality_metrics(cls, days: int = 30) -> Dict:
        start_date = cls._window_start(days)
        responses = InterviewResponse.objects.filter(session__created_at__gte=start_date)

        return {
            "avg_response_quality": round(
                float(responses.aggregate(v=Avg("response_quality_score")).get("v") or 0.0),
                2,
            ),
            "avg_relevance": round(
                float(responses.aggregate(v=Avg("relevance_score")).get("v") or 0.0),
                2,
            ),
            "avg_completeness": round(
                float(responses.aggregate(v=Avg("completeness_score")).get("v") or 0.0),
                2,
            ),
            "avg_coherence": round(
                float(responses.aggregate(v=Avg("coherence_score")).get("v") or 0.0),
                2,
            ),
        }

