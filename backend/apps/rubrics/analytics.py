# backend/apps/rubrics/analytics.py
from django.db.models import Avg, Count
from .models import RubricEvaluation, VettingRubric

class RubricAnalytics:
    @staticmethod
    def get_rubric_performance(rubric_id):
        """Get performance metrics for a rubric"""
        evaluations = RubricEvaluation.objects.filter(rubric_id=rubric_id)
        
        return {
            'total_evaluations': evaluations.count(),
            'average_score': evaluations.aggregate(Avg('overall_score'))['overall_score__avg'],
            'pass_rate': evaluations.filter(passed=True).count() / evaluations.count() * 100,
            'auto_approve_rate': evaluations.filter(
                ai_recommendation='AUTO_APPROVE'
            ).count() / evaluations.count() * 100,
            'auto_reject_rate': evaluations.filter(
                ai_recommendation='AUTO_REJECT'
            ).count() / evaluations.count() * 100,
        }
    
    @staticmethod
    def get_criterion_statistics(rubric_id):
        """Get statistics for each criterion"""
        rubric = VettingRubric.objects.get(id=rubric_id)
        evaluations = RubricEvaluation.objects.filter(rubric=rubric)
        
        stats = []
        for criterion in rubric.criteria.all():
            criterion_scores = [
                eval.criteria_scores.get(str(criterion.id), {}).get('score', 0)
                for eval in evaluations
            ]
            
            stats.append({
                'criterion_name': criterion.name,
                'average_score': sum(criterion_scores) / len(criterion_scores) if criterion_scores else 0,
                'pass_rate': sum(1 for s in criterion_scores if s >= criterion.minimum_score) / len(criterion_scores) * 100 if criterion_scores else 0,
            })
        
        return stats