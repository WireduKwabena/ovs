from django.db import transaction
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from apps.applications.models import VettingCase
from apps.users.permissions import RequiresRecentAuth
from apps.billing.quotas import (
    VETTING_OPERATION_RUBRIC_EVALUATION,
    enforce_vetting_operation_quota,
    resolve_case_organization_id,
)
from apps.core.policies.appointment_policy import can_view_internal_record
from apps.core.policies.registry_policy import can_manage_registry, is_platform_admin_actor

from .decision_engine import VettingDecisionEngine
from .engine import RubricEvaluationEngine
from .models import CriteriaOverride, RubricCriteria, RubricEvaluation, VettingRubric
from .permissions import IsInternalRubricOperator
from .serializers import (
    CriteriaOverrideSerializer,
    RubricCriteriaSerializer,
    RubricEvaluationSerializer,
    VettingDecisionOverrideRequestSerializer,
    VettingDecisionRecommendationSerializer,
    VettingRubricSerializer,
)
from .tasks import evaluate_case_with_rubric
from .templates import RUBRIC_TEMPLATES, create_rubric_from_template


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


def _parse_ai_signals(payload):
    if payload is None:
        return None, None
    if not isinstance(payload, dict):
        return None, Response({"error": "ai_signals must be an object"}, status=status.HTTP_400_BAD_REQUEST)
    return payload, None


class VettingRubricViewSet(viewsets.ModelViewSet):
    serializer_class = VettingRubricSerializer
    permission_classes = [IsInternalRubricOperator]

    def _require_registry_manage(self, *, detail: str):
        user = self.request.user
        if is_platform_admin_actor(user):
            return
        if can_manage_registry(user, allow_membershipless_fallback=False):
            return
        raise PermissionDenied(detail)

    def get_queryset(self):
        user = getattr(self.request, "user", None)
        if user is None or not getattr(user, "is_authenticated", False):
            return VettingRubric.objects.none()
        queryset = VettingRubric.objects.prefetch_related("criteria").all()
        rubric_type = self.request.query_params.get("rubric_type")
        is_active = self.request.query_params.get("is_active")
        if rubric_type:
            queryset = queryset.filter(rubric_type=rubric_type)
        if is_active in {"true", "false"}:
            queryset = queryset.filter(is_active=(is_active == "true"))
        return queryset.order_by("name")

    def perform_create(self, serializer):
        self._require_registry_manage(detail="You do not have permission to create rubrics.")
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        self._require_registry_manage(detail="You do not have permission to update rubrics.")
        serializer.save()

    def perform_destroy(self, instance):
        self._require_registry_manage(detail="You do not have permission to delete rubrics.")
        super().perform_destroy(instance)

    @action(detail=True, methods=["post"], url_path="activate")
    def activate(self, request, pk=None):
        rubric = self.get_object()
        self._require_registry_manage(detail="You do not have permission to activate rubrics.")
        rubric.is_active = True
        rubric.save(update_fields=["is_active", "updated_at"])
        data = self.get_serializer(rubric).data
        return Response({"message": "Rubric activated successfully.", "rubric": data}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="duplicate")
    def duplicate(self, request, pk=None):
        source = self.get_object()
        self._require_registry_manage(detail="You do not have permission to duplicate rubrics.")
        copy_name = f"{source.name} (Copy)"
        copy_index = 2
        while VettingRubric.objects.filter(name=copy_name).exists():
            copy_name = f"{source.name} (Copy {copy_index})"
            copy_index += 1

        with transaction.atomic():
            cloned = VettingRubric.objects.create(
                name=copy_name,
                description=source.description,
                rubric_type=source.rubric_type,
                document_authenticity_weight=source.document_authenticity_weight,
                consistency_weight=source.consistency_weight,
                fraud_detection_weight=source.fraud_detection_weight,
                interview_weight=source.interview_weight,
                manual_review_weight=source.manual_review_weight,
                passing_score=source.passing_score,
                auto_approve_threshold=source.auto_approve_threshold,
                auto_reject_threshold=source.auto_reject_threshold,
                minimum_document_score=source.minimum_document_score,
                maximum_fraud_score=source.maximum_fraud_score,
                require_interview=source.require_interview,
                critical_flags_auto_fail=source.critical_flags_auto_fail,
                max_unresolved_flags=source.max_unresolved_flags,
                is_active=False,
                is_default=False,
                created_by=request.user,
            )

            for criterion in source.criteria.all().order_by("display_order", "id"):
                RubricCriteria.objects.create(
                    rubric=cloned,
                    name=criterion.name,
                    description=criterion.description,
                    criteria_type=criterion.criteria_type,
                    scoring_method=criterion.scoring_method,
                    weight=criterion.weight,
                    minimum_score=criterion.minimum_score,
                    is_mandatory=criterion.is_mandatory,
                    evaluation_guidelines=criterion.evaluation_guidelines,
                    display_order=criterion.display_order,
                )

        return Response(self.get_serializer(cloned).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["get"], url_path="templates")
    def templates(self, request):
        payload = []
        for key, template in RUBRIC_TEMPLATES.items():
            payload.append(
                {
                    "template_key": key,
                    "name": template.get("name"),
                    "description": template.get("description", ""),
                    "rubric_type": template.get("rubric_type", "general"),
                    "criteria_count": len(template.get("criteria", [])),
                }
            )
        return Response(payload, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"], url_path="create_from_template")
    def create_from_template(self, request):
        template_key = str(request.data.get("template_key", "")).strip()
        if not template_key:
            return Response({"error": "template_key is required"}, status=status.HTTP_400_BAD_REQUEST)

        overrides = request.data.get("overrides", {})
        if overrides is None:
            overrides = {}
        if not isinstance(overrides, dict):
            return Response({"error": "overrides must be an object"}, status=status.HTTP_400_BAD_REQUEST)

        if not is_platform_admin_actor(request.user):
            if not can_manage_registry(request.user, allow_membershipless_fallback=False):
                return Response(
                    {"error": "You do not have permission to create rubrics from templates."},
                    status=status.HTTP_403_FORBIDDEN,
                )

        try:
            rubric = create_rubric_from_template(template_key, created_by=request.user, **overrides)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(self.get_serializer(rubric).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="criteria")
    def add_criteria(self, request, pk=None):
        rubric = self.get_object()
        self._require_registry_manage(detail="You do not have permission to manage rubric criteria.")
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
        ai_signals, ai_error = _parse_ai_signals(request.data.get("ai_signals"))

        if not case_id:
            return Response({"error": "case_id is required"}, status=status.HTTP_400_BAD_REQUEST)
        if ai_error is not None:
            return ai_error
        try:
            case = VettingCase.objects.get(id=case_id)
        except VettingCase.DoesNotExist:
            return Response({"error": "Case not found"}, status=status.HTTP_404_NOT_FOUND)
        if not is_platform_admin_actor(request.user) and not can_view_internal_record(request.user):
            raise PermissionDenied("You cannot evaluate cases outside your organization scope.")

        existing_evaluation = RubricEvaluation.objects.filter(case=case).exists()
        resolved_org_id = resolve_case_organization_id(case, actor=request.user)
        enforce_vetting_operation_quota(
            operation=VETTING_OPERATION_RUBRIC_EVALUATION,
            organization_id=resolved_org_id,
            additional=0 if existing_evaluation else 1,
        )

        if run_async:
            if ai_signals is not None:
                return Response(
                    {"error": "ai_signals are currently supported only for synchronous evaluation"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            evaluate_case_with_rubric.delay(case.id, rubric.id, request.user.id)
            return Response({"message": "Evaluation queued."}, status=status.HTTP_202_ACCEPTED)

        evaluation = RubricEvaluationEngine(case=case, rubric=rubric).evaluate(
            evaluated_by=request.user,
            ai_signals=ai_signals,
        )
        VettingDecisionEngine.generate_recommendation(
            evaluation=evaluation,
            actor=request.user,
            request=request,
        )
        data = RubricEvaluationSerializer(evaluation, context=self.get_serializer_context()).data
        return Response(data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="evaluate_application")
    def evaluate_application(self, request, pk=None):
        """
        Backward-compatible alias used by frontend service.

        Accepts either:
        - application_id (preferred from frontend)
        - case_id
        """
        rubric = self.get_object()
        case_ref = request.data.get("application_id") or request.data.get("case_id")
        run_async = _parse_boolean(request.data.get("async", False))
        ai_signals, ai_error = _parse_ai_signals(request.data.get("ai_signals"))

        if not case_ref:
            return Response({"error": "application_id (or case_id) is required"}, status=status.HTTP_400_BAD_REQUEST)
        if ai_error is not None:
            return ai_error

        case = VettingCase.objects.filter(case_id=str(case_ref)).first()
        if case is None:
            try:
                case = VettingCase.objects.get(id=case_ref)
            except (VettingCase.DoesNotExist, ValueError, TypeError):
                return Response({"error": "Case not found"}, status=status.HTTP_404_NOT_FOUND)
        if not is_platform_admin_actor(request.user) and not can_view_internal_record(request.user):
            raise PermissionDenied("You cannot evaluate cases outside your organization scope.")

        existing_evaluation = RubricEvaluation.objects.filter(case=case).exists()
        resolved_org_id = resolve_case_organization_id(case, actor=request.user)
        enforce_vetting_operation_quota(
            operation=VETTING_OPERATION_RUBRIC_EVALUATION,
            organization_id=resolved_org_id,
            additional=0 if existing_evaluation else 1,
        )

        if run_async:
            if ai_signals is not None:
                return Response(
                    {"error": "ai_signals are currently supported only for synchronous evaluation"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            evaluate_case_with_rubric.delay(case.id, rubric.id, request.user.id)
            return Response({"message": "Evaluation queued."}, status=status.HTTP_202_ACCEPTED)

        evaluation = RubricEvaluationEngine(case=case, rubric=rubric).evaluate(
            evaluated_by=request.user,
            ai_signals=ai_signals,
        )
        VettingDecisionEngine.generate_recommendation(
            evaluation=evaluation,
            actor=request.user,
            request=request,
        )
        data = RubricEvaluationSerializer(evaluation, context=self.get_serializer_context()).data
        return Response(data, status=status.HTTP_200_OK)


class RubricCriteriaViewSet(viewsets.ModelViewSet):
    serializer_class = RubricCriteriaSerializer
    permission_classes = [IsInternalRubricOperator]

    def get_queryset(self):
        user = getattr(self.request, "user", None)
        if user is None or not getattr(user, "is_authenticated", False):
            return RubricCriteria.objects.none()
        queryset = RubricCriteria.objects.select_related("rubric").all()
        rubric_id = self.request.query_params.get("rubric")
        if rubric_id:
            queryset = queryset.filter(rubric_id=rubric_id)
        return queryset.order_by("rubric_id", "display_order", "id")

    def _require_registry_manage(self, *, rubric):
        user = self.request.user
        if is_platform_admin_actor(user):
            return
        if can_manage_registry(user, allow_membershipless_fallback=False):
            return
        raise PermissionDenied("You do not have permission to manage rubric criteria.")

    def perform_create(self, serializer):
        rubric = serializer.validated_data.get("rubric")
        if rubric is None:
            raise PermissionDenied("A valid rubric is required.")
        self._require_registry_manage(rubric=rubric)
        serializer.save()

    def perform_update(self, serializer):
        rubric = getattr(serializer.instance, "rubric", None) or serializer.validated_data.get("rubric")
        if rubric is None:
            raise PermissionDenied("A valid rubric is required.")
        self._require_registry_manage(rubric=rubric)
        serializer.save()

    def perform_destroy(self, instance):
        self._require_registry_manage(rubric=instance.rubric)
        super().perform_destroy(instance)


class RubricEvaluationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = RubricEvaluationSerializer
    permission_classes = [IsInternalRubricOperator]

    def get_queryset(self):
        user = getattr(self.request, "user", None)
        if user is None or not getattr(user, "is_authenticated", False):
            return RubricEvaluation.objects.none()
        queryset = RubricEvaluation.objects.select_related("case", "rubric", "evaluated_by").prefetch_related(
            "overrides",
            "decision_recommendations__generated_by",
            "decision_recommendations__overrides__overridden_by",
        )
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
        ai_signals, ai_error = _parse_ai_signals(request.data.get("ai_signals"))
        if ai_error is not None:
            return ai_error
        resolved_org_id = resolve_case_organization_id(evaluation.case, actor=request.user)
        enforce_vetting_operation_quota(
            operation=VETTING_OPERATION_RUBRIC_EVALUATION,
            organization_id=resolved_org_id,
            additional=0,
        )
        updated = RubricEvaluationEngine(case=evaluation.case, rubric=evaluation.rubric).evaluate(
            evaluated_by=request.user,
            ai_signals=ai_signals,
        )
        VettingDecisionEngine.generate_recommendation(
            evaluation=updated,
            actor=request.user,
            request=request,
        )
        return Response(self.get_serializer(updated).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"], url_path="decision-recommendation")
    def decision_recommendation(self, request, pk=None):
        evaluation = self.get_object()
        recommendation = (
            evaluation.decision_recommendations.select_related("generated_by")
            .prefetch_related("overrides__overridden_by")
            .filter(is_latest=True)
            .order_by("-created_at")
            .first()
        )
        if recommendation is None:
            recommendation = VettingDecisionEngine.generate_recommendation(
                evaluation=evaluation,
                actor=request.user,
                request=request,
            )
        serializer = VettingDecisionRecommendationSerializer(recommendation, context=self.get_serializer_context())
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[IsInternalRubricOperator, RequiresRecentAuth],
        url_path="override-decision",
    )
    def override_decision(self, request, pk=None):
        evaluation = self.get_object()
        payload = VettingDecisionOverrideRequestSerializer(data=request.data)
        payload.is_valid(raise_exception=True)

        recommendation = (
            evaluation.decision_recommendations.filter(is_latest=True)
            .order_by("-created_at")
            .first()
        )
        if recommendation is None:
            recommendation = VettingDecisionEngine.generate_recommendation(
                evaluation=evaluation,
                actor=request.user,
                request=request,
            )

        try:
            recommendation, override = VettingDecisionEngine.record_human_override(
                recommendation=recommendation,
                actor=request.user,
                overridden_recommendation_status=payload.validated_data["recommendation_status"],
                rationale=payload.validated_data["rationale"],
                request=request,
            )
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                "message": "Decision recommendation override recorded.",
                "recommendation": VettingDecisionRecommendationSerializer(
                    recommendation,
                    context=self.get_serializer_context(),
                ).data,
                "override_id": str(override.id),
            },
            status=status.HTTP_200_OK,
        )

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

            if isinstance(evaluation.criterion_scores, dict):
                trace = evaluation.criterion_scores.get(RubricEvaluationEngine.TRACE_KEY)
                if isinstance(trace, dict):
                    events = list(trace.get("events", []))
                    events.append(
                        {
                            "event_type": "override_applied",
                            "criterion_id": str(criterion.id),
                            "criterion_name": criterion.name,
                            "overridden_by": str(request.user.id),
                            "timestamp": str(override.created_at.isoformat()),
                            "original_score": original,
                            "overridden_score": overridden_score,
                        }
                    )
                    trace["events"] = events
                    evaluation.criterion_scores[RubricEvaluationEngine.TRACE_KEY] = trace

            evaluation.save(update_fields=["criterion_scores", "review_reasons", "requires_manual_review", "status", "updated_at"])

        return Response(
            {
                "message": "Override recorded; evaluation marked for manual review.",
                "override": CriteriaOverrideSerializer(override).data,
            },
            status=status.HTTP_201_CREATED,
        )
