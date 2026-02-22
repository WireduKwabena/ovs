from django.db import transaction
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.applications.models import VettingCase

from .engine import RubricEvaluationEngine
from .models import CriteriaOverride, RubricCriteria, RubricEvaluation, VettingRubric
from .serializers import (
    CriteriaOverrideSerializer,
    RubricCriteriaSerializer,
    RubricEvaluationSerializer,
    VettingRubricSerializer,
)
from .tasks import evaluate_case_with_rubric


def _parse_boolean(value) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "y", "on"}:
            return True
        if normalized in {"0", "false", "no", "n", "off", ""}:
            return False
    return bool(value)


class VettingRubricViewSet(viewsets.ModelViewSet):
    serializer_class = VettingRubricSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = VettingRubric.objects.prefetch_related("criteria").all()
        rubric_type = self.request.query_params.get("rubric_type")
        is_active = self.request.query_params.get("is_active")
        if rubric_type:
            queryset = queryset.filter(rubric_type=rubric_type)
        if is_active in {"true", "false"}:
            queryset = queryset.filter(is_active=(is_active == "true"))
        return queryset.order_by("name")

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=["post"], url_path="criteria")
    def add_criteria(self, request, pk=None):
        rubric = self.get_object()
        payload = request.data.copy()
        payload["rubric"] = rubric.id
        serializer = RubricCriteriaSerializer(data=payload)
        serializer.is_valid(raise_exception=True)
        serializer.save(rubric=rubric)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="evaluate-case")
    def evaluate_case(self, request, pk=None):
        rubric = self.get_object()
        case_id = request.data.get("case_id")
        run_async = _parse_boolean(request.data.get("async", False))

        if not case_id:
            return Response({"error": "case_id is required"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            case = VettingCase.objects.get(id=case_id)
        except VettingCase.DoesNotExist:
            return Response({"error": "Case not found"}, status=status.HTTP_404_NOT_FOUND)

        if run_async:
            evaluate_case_with_rubric.delay(case.id, rubric.id, request.user.id)
            return Response({"message": "Evaluation queued."}, status=status.HTTP_202_ACCEPTED)

        evaluation = RubricEvaluationEngine(case=case, rubric=rubric).evaluate(evaluated_by=request.user)
        data = RubricEvaluationSerializer(evaluation, context=self.get_serializer_context()).data
        return Response(data, status=status.HTTP_200_OK)


class RubricCriteriaViewSet(viewsets.ModelViewSet):
    serializer_class = RubricCriteriaSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = RubricCriteria.objects.select_related("rubric").all()
        rubric_id = self.request.query_params.get("rubric")
        if rubric_id:
            queryset = queryset.filter(rubric_id=rubric_id)
        return queryset.order_by("rubric_id", "display_order", "id")


class RubricEvaluationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = RubricEvaluationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = RubricEvaluation.objects.select_related("case", "rubric", "evaluated_by").prefetch_related("overrides")
        case_id = self.request.query_params.get("case")
        rubric_id = self.request.query_params.get("rubric")
        if case_id:
            queryset = queryset.filter(case_id=case_id)
        if rubric_id:
            queryset = queryset.filter(rubric_id=rubric_id)
        return queryset.order_by("-created_at")

    @action(detail=True, methods=["post"], url_path="rerun")
    def rerun(self, request, pk=None):
        evaluation = self.get_object()
        updated = RubricEvaluationEngine(case=evaluation.case, rubric=evaluation.rubric).evaluate(evaluated_by=request.user)
        return Response(self.get_serializer(updated).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="override-criterion")
    def override_criterion(self, request, pk=None):
        evaluation = self.get_object()
        criterion_id = request.data.get("criterion_id")
        overridden_score = request.data.get("overridden_score")
        justification = request.data.get("justification")

        if not criterion_id or overridden_score is None or not justification:
            return Response(
                {"error": "criterion_id, overridden_score and justification are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            criterion = RubricCriteria.objects.get(id=criterion_id, rubric=evaluation.rubric)
        except RubricCriteria.DoesNotExist:
            return Response({"error": "Criterion not found for this rubric"}, status=status.HTTP_404_NOT_FOUND)

        try:
            overridden_score = float(overridden_score)
        except (TypeError, ValueError):
            return Response({"error": "overridden_score must be numeric"}, status=status.HTTP_400_BAD_REQUEST)
        if overridden_score < 0 or overridden_score > 100:
            return Response({"error": "overridden_score must be between 0 and 100"}, status=status.HTTP_400_BAD_REQUEST)

        original = None
        if isinstance(evaluation.criterion_scores, dict):
            original = evaluation.criterion_scores.get(str(criterion.id), {}).get("score")
        if original is None:
            original = 0.0

        with transaction.atomic():
            override = CriteriaOverride.objects.create(
                evaluation=evaluation,
                criteria=criterion,
                original_score=original,
                overridden_score=overridden_score,
                justification=justification,
                overridden_by=request.user,
            )
            if isinstance(evaluation.criterion_scores, dict) and str(criterion.id) in evaluation.criterion_scores:
                item = evaluation.criterion_scores[str(criterion.id)]
                item["original_score"] = original
                item["score"] = overridden_score
                item["overridden"] = True
                evaluation.criterion_scores[str(criterion.id)] = item
            reasons = list(evaluation.review_reasons or [])
            reasons.append(f"Manual override applied to criterion '{criterion.name}'.")
            evaluation.review_reasons = reasons
            evaluation.requires_manual_review = True
            evaluation.status = "requires_review"
            evaluation.save(update_fields=["criterion_scores", "review_reasons", "requires_manual_review", "status", "updated_at"])

        return Response(
            {
                "message": "Override recorded; evaluation marked for manual review.",
                "override": CriteriaOverrideSerializer(override).data,
            },
            status=status.HTTP_201_CREATED,
        )
