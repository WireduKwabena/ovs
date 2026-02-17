# backend/apps/fraud/views.py

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import FraudDetectionResult, ConsistencyCheckResult
from .serializers import (
    FraudDetectionResultSerializer,
    ConsistencyCheckResultSerializer
)

class FraudDetectionResultViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoints for fraud detection results
    
    list: GET /api/fraud/results/
    retrieve: GET /api/fraud/results/{id}/
    by_application: GET /api/fraud/results/by-application/?case_id=XXX
    """
    queryset = FraudDetectionResult.objects.all()
    serializer_class = FraudDetectionResultSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by application if provided
        case_id = self.request.query_params.get('case_id')
        if case_id:
            queryset = queryset.filter(application__case_id=case_id)
        
        # Filter by risk level
        risk_level = self.request.query_params.get('risk_level')
        if risk_level:
            queryset = queryset.filter(risk_level=risk_level.upper())
        
        return queryset.select_related('application').order_by('-detected_at')
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """
        Get fraud detection statistics
        GET /api/fraud/results/statistics/
        """
        queryset = self.get_queryset()
        
        total = queryset.count()
        fraud_detected = queryset.filter(is_fraud=True).count()
        
        risk_distribution = {
            'HIGH': queryset.filter(risk_level='HIGH').count(),
            'MEDIUM': queryset.filter(risk_level='MEDIUM').count(),
            'LOW': queryset.filter(risk_level='LOW').count(),
        }
        
        return Response({
            'total_scans': total,
            'fraud_detected': fraud_detected,
            'fraud_rate': (fraud_detected / total * 100) if total > 0 else 0,
            'risk_distribution': risk_distribution
        })


class ConsistencyCheckResultViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoints for consistency check results
    
    list: GET /api/fraud/consistency/
    retrieve: GET /api/fraud/consistency/{id}/
    by_application: GET /api/fraud/consistency/by-application/?case_id=XXX
    """
    queryset = ConsistencyCheckResult.objects.all()
    serializer_class = ConsistencyCheckResultSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by application
        case_id = self.request.query_params.get('case_id')
        if case_id:
            queryset = queryset.filter(application__case_id=case_id)
        
        # Filter by consistency
        is_consistent = self.request.query_params.get('consistent')
        if is_consistent is not None:
            queryset = queryset.filter(
                overall_consistent=(is_consistent.lower() == 'true')
            )
        
        return queryset.select_related('application').order_by('-checked_at')
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """
        Get consistency check statistics
        GET /api/fraud/consistency/statistics/
        """
        queryset = self.get_queryset()
        
        total = queryset.count()
        consistent = queryset.filter(overall_consistent=True).count()
        
        import numpy as np
        scores = list(queryset.values_list('overall_score', flat=True))
        
        return Response({
            'total_checks': total,
            'consistent_count': consistent,
            'consistency_rate': (consistent / total * 100) if total > 0 else 0,
            'average_score': np.mean(scores) if scores else 0,
            'median_score': np.median(scores) if scores else 0
        })