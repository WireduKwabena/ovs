# backend/apps/admin_dashboard/views.py

from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from apps.auth_actions import IsAdminUser
from django.db.models import Count, Avg, Q, Prefetch
from django.utils import timezone
from datetime import timedelta
from apps.applications import VettingCase, Document
from apps.rubrics import RubricEvaluation
from apps.fraud.models import FraudDetectionResult
from .serializers import VettingCaseAdminSerializer

@api_view(['GET'])
@permission_classes([IsAdminUser])
def admin_dashboard(request):
    """
    Main admin dashboard with statistics
    GET /api/admin/dashboard/
    """
    # Application statistics
    status_counts = VettingCase.objects.aggregate(
        total=Count('id'),
        pending=Count('id', filter=Q(status='pending')),
        under_review=Count('id', filter=Q(status='under_review')),
        approved=Count('id', filter=Q(status='approved')),
        rejected=Count('id', filter=Q(status='rejected')),
    )

    # Recent applications
    recent_applications = VettingCase.objects.select_related('applicant').prefetch_related(
        Prefetch('rubric_evaluations', queryset=RubricEvaluation.objects.order_by('-created_at'))
    ).order_by('-created_at')[:10]
    
    recent_apps_data = []
    for app in recent_applications:
        rubric_eval = app.rubric_evaluations.first()
        recent_apps_data.append({
            'id': app.id,
            'case_id': app.case_id,
            'applicant_name': app.applicant.get_full_name(),
            'application_type': app.position_applied,
            'status': app.status,
            'created_at': app.created_at,
            'rubric_score': rubric_eval.overall_score if rubric_eval else None
        })
    
    # Documents statistics
    total_documents = Document.objects.count()
    verified_documents = Document.objects.filter(status='verified').count()
    
    # Fraud statistics
    fraud_results = FraudDetectionResult.objects.all()
    total_fraud_scans = fraud_results.count()
    high_risk = fraud_results.filter(risk_level='HIGH').count()
    
    # Monthly trends
    thirty_days_ago = timezone.now() - timedelta(days=30)
    monthly_applications = VettingCase.objects.filter(
        created_at__gte=thirty_days_ago
    ).count()
    
    # Average processing time (simplified)
    avg_consistency_score = VettingCase.objects.filter(
        consistency_score__isnull=False
    ).aggregate(Avg('consistency_score'))['consistency_score__avg'] or 0
    
    return Response({
        'total_applications': status_counts['total'],
        'pending': status_counts['pending'],
        'under_review': status_counts['under_review'],
        'approved': status_counts['approved'],
        'rejected': status_counts['rejected'],
        'recent_applications': recent_apps_data,
        'documents': {
            'total': total_documents,
            'verified': verified_documents,
            'verification_rate': (verified_documents / total_documents * 100) if total_documents > 0 else 0
        },
        'fraud_detection': {
            'total_scans': total_fraud_scans,
            'high_risk_count': high_risk,
            'high_risk_rate': (high_risk / total_fraud_scans * 100) if total_fraud_scans > 0 else 0
        },
        'trends': {
            'monthly_applications': monthly_applications,
            'avg_consistency_score': round(avg_consistency_score, 2)
        }
    })


@api_view(['GET'])
@permission_classes([IsAdminUser])
def admin_analytics(request):
    """
    Detailed analytics for admin
    GET /api/admin/analytics/
    """
    # Application status distribution
    status_distribution = VettingCase.objects.values('status').annotate(
        count=Count('id')
    )
    
    # Application type distribution
    type_distribution = VettingCase.objects.values('position_applied').annotate(
        count=Count('id')
    )
    
    # Priority distribution
    priority_distribution = VettingCase.objects.values('priority').annotate(
        count=Count('id')
    )
    
    # Rubric evaluation statistics
    rubric_stats = RubricEvaluation.objects.aggregate(
        avg_score=Avg('overall_score'),
        pass_count=Count('id', filter=Q(passed=True)),
        fail_count=Count('id', filter=Q(passed=False))
    )
    
    # Monthly application trend
    months = int(request.query_params.get('months', 6))
    monthly_trend = []
    for i in range(months):
        month_start = timezone.now() - timedelta(days=30 * (i + 1))
        month_end = timezone.now() - timedelta(days=30 * i)
        
        count = VettingCase.objects.filter(
            created_at__gte=month_start,
            created_at__lt=month_end
        ).count()
        
        monthly_trend.append({
            'month': month_start.strftime('%B %Y'),
            'count': count
        })
    
    monthly_trend.reverse()
    
    return Response({
        'status_distribution': list(status_distribution),
        'type_distribution': list(type_distribution),
        'priority_distribution': list(priority_distribution),
        'rubric_statistics': rubric_stats,
        'monthly_trend': monthly_trend,
        'total_applications': VettingCase.objects.count(),
        'total_users': VettingCase.objects.values('applicant').distinct().count()
    })


@api_view(['GET'])
@permission_classes([IsAdminUser])
def admin_cases(request):
    """
    Get all cases for admin review
    GET /api/admin/cases/
    Supports filtering: ?status=pending&application_type=employment
    """
    cases = VettingCase.objects.select_related('applicant', 'admin').all()
    
    # Apply filters
    status_filter = request.query_params.get('status')
    if status_filter:
        cases = cases.filter(status=status_filter)
    
    app_type_filter = request.query_params.get('application_type')
    if app_type_filter:
        cases = cases.filter(position_applied__icontains=app_type_filter)
    
    priority_filter = request.query_params.get('priority')
    if priority_filter:
        cases = cases.filter(priority=priority_filter)
    
    # Pagination
    from django.core.paginator import Paginator
    page = int(request.query_params.get('page', 1))
    page_size = int(request.query_params.get('page_size', 20))
    
    paginator = Paginator(cases.order_by('-created_at'), page_size)
    page_obj = paginator.get_page(page)
    
    serializer = VettingCaseAdminSerializer(page_obj, many=True)
    
    return Response({
        'results': serializer.data,
        'count': paginator.count,
        'page': page,
        'page_size': page_size,
        'total_pages': paginator.num_pages
    })
