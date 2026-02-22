"""Read-only API endpoints for model performance metrics."""

from django.db.models import OuterRef, Subquery
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.auth_actions import IsAdminUser

from .models import MLModelMetrics
from .serializers import MLModelMetricsSerializer


class MLModelMetricsViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoints for ML model metrics.

    list: GET /api/ml-monitoring/
    retrieve: GET /api/ml-monitoring/{id}/
    latest: GET /api/ml-monitoring/latest/
    performance summary: GET /api/ml-monitoring/performance-summary/
    history: GET /api/ml-monitoring/history/?model_name=authenticity_detector

    Legacy alias routes are also available under /api/ml-monitoring/metrics/.
    """

    queryset = MLModelMetrics.objects.all()
    serializer_class = MLModelMetricsSerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return MLModelMetrics.objects.none()

        queryset = super().get_queryset()
        model_name = self.request.query_params.get("model_name")
        if model_name:
            queryset = queryset.filter(model_name=model_name)
        return queryset.order_by("-evaluated_at", "-trained_at", "-model_version")

    @action(detail=False, methods=["get"])
    def latest(self, request):
        """Get latest metrics for each model."""
        latest_sq = MLModelMetrics.objects.filter(model_name=OuterRef("model_name")).order_by(
            "-evaluated_at",
            "-trained_at",
            "-model_version",
        )
        latest_metrics = MLModelMetrics.objects.filter(pk=Subquery(latest_sq.values("pk")[:1])).order_by(
            "model_name"
        )
        serializer = self.get_serializer(latest_metrics, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"], url_path="performance-summary", url_name="performance-summary")
    def performance_summary(self, request):
        """Get performance summary for all models."""
        latest_sq = MLModelMetrics.objects.filter(model_name=OuterRef("model_name")).order_by(
            "-evaluated_at",
            "-trained_at",
            "-model_version",
        )
        latest_metrics = MLModelMetrics.objects.filter(pk=Subquery(latest_sq.values("pk")[:1]))

        models = {}
        for metric in latest_metrics:
            models[metric.model_name] = {
                "version": metric.model_version,
                "accuracy": metric.accuracy,
                "precision": metric.precision,
                "recall": metric.recall,
                "f1_score": metric.f1_score,
                "last_evaluated": metric.evaluated_at,
            }

        return Response({"models": models, "total_models": len(models)})

    @action(detail=False, methods=["get"])
    def history(self, request):
        """
        Get performance history for a specific model.
        GET /api/ml-monitoring/history/?model_name=authenticity_detector&limit=10
        """
        model_name = request.query_params.get("model_name")
        if not model_name:
            return Response({"error": "model_name parameter is required"}, status=status.HTTP_400_BAD_REQUEST)

        limit_raw = request.query_params.get("limit", "10")
        try:
            limit = int(limit_raw)
        except (TypeError, ValueError):
            return Response({"error": "limit must be an integer"}, status=status.HTTP_400_BAD_REQUEST)

        limit = max(1, min(limit, 200))
        metrics = self.get_queryset().filter(model_name=model_name)[:limit]
        serializer = self.get_serializer(metrics, many=True)
        return Response({"model_name": model_name, "history": serializer.data, "limit": limit})
