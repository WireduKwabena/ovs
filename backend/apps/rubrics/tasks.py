# backend/apps/rubrics/tasks.py
from celery import shared_task
from .models import VettingRubric
from .engine import RubricEvaluationEngine
from apps.applications import VettingCase
from apps.notifications.services import NotificationService

@shared_task
def evaluate_application_with_rubric(application_id, rubric_id):
    """Evaluate application using specified rubric"""
    try:
        application = VettingCase.objects.get(id=application_id)
        rubric = VettingRubric.objects.get(id=rubric_id)
        
        # Run evaluation
        engine = RubricEvaluationEngine(application, rubric)
        evaluation = engine.evaluate()
        
        # Update application status based on evaluation
        if evaluation.ai_recommendation == 'AUTO_APPROVE':
            application.status = 'approved'
            application.notes = f'Auto-approved (Score: {evaluation.overall_score:.1f}%)'
        elif evaluation.ai_recommendation == 'AUTO_REJECT':
            application.status = 'rejected'
            application.notes = f'Auto-rejected (Score: {evaluation.overall_score:.1f}%)'
        else:
            application.status = 'under_review'
            application.notes = f'Manual review required (Score: {evaluation.overall_score:.1f}%)'
        
        application.save()
        
        # Send notification
        NotificationService.send_evaluation_complete(
            application=application,
            evaluation=evaluation
        )
        
        return {
            'success': True,
            'evaluation_id': evaluation.id,
            'overall_score': evaluation.overall_score,
            'recommendation': evaluation.ai_recommendation
        }
    
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }

@shared_task
def auto_assign_rubric(application_id):
    """Automatically assign appropriate rubric based on application type"""
    try:
        application = VettingCase.objects.get(id=application_id)
        
        # Find matching rubric
        rubrics = VettingRubric.objects.filter(
            status='active',
            rubric_type=application.application_type
        )
        
        # Filter by department/position if available
        if hasattr(application, 'department') and application.department:
            rubrics = rubrics.filter(department=application.department)
        
        if hasattr(application, 'position_level') and application.position_level:
            rubrics = rubrics.filter(position_level=application.position_level)
        
        # Get the most recently updated active rubric
        rubric = rubrics.order_by('-updated_at').first()
        
        if rubric:
            # Assign and evaluate
            evaluate_application_with_rubric.delay(application_id, rubric.id)
            return {
                'success': True,
                'rubric_id': rubric.id,
                'rubric_name': rubric.name
            }
        else:
            return {
                'success': False,
                'error': 'No matching rubric found'
            }
    
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }