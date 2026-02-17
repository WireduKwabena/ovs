# backend/apps/rubrics/views.py
# From: Dynamic Vetting Rubrics PDF

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from .models import VettingRubric, RubricCriteria, RubricEvaluation, CriteriaOverride
from .serializers import (
    VettingRubricSerializer, VettingRubricCreateSerializer,
    RubricEvaluationSerializer,
    CriteriaOverrideSerializer
)
from .engine import RubricEvaluationEngine
from apps.applications import VettingCase


class VettingRubricViewSet(viewsets.ModelViewSet):
    """
    API endpoints for managing vetting rubrics
    From: Dynamic Vetting Rubrics PDF
    """
    queryset = VettingRubric.objects.all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'rubric_type', 'department']
    search_fields = ['name', 'description']
    ordering_fields = ['created_at', 'updated_at', 'name']
    ordering = ['-created_at']
    
    def get_serializer_class(self):
        if self.action == 'create':
            return VettingRubricCreateSerializer
        return VettingRubricSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        
        # HR managers see their own rubrics
        if hasattr(user, 'role') and user.role == 'hr_manager':
            queryset = queryset.filter(created_by=user)
        
        # Filter by status from query params
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        return queryset.prefetch_related('criteria')
    
    def perform_create(self, serializer):
        """Set created_by to current user"""
        serializer.save(created_by=self.request.user)
    
    @action(detail=True, methods=['post'])
    def duplicate(self, request, pk=None):
        """
        Duplicate an existing rubric
        From: Rubrics PDF
        """
        original_rubric = self.get_object()
        
        # Create duplicate
        new_rubric = VettingRubric.objects.create(
            rubric_id=f"{original_rubric.rubric_id}-COPY-{self.request.user.id}",
            name=f"{original_rubric.name} (Copy)",
            description=original_rubric.description,
            rubric_type=original_rubric.rubric_type,
            created_by=request.user,
            department=original_rubric.department,
            position_level=original_rubric.position_level,
            status='draft',
            passing_score=original_rubric.passing_score,
            auto_approve_threshold=original_rubric.auto_approve_threshold,
            auto_reject_threshold=original_rubric.auto_reject_threshold
        )
        
        # Duplicate criteria
        for criterion in original_rubric.criteria.all():
            RubricCriteria.objects.create(
                rubric=new_rubric,
                name=criterion.name,
                description=criterion.description,
                criteria_type=criterion.criteria_type,
                weight=criterion.weight,
                minimum_score=criterion.minimum_score,
                is_mandatory=criterion.is_mandatory,
                scoring_rules=criterion.scoring_rules,
                order=criterion.order
            )
        
        serializer = self.get_serializer(new_rubric)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """
        Activate a draft rubric
        From: Rubrics PDF - validates before activation
        """
        rubric = self.get_object()
        
        # Validation checks
        if not rubric.criteria.exists():
            return Response(
                {'error': 'Cannot activate rubric without criteria'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check weights sum to 100
        total_weight = sum(c.weight for c in rubric.criteria.all())
        if total_weight != 100:
            return Response(
                {'error': f'Criteria weights must sum to 100 (currently {total_weight})'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        rubric.status = 'active'
        rubric.save()
        
        return Response({
            'message': 'Rubric activated successfully',
            'rubric': VettingRubricSerializer(rubric).data
        })
    
    @action(detail=True, methods=['post'])
    def archive(self, request, pk=None):
        """Archive a rubric"""
        rubric = self.get_object()
        rubric.status = 'archived'
        rubric.save()
        
        return Response({'message': 'Rubric archived successfully'})
    
    @action(detail=True, methods=['post'])
    def evaluate_application(self, request, pk=None):
        """
        Evaluate an application using this rubric
        From: Rubrics PDF - main evaluation endpoint
        """
        rubric = self.get_object()
        application_id = request.data.get('application_id')
        
        if not application_id:
            return Response(
                {'error': 'application_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            application = VettingCase.objects.get(case_id=application_id)
        except VettingCase.DoesNotExist:
            return Response(
                {'error': 'Application not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check if application has required data
        if not application.documents.filter(verification_status='verified').exists():
            return Response(
                {'error': 'Application has no verified documents'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Run evaluation
        engine = RubricEvaluationEngine(application, rubric)
        evaluation = engine.evaluate()
        
        serializer = RubricEvaluationSerializer(evaluation)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def templates(self, request):
        """
        Get pre-built rubric templates
        From: Rubrics PDF - templates section
        """
        from .templates import RUBRIC_TEMPLATES
        
        templates = []
        for key, template in RUBRIC_TEMPLATES.items():
            templates.append({
                'key': key,
                'name': template['name'],
                'rubric_type': template['rubric_type'],
                'description': f"Pre-built template for {template['name']}",
                'criteria_count': len(template['criteria'])
            })
        
        return Response(templates)
    
    @action(detail=False, methods=['post'])
    def create_from_template(self, request):
        """
        Create rubric from template
        From: Rubrics PDF
        """
        from .templates import create_rubric_from_template
        
        template_key = request.data.get('template_key')
        overrides = request.data.get('overrides', {})
        
        if not template_key:
            return Response(
                {'error': 'template_key is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            rubric = create_rubric_from_template(
                template_key,
                created_by=request.user,
                **overrides
            )
            serializer = self.get_serializer(rubric)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class RubricEvaluationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoints for viewing rubric evaluations
    From: Rubrics PDF
    """
    queryset = RubricEvaluation.objects.all()
    serializer_class = RubricEvaluationSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['application', 'rubric', 'passed']
    ordering = ['-evaluated_at']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by application_id from query params
        application_id = self.request.query_params.get('application_id')
        if application_id:
            queryset = queryset.filter(application__case_id=application_id)
        
        # Filter by rubric_id
        rubric_id = self.request.query_params.get('rubric_id')
        if rubric_id:
            queryset = queryset.filter(rubric_id=rubric_id)
        
        return queryset.select_related('application', 'rubric').prefetch_related('overrides')
    
    @action(detail=True, methods=['post'])
    def override_criterion(self, request, pk=None):
        """
        Override AI score for a specific criterion
        From: Rubrics PDF - HR override functionality
        """
        evaluation = self.get_object()
        
        # Validate input
        criterion_id = request.data.get('criterion_id')
        override_score = request.data.get('override_score')
        reason = request.data.get('reason')
        
        if not all([criterion_id, override_score is not None, reason]):
            return Response(
                {'error': 'criterion_id, override_score, and reason are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            override_score = float(override_score)
            if override_score < 0 or override_score > 100:
                raise ValueError
        except ValueError:
            return Response(
                {'error': 'override_score must be a number between 0 and 100'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get original score
        criteria_score_data = evaluation.criteria_scores.get(str(criterion_id))
        if not criteria_score_data:
            return Response(
                {'error': 'Criterion not found in evaluation'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        original_score = criteria_score_data.get('score', 0)
        
        # Create override
        override = CriteriaOverride.objects.create(
            evaluation=evaluation,
            criteria_id=criterion_id,
            original_score=original_score,
            override_score=override_score,
            reason=reason,
            overridden_by=request.user
        )
        
        # Recalculate overall score with override
        evaluation.criteria_scores[str(criterion_id)]['score'] = override_score
        evaluation.criteria_scores[str(criterion_id)]['overridden'] = True
        
        # Recalculate weighted score
        total_weighted_score = 0
        total_weight = 0
        
        for crit_id, score_data in evaluation.criteria_scores.items():
            weight = score_data['weight']
            score = score_data['score']
            total_weighted_score += score * (weight / 100)
            total_weight += weight
        
        evaluation.overall_score = (total_weighted_score / total_weight * 100) if total_weight > 0 else 0
        evaluation.passed = evaluation.overall_score >= evaluation.rubric.passing_score
        evaluation.save()
        
        # Log audit
        from audit.models import AuditLog
        AuditLog.objects.create(
            admin_user=request.user,
            action='override',
            entity_type='RubricEvaluation',
            entity_id=evaluation.id,
            changes={
                'criterion_id': criterion_id,
                'original_score': original_score,
                'override_score': override_score,
                'reason': reason,
                'new_overall_score': evaluation.overall_score
            }
        )
        
        return Response({
            'message': 'Criterion score overridden successfully',
            'override': CriteriaOverrideSerializer(override).data,
            'new_overall_score': evaluation.overall_score,
            'passed': evaluation.passed
        })
    
    @action(detail=True, methods=['get'])
    def breakdown(self, request, pk=None):
        """
        Get detailed breakdown of evaluation
        Includes visual data for frontend charts
        """
        evaluation = self.get_object()
        
        # Prepare chart data
        criteria_labels = []
        criteria_scores = []
        criteria_weights = []
        
        for crit_id, score_data in evaluation.criteria_scores.items():
            criteria_labels.append(score_data['name'])
            criteria_scores.append(score_data['score'])
            criteria_weights.append(score_data['weight'])
        
        return Response({
            'evaluation': RubricEvaluationSerializer(evaluation).data,
            'chart_data': {
                'labels': criteria_labels,
                'scores': criteria_scores,
                'weights': criteria_weights,
                'overall_score': evaluation.overall_score,
                'passing_score': evaluation.rubric.passing_score
            }
        })