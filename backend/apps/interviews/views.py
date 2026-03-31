import uuid
import logging

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.core.files.storage import default_storage
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.invitations.permissions import IsAuthenticatedOrCandidateAccessSession
from apps.applications.models import VettingCase
from apps.billing.quotas import (
    VETTING_OPERATION_INTERVIEW_ANALYSIS,
    enforce_vetting_operation_quota,
    resolve_case_organization_id,
)
from apps.core.permissions import (
    can_access_organization_id,
    get_request_active_organization_id,
    get_user_allowed_organization_ids,
    is_government_workflow_operator,
    is_platform_admin_user,
)
from apps.tenants.models import Organization

try:
    from drf_spectacular.utils import extend_schema
except ModuleNotFoundError:  # pragma: no cover - optional in some setups
    def extend_schema(*args, **kwargs):
        def decorator(func):
            return func

        return decorator

from .models import InterviewFeedback, InterviewQuestion, InterviewResponse, InterviewSession
from .permissions import IsHrAdminOrServiceAuthenticated
from .serializers import (
    InterviewActionErrorSerializer,
    InterviewAnalyticsDashboardQuerySerializer,
    InterviewAnalyticsDashboardResponseSerializer,
    InterviewAvatarSessionResponseSerializer,
    InterviewResponseUploadRequestSerializer,
    InterviewResponseUploadResponseSerializer,
    InterviewCompareRequestSerializer,
    InterviewCompareResponseSerializer,
    InterviewFeedbackSerializer,
    InterviewGenerateFlagsRequestSerializer,
    InterviewGenerateFlagsResponseSerializer,
    InterviewPlaybackResponseSerializer,
    InterviewQuestionSerializer,
    InterviewResponseSerializer,
    InterviewSessionSerializer,
    LegacyInterviewStartRequestSerializer,
    LegacyInterviewStartResponseSerializer,
)
from .services.analytics_service import InterviewAnalytics
from .services.comparison_service import ApplicantComparisonService
from .services.flag_generator import InterrogationFlagGenerator
from .services.livekit_sdk import build_interview_session_payload
from .services.playback_service import InterviewPlaybackService
from .tasks import analyze_response_task, generate_session_summary_task

logger = logging.getLogger(__name__)


def _question_type_from_intent(intent: str) -> str:
    normalized = (intent or "").strip().lower()
    if normalized == "resolve_flag":
        return "flag_specific"
    if normalized in {"verification", "document_verification"}:
        return "verification"
    return "general"


def _candidate_enrollment_id(request) -> int | None:
    candidate_session = getattr(request, "candidate_access_session", None)
    return getattr(candidate_session, "enrollment_id", None)


def _is_service_authenticated_request(request) -> bool:
    return bool(getattr(request, "service_authenticated", False))


def _is_internal_interview_operator(request, *, organization_id=None) -> bool:
    org_id = organization_id
    if org_id is None:
        org_id = get_request_active_organization_id(request)
    return is_government_workflow_operator(
        getattr(request, "user", None),
        organization_id=org_id,
    )


def _scope_internal_interview_queryset(
    queryset,
    *,
    request,
    organization_field: str,
    assigned_field: str,
):
    user = getattr(request, "user", None)
    if is_platform_admin_user(user):
        return queryset
    membership_org_ids = get_user_allowed_organization_ids(user)
    if membership_org_ids:
        explicit_active_org_id = str(
            getattr(request, "META", {}).get("HTTP_X_ACTIVE_ORGANIZATION_ID", "")
            or getattr(request, "query_params", {}).get("active_organization_id", "")
            or ""
        ).strip()
        if explicit_active_org_id and explicit_active_org_id in membership_org_ids:
            return queryset.filter(**{organization_field: explicit_active_org_id})
        return queryset.filter(**{f"{organization_field}__in": list(membership_org_ids)})
    return queryset.filter(
        **{
            assigned_field: user,
            f"{organization_field}__isnull": True,
        }
    )


def _assert_case_interview_access(request, case: VettingCase) -> None:
    enrollment_id = _candidate_enrollment_id(request)
    if enrollment_id:
        if case.candidate_enrollment_id != enrollment_id:
            raise PermissionDenied("Candidate access session cannot access interviews for another enrollment.")
        return

    if _is_service_authenticated_request(request):
        return

    user = getattr(request, "user", None)
    if not getattr(user, "is_authenticated", False):
        raise PermissionDenied("Authentication is required.")
    if is_platform_admin_user(user):
        return

    case_org_id = getattr(case, "organization_id", None)
    if _is_internal_interview_operator(request, organization_id=case_org_id):
        if case_org_id and not can_access_organization_id(
            user,
            case_org_id,
            allow_membershipless_fallback=False,
        ):
            raise PermissionDenied("You cannot access interview data for another organization.")
        if not case_org_id and getattr(case, "assigned_to_id", None) != getattr(user, "id", None):
            raise PermissionDenied("Legacy unscoped interview data is restricted to assigned actors.")
        return

    if case.applicant_id != getattr(user, "id", None) and case.assigned_to_id != getattr(user, "id", None):
        raise PermissionDenied("You do not have access to this interview case.")


def _reserve_interview_analysis_quota(*, case, actor, additional: int) -> None:
    resolved_org_id = resolve_case_organization_id(case, actor=actor)
    quota_actor = actor if (resolved_org_id is None and getattr(actor, "is_authenticated", False)) else None

    if resolved_org_id:
        with transaction.atomic():
            Organization.objects.select_for_update().filter(id=resolved_org_id).exists()
            enforce_vetting_operation_quota(
                operation=VETTING_OPERATION_INTERVIEW_ANALYSIS,
                user=quota_actor,
                organization_id=resolved_org_id,
                additional=additional,
            )
        return

    enforce_vetting_operation_quota(
        operation=VETTING_OPERATION_INTERVIEW_ANALYSIS,
        user=quota_actor,
        organization_id=resolved_org_id,
        additional=additional,
    )


def _queue_interview_task_safely(task, *args, fallback_to_inline: bool = False) -> bool:
    try:
        task.delay(*args)
        return True
    except Exception as exc:
        logger.warning(
            "Failed to queue interview task '%s' with args=%s: %s",
            getattr(task, "name", repr(task)),
            args,
            exc,
        )
        if fallback_to_inline:
            try:
                task.run(*args)
                return True
            except Exception as run_exc:
                logger.warning(
                    "Failed inline interview task '%s' with args=%s after queue failure: %s",
                    getattr(task, "name", repr(task)),
                    args,
                    run_exc,
                )
        return False


class InterviewSessionViewSet(viewsets.ModelViewSet):
    serializer_class = InterviewSessionSerializer
    permission_classes = [IsAuthenticatedOrCandidateAccessSession]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return InterviewSession.objects.none()
        queryset = InterviewSession.objects.select_related(
            "case",
            "case__applicant",
            "case__candidate_enrollment",
        ).prefetch_related("responses")

        case_id = self.request.query_params.get("case")
        status_value = self.request.query_params.get("status")
        if case_id:
            queryset = queryset.filter(case_id=case_id)
        if status_value:
            queryset = queryset.filter(status=status_value)

        enrollment_id = _candidate_enrollment_id(self.request)
        if enrollment_id:
            return queryset.filter(case__candidate_enrollment_id=enrollment_id).order_by("-created_at")
        if _is_service_authenticated_request(self.request):
            return queryset.order_by("-created_at")

        user = self.request.user
        scope = str(self.request.query_params.get("scope", "") or "").strip().lower()
        if not getattr(user, "is_authenticated", False):
            return InterviewSession.objects.none()

        if _is_internal_interview_operator(self.request):
            scoped = _scope_internal_interview_queryset(
                queryset,
                request=self.request,
                organization_field="case__organization_id",
                assigned_field="case__assigned_to",
            )
            if scope in {"assigned", "mine", "my"}:
                scoped = scoped.filter(case__assigned_to=user)
            return scoped.order_by("-created_at")

        return queryset.filter(Q(case__applicant=user) | Q(case__assigned_to=user)).order_by("-created_at")

    def get_object(self):
        queryset = self.filter_queryset(self.get_queryset())
        lookup_value = self.kwargs.get(self.lookup_url_kwarg or self.lookup_field)
        if lookup_value is None:
            return super().get_object()

        if str(lookup_value).isdigit():
            obj = queryset.filter(pk=lookup_value).first()
            if obj is None:
                obj = queryset.filter(session_id=lookup_value).first()
        else:
            obj = queryset.filter(session_id=lookup_value).first()

        if obj is None:
            obj = get_object_or_404(queryset, pk=lookup_value)
        self.check_object_permissions(self.request, obj)
        return obj

    def perform_create(self, serializer):
        if _candidate_enrollment_id(self.request):
            raise PermissionDenied("Candidates cannot create interview sessions directly.")
        case = serializer.validated_data["case"]
        _assert_case_interview_access(self.request, case)
        serializer.save()

    @action(detail=True, methods=["post"], url_path="start")
    def start(self, request, pk=None):
        session = self.get_object()
        if session.status != "created":
            return Response({"error": "Session has already started or ended."}, status=status.HTTP_400_BAD_REQUEST)
        session.start_session()
        return Response(self.get_serializer(session).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="complete")
    def complete(self, request, pk=None):
        session = self.get_object()
        if session.status in {"completed", "cancelled"}:
            return Response({"error": "Session is already finished."}, status=status.HTTP_400_BAD_REQUEST)

        session.complete_session()
        _queue_interview_task_safely(
            generate_session_summary_task,
            session.id,
            fallback_to_inline=bool(
                getattr(settings, "INTERVIEWS_TASK_INLINE_FALLBACK_ENABLED", False)
            ),
        )

        enrollment = session.case.candidate_enrollment
        if enrollment and enrollment.status in {"invited", "registered", "in_progress"}:
            enrollment.status = "completed"
            enrollment.completed_at = timezone.now()
            enrollment.save(update_fields=["status", "completed_at", "updated_at"])

        return Response(self.get_serializer(session).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="save-exchange")
    def save_exchange(self, request, pk=None):
        session = self.get_object()
        question_text = (request.data.get("question_text") or "").strip()
        if not question_text:
            return Response({"error": "question_text is required."}, status=status.HTTP_400_BAD_REQUEST)

        raw_sequence = request.data.get("sequence_number") or (session.current_question_number + 1)
        try:
            sequence_number = int(raw_sequence)
        except (TypeError, ValueError):
            return Response({"error": "sequence_number must be an integer."}, status=status.HTTP_400_BAD_REQUEST)
        question_intent = (request.data.get("question_intent") or "").strip()
        target_flag_id = request.data.get("target_flag_id")

        target_flag = None
        if target_flag_id:
            target_flag = session.case.interrogation_flags.filter(id=target_flag_id).first()

        question, _ = InterviewQuestion.objects.get_or_create(
            question_text=question_text,
            defaults={
                "question_type": _question_type_from_intent(question_intent),
                "difficulty": "medium",
                "evaluation_rubric": "Assess clarity, specificity, and consistency with submitted records.",
                "expected_keywords": [],
                "is_active": False,
            },
        )

        response, created = InterviewResponse.objects.update_or_create(
            session=session,
            sequence_number=sequence_number,
            defaults={
                "question": question,
                "target_flag": target_flag,
            },
        )
        if created:
            question.increment_usage()

        fields_to_update = []
        if session.current_question_number < sequence_number:
            session.current_question_number = sequence_number
            fields_to_update.append("current_question_number")
        if session.total_questions_asked < sequence_number:
            session.total_questions_asked = sequence_number
            fields_to_update.append("total_questions_asked")
        if fields_to_update:
            session.save(update_fields=fields_to_update)

        return Response(
            {
                "response_id": response.id,
                "question_number": response.sequence_number,
                "question_text": question.question_text,
                "current_flag_id": response.target_flag_id,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="update-exchange")
    def update_exchange(self, request, pk=None):
        session = self.get_object()
        sequence_number = request.data.get("sequence_number")

        responses = session.responses.select_related("question", "target_flag").order_by("-sequence_number")
        if sequence_number is not None:
            responses = responses.filter(sequence_number=sequence_number)
        response = responses.first()
        if response is None:
            return Response({"error": "No exchange found for this session."}, status=status.HTTP_404_NOT_FOUND)

        update_fields = []
        transcript = request.data.get("transcript")
        if transcript is not None:
            response.transcript = transcript
            update_fields.append("transcript")

        video_url = request.data.get("video_url")
        if video_url is not None:
            response.video_url = video_url
            update_fields.append("video_url")

        sentiment = request.data.get("sentiment")
        if sentiment is not None:
            response.sentiment = sentiment
            update_fields.append("sentiment")

        reserve_additional = 0 if response.answered_at is not None else 1
        _reserve_interview_analysis_quota(
            case=session.case,
            actor=request.user,
            additional=reserve_additional,
        )

        response.answered_at = timezone.now()
        update_fields.append("answered_at")
        response.save(update_fields=update_fields)

        if response.target_flag and response.target_flag.status == "pending":
            response.target_flag.mark_addressed()
            session.flags_addressed.add(response.target_flag)

        history_entry = {
            "question_number": response.sequence_number,
            "question_text": response.question.question_text,
            "transcript": response.transcript,
            "sentiment": response.sentiment,
            "nonverbal_data": request.data.get("nonverbal_data") or {},
            "answered_at": response.answered_at.isoformat(),
        }
        session.conversation_history = [*(session.conversation_history or []), history_entry]
        session.save(update_fields=["conversation_history"])

        _queue_interview_task_safely(
            analyze_response_task,
            response.id,
            fallback_to_inline=bool(
                getattr(settings, "INTERVIEWS_TASK_INLINE_FALLBACK_ENABLED", False)
            ),
        )

        return Response(
            {
                "response_id": response.id,
                "question_number": response.sequence_number,
                "question_text": response.question.question_text,
                "current_flag_id": response.target_flag_id,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="avatar-session")
    @extend_schema(
        responses={
            200: InterviewAvatarSessionResponseSerializer,
            503: InterviewActionErrorSerializer,
        }
    )
    def avatar_session(self, request, pk=None):
        session = self.get_object()
        try:
            case = getattr(session, "case", None)
            case_title = str(getattr(case, "title", "") or "").strip()
            payload = build_interview_session_payload(
                session_id=str(session.session_id),
                case_title=case_title,
            )
        except RuntimeError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response(payload, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"], url_path="playback")
    @extend_schema(
        responses={
            200: InterviewPlaybackResponseSerializer,
            404: InterviewActionErrorSerializer,
        }
    )
    def playback(self, request, pk=None):
        session = self.get_object()
        payload = InterviewPlaybackService.get_playback_data(session.session_id)
        return Response(payload, status=status.HTTP_200_OK)

    @action(
        detail=False,
        methods=["get"],
        url_path="analytics-dashboard",
        permission_classes=[IsHrAdminOrServiceAuthenticated],
    )
    @extend_schema(
        parameters=[InterviewAnalyticsDashboardQuerySerializer],
        responses={
            200: InterviewAnalyticsDashboardResponseSerializer,
            400: InterviewActionErrorSerializer,
            403: InterviewActionErrorSerializer,
        },
    )
    def analytics_dashboard(self, request):
        query_serializer = InterviewAnalyticsDashboardQuerySerializer(data=request.query_params)
        query_serializer.is_valid(raise_exception=True)
        days = query_serializer.validated_data["days"]

        payload = {
            "metrics": InterviewAnalytics.get_dashboard_metrics(days=days),
            "trends": InterviewAnalytics.get_trend_data(days=days),
            "flags": InterviewAnalytics.get_flag_breakdown(days=days),
            "behavioral": InterviewAnalytics.get_behavioral_analysis(days=days),
            "quality": InterviewAnalytics.get_interview_quality_metrics(days=days),
        }
        return Response(payload, status=status.HTTP_200_OK)

    @action(
        detail=False,
        methods=["post"],
        url_path="compare",
        permission_classes=[IsHrAdminOrServiceAuthenticated],
    )
    @extend_schema(
        request=InterviewCompareRequestSerializer,
        responses={
            200: InterviewCompareResponseSerializer,
            400: InterviewActionErrorSerializer,
            403: InterviewActionErrorSerializer,
            404: InterviewActionErrorSerializer,
        },
    )
    def compare(self, request):
        input_serializer = InterviewCompareRequestSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        session_ids = input_serializer.validated_data["session_ids"]

        payload = ApplicantComparisonService.compare_sessions(session_ids)
        if payload.get("error"):
            return Response(payload, status=status.HTTP_404_NOT_FOUND)
        return Response(payload, status=status.HTTP_200_OK)

    @action(
        detail=False,
        methods=["post"],
        url_path="generate-flags",
        permission_classes=[IsHrAdminOrServiceAuthenticated],
    )
    @extend_schema(
        request=InterviewGenerateFlagsRequestSerializer,
        responses={
            200: InterviewGenerateFlagsResponseSerializer,
            400: InterviewActionErrorSerializer,
            403: InterviewActionErrorSerializer,
            404: InterviewActionErrorSerializer,
        },
    )
    def generate_flags(self, request):
        input_serializer = InterviewGenerateFlagsRequestSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        case_id = input_serializer.validated_data["case"]

        case = VettingCase.objects.filter(id=case_id).first()
        if case is None:
            case = VettingCase.objects.filter(case_id=case_id).first()
        if case is None:
            return Response({"error": "Vetting case not found."}, status=status.HTTP_404_NOT_FOUND)

        persist = input_serializer.validated_data["persist"]
        replace_pending = input_serializer.validated_data["replace_pending"]
        payload = InterrogationFlagGenerator.sync_case_flags(
            case=case,
            persist=persist,
            replace_pending=replace_pending,
        )
        return Response(payload, status=status.HTTP_200_OK)


class InterviewQuestionViewSet(viewsets.ModelViewSet):
    serializer_class = InterviewQuestionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return InterviewQuestion.objects.none()
        user = self.request.user
        queryset = InterviewQuestion.objects.all()
        if not is_platform_admin_user(user) and not _is_internal_interview_operator(self.request):
            return InterviewQuestion.objects.none()
        question_type = self.request.query_params.get("question_type")
        difficulty = self.request.query_params.get("difficulty")
        active = self.request.query_params.get("active")

        if question_type:
            queryset = queryset.filter(question_type=question_type)
        if difficulty:
            queryset = queryset.filter(difficulty=difficulty)
        if active in {"true", "false"}:
            queryset = queryset.filter(is_active=(active == "true"))

        return queryset.order_by("question_type", "difficulty", "id")

    def perform_create(self, serializer):
        user = self.request.user
        if not is_platform_admin_user(user) and not _is_internal_interview_operator(self.request):
            raise PermissionDenied("Only authorized internal workflow actors can manage interview questions.")
        serializer.save(created_by=self.request.user)


class InterviewResponseViewSet(viewsets.ModelViewSet):
    serializer_class = InterviewResponseSerializer
    permission_classes = [IsAuthenticatedOrCandidateAccessSession]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return InterviewResponse.objects.none()
        queryset = InterviewResponse.objects.select_related("session", "question", "target_flag")

        session_id = self.request.query_params.get("session")
        if session_id:
            queryset = queryset.filter(session_id=session_id)

        enrollment_id = _candidate_enrollment_id(self.request)
        if enrollment_id:
            return queryset.filter(session__case__candidate_enrollment_id=enrollment_id).order_by(
                "session_id",
                "sequence_number",
            )
        if _is_service_authenticated_request(self.request):
            return queryset.order_by("session_id", "sequence_number")

        user = self.request.user
        if not getattr(user, "is_authenticated", False):
            return InterviewResponse.objects.none()

        if _is_internal_interview_operator(self.request):
            scoped = _scope_internal_interview_queryset(
                queryset,
                request=self.request,
                organization_field="session__case__organization_id",
                assigned_field="session__case__assigned_to",
            )
            return scoped.order_by("session_id", "sequence_number")

        return queryset.filter(
            Q(session__case__applicant=user) | Q(session__case__assigned_to=user)
        ).order_by("session_id", "sequence_number")

    def perform_create(self, serializer):
        enrollment_id = _candidate_enrollment_id(self.request)
        session = serializer.validated_data["session"]
        if enrollment_id:
            if session.case.candidate_enrollment_id != enrollment_id:
                raise PermissionDenied("You cannot submit responses for this interview session.")
        _assert_case_interview_access(self.request, session.case)
        _reserve_interview_analysis_quota(
            case=session.case,
            actor=self.request.user,
            additional=1,
        )
        response = serializer.save(answered_at=timezone.now())
        response.question.increment_usage()

    @action(detail=True, methods=["post"], url_path="analyze")
    def analyze(self, request, pk=None):
        response = self.get_object()
        reserve_additional = 0 if response.answered_at is not None else 1
        _reserve_interview_analysis_quota(
            case=response.session.case,
            actor=request.user,
            additional=reserve_additional,
        )
        if response.answered_at is None:
            response.answered_at = timezone.now()
            response.save(update_fields=["answered_at"])
        _queue_interview_task_safely(
            analyze_response_task,
            response.id,
            fallback_to_inline=bool(
                getattr(settings, "INTERVIEWS_TASK_INLINE_FALLBACK_ENABLED", False)
            ),
        )
        return Response({"message": "Response queued for analysis."}, status=status.HTTP_202_ACCEPTED)


class InterviewFeedbackViewSet(viewsets.ModelViewSet):
    serializer_class = InterviewFeedbackSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return InterviewFeedback.objects.none()
        user = self.request.user
        queryset = InterviewFeedback.objects.select_related("session", "reviewer")
        if not is_platform_admin_user(user):
            if _is_internal_interview_operator(self.request):
                queryset = _scope_internal_interview_queryset(
                    queryset,
                    request=self.request,
                    organization_field="session__case__organization_id",
                    assigned_field="session__case__assigned_to",
                )
            else:
                queryset = queryset.filter(
                    Q(session__case__applicant=user) | Q(session__case__assigned_to=user)
                )
        session_id = self.request.query_params.get("session")
        if session_id:
            queryset = queryset.filter(session_id=session_id)
        return queryset.order_by("-created_at")

    def perform_create(self, serializer):
        user = self.request.user
        if not is_platform_admin_user(user) and not _is_internal_interview_operator(self.request):
            raise PermissionDenied("Only authorized internal workflow actors can submit interview feedback.")
        serializer.save(reviewer=self.request.user)


def _build_interview_ws_url(request, session_id: str) -> str:
    protocol = "wss" if request.is_secure() else "ws"
    host = request.get_host()
    return f"{protocol}://{host}/ws/interview/{session_id}/"


class LegacyInterviewStartAPIView(APIView):
    """
    Backward-compatible bootstrap endpoint used by older frontend integrations.

    POST /api/interviews/interrogation/start/
    Body: {"application_id": "<case_id or pk>"}
    """

    permission_classes = [IsAuthenticatedOrCandidateAccessSession]

    @extend_schema(
        request=LegacyInterviewStartRequestSerializer,
        responses={
            200: LegacyInterviewStartResponseSerializer,
            400: InterviewActionErrorSerializer,
            404: InterviewActionErrorSerializer,
        },
    )
    def post(self, request):
        application_id = request.data.get("application_id")
        if not application_id:
            return Response({"error": "application_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        case = VettingCase.objects.filter(case_id=str(application_id)).first()
        if case is None:
            try:
                case = VettingCase.objects.get(id=application_id)
            except (VettingCase.DoesNotExist, ValueError, TypeError):
                return Response({"error": "Vetting case not found."}, status=status.HTTP_404_NOT_FOUND)

        enrollment_id = _candidate_enrollment_id(request)
        if enrollment_id and case.candidate_enrollment_id != enrollment_id:
            raise PermissionDenied("Candidate access session cannot start interviews for another enrollment.")
        _assert_case_interview_access(request, case)

        session = (
            InterviewSession.objects.filter(case=case)
            .order_by("-created_at")
            .first()
        )
        if session is None:
            session = InterviewSession.objects.create(case=case, use_dynamic_questions=True)

        if session.status == "created":
            session.start_session()

        serialized = InterviewSessionSerializer(session, context={"request": request}).data
        return Response(
            {
                "session_id": session.session_id,
                "interrogation_flags": serialized.get("interrogation_flags", []),
                "websocket_url": _build_interview_ws_url(request, session.session_id),
            },
            status=status.HTTP_200_OK,
        )


class InterviewResponseUploadAPIView(APIView):
    """
    Backward-compatible media upload endpoint used before websocket-only flow.

    POST /api/interviews/upload-response/
    multipart: video, session_id
    """

    permission_classes = [IsAuthenticatedOrCandidateAccessSession]

    @extend_schema(
        request=InterviewResponseUploadRequestSerializer,
        responses={
            201: InterviewResponseUploadResponseSerializer,
            400: InterviewActionErrorSerializer,
            404: InterviewActionErrorSerializer,
        },
    )
    def post(self, request):
        session_ref = request.data.get("session_id")
        video = request.FILES.get("video")

        if not session_ref:
            return Response({"error": "session_id is required."}, status=status.HTTP_400_BAD_REQUEST)
        if video is None:
            return Response({"error": "video file is required."}, status=status.HTTP_400_BAD_REQUEST)

        session = InterviewSession.objects.filter(session_id=str(session_ref)).first()
        if session is None:
            session = InterviewSession.objects.filter(id=session_ref).first()
        if session is None:
            return Response({"error": "Interview session not found."}, status=status.HTTP_404_NOT_FOUND)
        _assert_case_interview_access(request, session.case)

        upload_path = f"interview_uploads/{session.session_id}/{uuid.uuid4().hex}.webm"
        saved_path = default_storage.save(upload_path, video)
        try:
            saved_url = default_storage.url(saved_path)
        except Exception:
            saved_url = ""

        return Response(
            {
                "video_path": saved_path,
                "video_url": saved_url,
            },
            status=status.HTTP_201_CREATED,
        )
