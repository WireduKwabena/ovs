"""Read-only API endpoints for fraud and consistency results."""

from statistics import mean, median

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.permissions import IsGovernmentWorkflowOperator, scope_internal_queryset_to_tenant

from .models import ConsistencyCheckResult, FraudDetectionResult, SocialProfileCheckResult
from .serializers import (
    ConsistencyCheckResultSerializer,
    FraudDetectionResultSerializer,
    SocialProfileCheckResultSerializer,
)


class FraudDetectionResultViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoints for fraud detection results.

    list: GET /api/fraud/results/
    retrieve: GET /api/fraud/results/{id}/
    by_application: GET /api/fraud/results/by-application/?case_id=XXX
    """

    queryset = FraudDetectionResult.objects.select_related("application", "application__applicant").all()
    serializer_class = FraudDetectionResultSerializer
    permission_classes = [IsGovernmentWorkflowOperator]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return FraudDetectionResult.objects.none()

        queryset = super().get_queryset()
        queryset = scope_internal_queryset_to_tenant(queryset, request=self.request)

        case_id = self.request.query_params.get("case_id")
        if case_id:
            queryset = queryset.filter(application__case_id=case_id)

        risk_level = self.request.query_params.get("risk_level")
        if risk_level:
            queryset = queryset.filter(risk_level=risk_level.upper())

        return queryset.order_by("-detected_at")

    @action(detail=False, methods=["get"])
    def statistics(self, request):
        """Get fraud detection statistics."""
        queryset = self.get_queryset()
        total = queryset.count()
        fraud_detected = queryset.filter(is_fraud=True).count()

        return Response(
            {
                "total_scans": total,
                "fraud_detected": fraud_detected,
                "fraud_rate": (fraud_detected / total * 100) if total > 0 else 0.0,
                "risk_distribution": {
                    "HIGH": queryset.filter(risk_level="HIGH").count(),
                    "MEDIUM": queryset.filter(risk_level="MEDIUM").count(),
                    "LOW": queryset.filter(risk_level="LOW").count(),
                },
            }
        )


class ConsistencyCheckResultViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoints for consistency check results.

    list: GET /api/fraud/consistency/
    retrieve: GET /api/fraud/consistency/{id}/
    by_application: GET /api/fraud/consistency/by-application/?case_id=XXX
    """

    queryset = ConsistencyCheckResult.objects.select_related("application", "application__applicant").all()
    serializer_class = ConsistencyCheckResultSerializer
    permission_classes = [IsGovernmentWorkflowOperator]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return ConsistencyCheckResult.objects.none()

        queryset = super().get_queryset()
        queryset = scope_internal_queryset_to_tenant(queryset, request=self.request)

        case_id = self.request.query_params.get("case_id")
        if case_id:
            queryset = queryset.filter(application__case_id=case_id)

        is_consistent = self.request.query_params.get("consistent")
        if is_consistent is not None:
            normalized = is_consistent.strip().lower()
            if normalized not in {"true", "false"}:
                return ConsistencyCheckResult.objects.none()
            queryset = queryset.filter(overall_consistent=(normalized == "true"))

        return queryset.order_by("-checked_at")

    @action(detail=False, methods=["get"])
    def statistics(self, request):
        """Get consistency check statistics."""
        queryset = self.get_queryset()
        total = queryset.count()
        consistent = queryset.filter(overall_consistent=True).count()
        scores = list(queryset.values_list("overall_score", flat=True))

        return Response(
            {
                "total_checks": total,
                "consistent_count": consistent,
                "consistency_rate": (consistent / total * 100) if total > 0 else 0.0,
                "average_score": mean(scores) if scores else 0.0,
                "median_score": median(scores) if scores else 0.0,
            }
        )

    @action(detail=False, methods=["get"])
    def history(self, request):
        """
        Optional endpoint for recent consistency checks.
        GET /api/fraud/consistency/history/?limit=20
        """
        limit_raw = request.query_params.get("limit", "20")
        try:
            limit = int(limit_raw)
        except (TypeError, ValueError):
            return Response(
                {"error": "limit must be an integer"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        limit = max(1, min(limit, 200))

        serializer = self.get_serializer(self.get_queryset()[:limit], many=True)
        return Response({"history": serializer.data, "limit": limit})


class SocialProfileCheckResultViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoints for social profile check results.

    list: GET /api/fraud/social-profiles/
    retrieve: GET /api/fraud/social-profiles/{id}/
    """

    queryset = SocialProfileCheckResult.objects.select_related("application", "application__applicant").all()
    serializer_class = SocialProfileCheckResultSerializer
    permission_classes = [IsGovernmentWorkflowOperator]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return SocialProfileCheckResult.objects.none()

        queryset = super().get_queryset()
        queryset = scope_internal_queryset_to_tenant(queryset, request=self.request)

        case_id = self.request.query_params.get("case_id")
        if case_id:
            queryset = queryset.filter(application__case_id=case_id)

        risk_level = self.request.query_params.get("risk_level")
        if risk_level:
            queryset = queryset.filter(risk_level=risk_level.upper())

        return queryset.order_by("-checked_at")

    @action(detail=False, methods=["get"])
    def statistics(self, request):
        """Get social profile check statistics."""
        queryset = self.get_queryset()
        total = queryset.count()
        manual = queryset.filter(recommendation="MANUAL_REVIEW").count()
        avg_score = mean(queryset.values_list("overall_score", flat=True)) if total else 0.0

        return Response(
            {
                "total_checks": total,
                "manual_review_count": manual,
                "manual_review_rate": (manual / total * 100) if total > 0 else 0.0,
                "average_score": avg_score,
                "risk_distribution": {
                    "HIGH": queryset.filter(risk_level="HIGH").count(),
                    "MEDIUM": queryset.filter(risk_level="MEDIUM").count(),
                    "LOW": queryset.filter(risk_level="LOW").count(),
                },
            }
        )
