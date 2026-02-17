# ============================================================================
# PART 6: APPLICANT COMPARISON TOOL
# ============================================================================

# backend/apps/interviews/comparison_service.py
import numpy as np
from collections import Counter
from datetime import datetime

from apps.interviews.models import DynamicInterviewSession


class ApplicantComparisonService:
    """
    Compare multiple applicants side-by-side
    """

    @staticmethod
    def compare_applicants(session_ids: list):
        """
        Compare multiple applicants across key metrics

        Args:
            session_ids: List of session IDs to compare

        Returns:
            Comprehensive comparison data
        """

        sessions = DynamicInterviewSession.objects.filter(
            session_id__in=session_ids,
            status='completed'
        ).prefetch_related('exchanges', 'interrogation_flags')

        if not sessions.exists():
            return {'error': 'No completed sessions found'}

        comparisons = []

        for session in sessions:
            comparison_data = ApplicantComparisonService._build_comparison_profile(session)
            comparisons.append(comparison_data)

        # Add rankings
        comparisons = ApplicantComparisonService._add_rankings(comparisons)

        # Generate recommendation
        recommendation = ApplicantComparisonService._generate_recommendation(comparisons)

        return {
            'applicants': comparisons,
            'recommendation': recommendation,
            'comparison_date': datetime.now().isoformat()
        }

    @staticmethod
    def _build_comparison_profile(session):
        """Build complete profile for single applicant"""

        exchanges = session.exchanges.all()
        flags = session.interrogation_flags.all()

        # Calculate aggregate metrics
        deception_scores = [
            ex.nonverbal_analysis.deception_score
            for ex in exchanges
            if hasattr(ex, 'nonverbal_analysis') and ex.nonverbal_analysis.deception_score is not None
        ]

        response_qualities = [
            ex.response_quality_score
            for ex in exchanges
            if ex.response_quality_score is not None
        ]

        eye_contacts = [
            ex.nonverbal_analysis.eye_contact_percentage
            for ex in exchanges
            if hasattr(ex, 'nonverbal_analysis') and ex.nonverbal_analysis.eye_contact_percentage is not None
        ]

        # Count behavioral indicators
        all_red_flags = []
        for ex in exchanges:
            if hasattr(ex, 'nonverbal_analysis') and ex.nonverbal_analysis.behavioral_red_flags:
                all_red_flags.extend(ex.nonverbal_analysis.behavioral_red_flags)

        return {
            'session_id': session.session_id,
            'applicant_name': session.application.applicant.full_name,
            'applicant_email': session.application.applicant.email,

            # Core scores
            'overall_score': session.overall_score,
            'confidence_score': session.confidence_score,
            'consistency_score': session.consistency_score,
            'completeness_score': session.completeness_score,

            # Behavioral metrics
            'avg_deception_score': round(np.mean(deception_scores), 1) if deception_scores else 0,
            'max_deception_score': round(np.max(deception_scores), 1) if deception_scores else 0,
            'avg_eye_contact': round(np.mean(eye_contacts), 1) if eye_contacts else 0,
            'avg_response_quality': round(np.mean(response_qualities), 1) if response_qualities else 0,

            # Interview metrics
            'duration_minutes': round(session.duration_seconds / 60, 1),
            'questions_asked': session.current_question_number,
            'avg_response_time': round(session.duration_seconds / session.current_question_number, 0) if session.current_question_number > 0 else 0,

            # Flags
            'total_flags': flags.count(),
            'critical_flags': flags.filter(severity='critical').count(),
            'resolved_flags': flags.filter(status='resolved').count(),
            'unresolved_flags': flags.filter(status='unresolved').count(),
            'flag_resolution_rate': round((flags.filter(status='resolved').count() / flags.count() * 100), 1) if flags.count() > 0 else 100,

            # Behavioral analysis
            'total_red_flags': len(all_red_flags),
            'unique_red_flags': len(set(all_red_flags)),
            'most_common_red_flags': ApplicantComparisonService._count_most_common(all_red_flags, 3),

            # Final assessment
            'recommendation': session.recommendations,
            'ai_summary': session.interview_summary[:200] + '...' if session.interview_summary and len(session.interview_summary) > 200 else session.interview_summary
        }

    @staticmethod
    def _add_rankings(comparisons):
        """Add rankings for each metric"""

        metrics_to_rank = [
            ('overall_score', 'desc'),
            ('avg_deception_score', 'asc'),
            ('avg_response_quality', 'desc'),
            ('flag_resolution_rate', 'desc'),
            ('avg_eye_contact', 'desc'),
            ('total_flags', 'asc'),
            ('total_red_flags', 'asc')
        ]

        for metric, direction in metrics_to_rank:
            # Sort and assign ranks
            sorted_comparisons = sorted(
                comparisons,
                key=lambda x: x[metric] if x[metric] is not None else (0 if direction == 'desc' else 999),
                reverse=(direction == 'desc')
            )

            for i, comp in enumerate(sorted_comparisons, start=1):
                # Find the original comparison object and update it
                for original_comp in comparisons:
                    if original_comp['session_id'] == comp['session_id']:
                        original_comp[f'{metric}_rank'] = i
                        break

        return comparisons

    @staticmethod
    def _count_most_common(items: list, n: int) -> list:
        """Count the n most common items in a list."""
        if not items:
            return []
        counter = Counter(items)
        return [{'item': item, 'count': count} for item, count in counter.most_common(n)]

    @staticmethod
    def _generate_recommendation(comparisons):
        """
        Generate a final recommendation based on a weighted score of ranks.
        """
        if not comparisons:
            return {
                'top_candidate': None,
                'reasoning': 'No applicants to compare.',
                'confidence': 0.0
            }

        # Define weights for each rank
        rank_weights = {
            'overall_score_rank': 0.4,
            'avg_deception_score_rank': 0.2,
            'avg_response_quality_rank': 0.2,
            'flag_resolution_rate_rank': 0.1,
            'total_flags_rank': 0.05,
            'total_red_flags_rank': 0.05
        }

        # Calculate a weighted rank score for each applicant
        for comp in comparisons:
            weighted_score = 0
            for metric, weight in rank_weights.items():
                # Lower rank is better, so we use the rank directly
                weighted_score += comp.get(metric, len(comparisons)) * weight
            comp['weighted_rank_score'] = weighted_score

        # The applicant with the lowest weighted_rank_score is the best
        top_candidate = sorted(comparisons, key=lambda x: x['weighted_rank_score'])[0]

        # Generate reasoning
        reasoning = (
            f"Based on a side-by-side comparison, {top_candidate['applicant_name']} is the top candidate. "
            f"They ranked highest in Overall Score (Rank: {top_candidate.get('overall_score_rank', 'N/A')}) "
            f"and demonstrated strong performance in Response Quality (Rank: {top_candidate.get('avg_response_quality_rank', 'N/A')}) "
            f"and low Deception Score (Rank: {top_candidate.get('avg_deception_score_rank', 'N/A')})."
        )

        # Calculate confidence based on the score difference between the top two candidates
        if len(comparisons) > 1:
            second_candidate = sorted(comparisons, key=lambda x: x['weighted_rank_score'])[1]
            score_diff = second_candidate['weighted_rank_score'] - top_candidate['weighted_rank_score']
            # Normalize the confidence score (this is a heuristic)
            confidence = min(1.0, score_diff / 2.0) * 100
        else:
            confidence = 100.0

        return {
            'top_candidate': {
                'name': top_candidate['applicant_name'],
                'email': top_candidate['applicant_email'],
                'session_id': top_candidate['session_id']
            },
            'reasoning': reasoning,
            'confidence': round(confidence, 1)
        }
