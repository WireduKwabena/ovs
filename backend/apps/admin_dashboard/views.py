# backend/apps/admin_dashboard/views.py

from datetime import timedelta

from django.contrib.auth.models import Group
from django.shortcuts import get_object_or_404
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Q
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.applications.models import Document, VettingCase
from apps.auth_actions import IsAdminUser
from apps.authentication.models import User
from apps.core.authz import GOVERNMENT_ROLE_GROUPS
from apps.fraud.models import FraudDetectionResult
from apps.rubrics.models import RubricEvaluation

from .serializers import (
    AdminAnalyticsResponseSerializer,
    AdminCasesResponseSerializer,
    AdminDashboardResponseSerializer,
    AdminManagedUserSerializer,
    AdminUserUpdateRequestSerializer,
    AdminUsersResponseSerializer,
    VettingCaseAdminSerializer,
)

try:
    from drf_spectacular.utils import extend_schema
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    def extend_schema(*args, **kwargs):  # type: ignore[override]
        def decorator(func):
            return func

        return decorator


def _parse_positive_int(value, *, default: int, minimum: int = 1, maximum: int | None = None) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    if parsed < minimum:
        return default
    if maximum is not None:
        parsed = min(maximum, parsed)
    return parsed


ADMIN_CASE_ORDERING_FIELDS = {
    "case_id": "case_id",
    "application_type": "position_applied",
    "status": "status",
    "priority": "priority",
    "consistency_score": "consistency_score",
    "fraud_risk_score": "fraud_risk_score",
    "created_at": "created_at",
    "updated_at": "updated_at",
}


def _parse_admin_case_ordering(value: str | None, *, default: str = "-created_at") -> str:
    raw = (value or "").strip()
    if not raw:
        return default

    descending = raw.startswith("-")
    key = raw[1:] if descending else raw
    mapped = ADMIN_CASE_ORDERING_FIELDS.get(key)
    if not mapped:
        return default

    return f"-{mapped}" if descending else mapped


def _parse_bool(value: str | None, *, default: bool | None = None) -> bool | None:
    if value is None:
        return default
    lowered = str(value).strip().lower()
    if lowered in {"1", "true", "yes", "y"}:
        return True
    if lowered in {"0", "false", "no", "n"}:
        return False
    return default


ADMIN_USER_ORDERING_FIELDS = {
    "email": "email",
    "user_type": "user_type",
    "is_active": "is_active",
    "is_staff": "is_staff",
    "is_superuser": "is_superuser",
    "created_at": "created_at",
    "updated_at": "updated_at",
    "last_login": "last_login",
}


def _parse_admin_user_ordering(value: str | None, *, default: str = "-created_at") -> str:
    raw = (value or "").strip()
    if not raw:
        return default

    descending = raw.startswith("-")
    key = raw[1:] if descending else raw
    mapped = ADMIN_USER_ORDERING_FIELDS.get(key)
    if not mapped:
        return default

    return f"-{mapped}" if descending else mapped


@extend_schema(responses={200: AdminDashboardResponseSerializer})
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
    recent_applications = VettingCase.objects.select_related(
        "applicant", "rubric_evaluation"
    ).order_by("-created_at")[:10]
    
    recent_apps_data = []
    for app in recent_applications:
        rubric_eval = getattr(app, "rubric_evaluation", None)
        recent_apps_data.append({
            'id': app.id,
            'case_id': app.case_id,
            'applicant_name': app.applicant.get_full_name(),
            'application_type': app.position_applied,
            'status': app.status,
            'created_at': app.created_at,
            'rubric_score': rubric_eval.total_weighted_score if rubric_eval else None
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


@extend_schema(responses={200: AdminAnalyticsResponseSerializer})
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
        avg_score=Avg("total_weighted_score"),
        pass_count=Count("id", filter=Q(passes_threshold=True)),
        fail_count=Count("id", filter=Q(passes_threshold=False)),
    )
    
    # Monthly application trend
    months = _parse_positive_int(request.query_params.get('months'), default=6, minimum=1, maximum=24)
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


@extend_schema(responses={200: AdminCasesResponseSerializer})
@api_view(['GET'])
@permission_classes([IsAdminUser])
def admin_cases(request):
    """
    Get all cases for admin review
    GET /api/admin/cases/
    Supports filtering: ?status=pending&application_type=employment
    """
    cases = VettingCase.objects.select_related("applicant", "assigned_to").all()
    
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
    
    # Ordering + pagination
    ordering = _parse_admin_case_ordering(request.query_params.get('ordering'), default='-created_at')
    page = _parse_positive_int(request.query_params.get('page'), default=1, minimum=1)
    page_size = _parse_positive_int(request.query_params.get('page_size'), default=20, minimum=1, maximum=200)

    paginator = Paginator(cases.order_by(ordering), page_size)
    page_obj = paginator.get_page(page)

    serializer = VettingCaseAdminSerializer(page_obj, many=True)

    return Response({
        'results': serializer.data,
        'count': paginator.count,
        'page': page,
        'page_size': page_size,
        'total_pages': paginator.num_pages,
        'ordering': ordering,
    })


@extend_schema(responses={200: AdminUsersResponseSerializer})
@api_view(['GET'])
@permission_classes([IsAdminUser])
def admin_users(request):
    """
    List users for admin management.
    GET /api/admin/users/
    Supports filtering: ?q=email_or_name&user_type=admin|hr_manager|applicant&is_active=true|false
    """
    users = User.objects.all()

    query = (request.query_params.get('q') or "").strip()
    if query:
        users = users.filter(
            Q(email__icontains=query)
            | Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
        )

    user_type_filter = (request.query_params.get('user_type') or "").strip()
    if user_type_filter in {choice[0] for choice in User.USER_TYPE_CHOICES}:
        users = users.filter(user_type=user_type_filter)

    is_active_filter = _parse_bool(request.query_params.get('is_active'), default=None)
    if is_active_filter is not None:
        users = users.filter(is_active=is_active_filter)

    ordering = _parse_admin_user_ordering(
        request.query_params.get('ordering'),
        default='-created_at',
    )
    page = _parse_positive_int(request.query_params.get('page'), default=1, minimum=1)
    page_size = _parse_positive_int(
        request.query_params.get('page_size'),
        default=20,
        minimum=1,
        maximum=200,
    )

    paginator = Paginator(users.order_by(ordering), page_size)
    page_obj = paginator.get_page(page)
    serializer = AdminManagedUserSerializer(page_obj, many=True)

    return Response(
        {
            'results': serializer.data,
            'count': paginator.count,
            'page': page,
            'page_size': page_size,
            'total_pages': paginator.num_pages,
            'ordering': ordering,
        }
    )


@extend_schema(
    request=AdminUserUpdateRequestSerializer,
    responses={
        200: AdminManagedUserSerializer,
    },
)
@api_view(['PATCH'])
@permission_classes([IsAdminUser])
def admin_user_update(request, user_id):
    """
    Partially update an admin-managed user.
    PATCH /api/admin/users/<uuid:user_id>/
    """
    managed_user = get_object_or_404(User, pk=user_id)
    serializer = AdminUserUpdateRequestSerializer(data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)

    updates = serializer.validated_data.copy()
    reset_two_factor = bool(updates.pop("reset_two_factor", False))
    group_roles = updates.pop("group_roles", None)

    if "is_active" in updates:
        next_active = bool(updates["is_active"])
        if request.user.pk == managed_user.pk and not next_active:
            return Response(
                {"detail": "You cannot deactivate your own account."},
                status=status.HTTP_400_BAD_REQUEST,
            )

    if "user_type" in updates:
        next_user_type = str(updates["user_type"])
        if next_user_type == "admin":
            updates["is_staff"] = True

    if "is_staff" in updates and not updates["is_staff"] and managed_user.is_superuser:
        return Response(
            {"detail": "Cannot remove staff access from a superuser."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if group_roles is not None and group_roles and managed_user.user_type == "applicant":
        return Response(
            {"detail": "Internal operational roles can only be assigned to internal users."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    for field, value in updates.items():
        setattr(managed_user, field, value)

    update_fields = list(updates.keys())

    if reset_two_factor:
        managed_user.is_two_factor_enabled = False
        managed_user.two_factor_secret = None
        managed_user.two_factor_backup_codes = []
        update_fields.extend([
            "is_two_factor_enabled",
            "two_factor_secret",
            "two_factor_backup_codes",
        ])

    if update_fields:
        managed_user.save(update_fields=[*set(update_fields), "updated_at"])

    if group_roles is not None:
        requested_roles = set(group_roles)
        existing_group_names = set(managed_user.groups.values_list("name", flat=True))
        preserved_groups = existing_group_names.difference(GOVERNMENT_ROLE_GROUPS)
        target_group_names = preserved_groups.union(requested_roles)

        for role_name in requested_roles:
            Group.objects.get_or_create(name=role_name)

        target_groups = Group.objects.filter(name__in=target_group_names)
        managed_user.groups.set(target_groups)

    return Response(AdminManagedUserSerializer(managed_user).data)


