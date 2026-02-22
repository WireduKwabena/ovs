# backend/apps/ml_monitoring/views.py

from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from apps.auth_actions import IsAdminUser
from .models import MLModelMetrics
from .serializers import MLModelMetricsSerializer
from django.db.models import Subquery, OuterRef

class MLModelMetricsViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoints for ML model metrics
    
    list: GET /api/ml-monitoring/metrics/
    retrieve: GET /api/ml-monitoring/metrics/{id}/
    latest: GET /api/ml-monitoring/metrics/latest/
    by_model: GET /api/ml-monitoring/metrics/by-model/?model_name=authenticity_detector
    """
    queryset = MLModelMetrics.objects.all()
    serializer_class = MLModelMetricsSerializer
    permission_classes = [IsAdminUser]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by model name
        model_name = self.request.query_params.get('model_name')
        if model_name:
            queryset = queryset.filter(model_name=model_name)
        
        return queryset.order_by('-evaluated_at')
    
    @action(detail=False, methods=['get'])
    def latest(self, request):
        """
        Get latest metrics for each model
        GET /api/ml-monitoring/metrics/latest/
        """
        latest_sq = MLModelMetrics.objects.filter(
            model_name=OuterRef('model_name')
        ).order_by('-evaluated_at')
        latest_metrics = MLModelMetrics.objects.filter(
            pk=Subquery(latest_sq.values('pk')[:1])
        )
        serializer = self.get_serializer(latest_metrics, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def performance_summary(self, request):
        """
        Get performance summary for all models
        GET /api/ml-monitoring/metrics/performance-summary/
        """
        models = {}
        model_names = self.get_queryset().values_list('model_name', flat=True).distinct()
        
        for model_name in model_names:
            latest = self.get_queryset().filter(model_name=model_name).first()
            
            if latest:
                models[model_name] = {
                    'version': latest.model_version,
                    'accuracy': latest.accuracy,
                    'precision': latest.precision,
                    'recall': latest.recall,
                    'f1_score': latest.f1_score,
                    'last_evaluated': latest.evaluated_at
                }
        
        return Response({
            'models': models,
            'total_models': len(models)
        })
    
    @action(detail=False, methods=['get'])
    def history(self, request):
        """
        Get performance history for a specific model
        GET /api/ml-monitoring/metrics/history/?model_name=authenticity_detector&limit=10
        """
        model_name = request.query_params.get('model_name')
        limit = int(request.query_params.get('limit', 10))
        
        if not model_name:
            return Response(
                {'error': 'model_name parameter is required'},
                status=400
            )
        
        metrics = self.get_queryset().filter(model_name=model_name)[:limit]
        serializer = self.get_serializer(metrics, many=True)
        
        return Response({
            'model_name': model_name,
            'history': serializer.data
        })
