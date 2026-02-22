"""Rubric analytics helpers."""

from django.db.models import Avg

from .models import RubricEvaluation, VettingRubric


class RubricAnalytics:
    @staticmethod
    def get_rubric_performance(rubric_id):
        """Get aggregate performance metrics for a rubric."""
        evaluations = RubricEvaluation.objects.filter(rubric_id=rubric_id)
        total = evaluations.count()
        if total == 0:
            return {
                "total_evaluations": 0,
                "average_score": None,
                "pass_rate": 0.0,
                "auto_approve_rate": 0.0,
                "auto_reject_rate": 0.0,
            }

        average_score = evaluations.aggregate(Avg("total_weighted_score"))["total_weighted_score__avg"]
        return {
            "total_evaluations": total,
            "average_score": average_score,
            "pass_rate": evaluations.filter(passes_threshold=True).count() / total * 100,
            "auto_approve_rate": evaluations.filter(final_decision="auto_approved").count() / total * 100,
            "auto_reject_rate": evaluations.filter(final_decision="auto_rejected").count() / total * 100,
        }

    @staticmethod
    def get_criterion_statistics(rubric_id):
        """Get statistics for each criterion within a rubric."""
        rubric = VettingRubric.objects.get(id=rubric_id)
        evaluations = RubricEvaluation.objects.filter(rubric=rubric)

        stats = []
        for criterion in rubric.criteria.all():
            criterion_scores = [
                evaluation.criteria_scores.get(str(criterion.id), {}).get("score")
                for evaluation in evaluations
            ]
            criterion_scores = [score for score in criterion_scores if score is not None]

            if criterion_scores:
                average_score = sum(criterion_scores) / len(criterion_scores)
            else:
                average_score = 0.0

            if criterion.minimum_score is None:
                pass_rate = 100.0 if criterion_scores else 0.0
            else:
                pass_rate = (
                    sum(1 for score in criterion_scores if score >= criterion.minimum_score)
                    / len(criterion_scores)
                    * 100
                    if criterion_scores
                    else 0.0
                )

            stats.append(
                {
                    "criterion_name": criterion.name,
                    "average_score": average_score,
                    "pass_rate": pass_rate,
                }
            )

        return stats
