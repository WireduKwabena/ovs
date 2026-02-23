from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.invitations.permissions import IsAuthenticatedOrCandidateAccessSession
from apps.applications.models import VettingCase

try:
    from drf_spectacular.utils import extend_schema
except ModuleNotFoundError:  # pragma: no cover - optional in some setups
    def extend_schema(*args, **kwargs):
        def decorator(func):
            return func

        return decorator

from .models import InterviewFeedback, InterviewQuestion, InterviewResponse, InterviewSession
from .permissions import IsHrAdminOrServiceAuthenticated, is_hr_admin_user
from .serializers import (
    InterviewActionErrorSerializer,
    InterviewAnalyticsDashboardQuerySerializer,
    InterviewAnalyticsDashboardResponseSerializer,
    InterviewAvatarSessionResponseSerializer,
    InterviewCompareRequestSerializer,
    InterviewCompareResponseSerializer,
    InterviewFeedbackSerializer,
    InterviewGenerateFlagsRequestSerializer,
    InterviewGenerateFlagsResponseSerializer,
    InterviewPlaybackResponseSerializer,
    InterviewQuestionSerializer,
    InterviewResponseSerializer,
    InterviewSessionSerializer,
)
from .services.analytics_service import InterviewAnalytics
from .services.comparison_service import ApplicantComparisonService
from .services.flag_generator import InterrogationFlagGenerator
from .services.heygen_sdk import build_avatar_session_payload
from .services.playback_service import InterviewPlaybackService
from .tasks import analyze_response_task, generate_session_summary_task


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
        if not is_hr_admin_user(user) and not getattr(user, "is_authenticated", False):
            return InterviewSession.objects.none()
        if is_hr_admin_user(user):
            return queryset.order_by("-created_at")
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
        generate_session_summary_task.delay(session.id)

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

        analyze_response_task.delay(response.id)

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
        self.get_object()
        try:
            payload = build_avatar_session_payload()
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
        queryset = InterviewQuestion.objects.all()
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
        if not is_hr_admin_user(user) and not getattr(user, "is_authenticated", False):
            return InterviewResponse.objects.none()
        if is_hr_admin_user(user):
            return queryset.order_by("session_id", "sequence_number")
        return queryset.filter(
            Q(session__case__applicant=user) | Q(session__case__assigned_to=user)
        ).order_by("session_id", "sequence_number")

    def perform_create(self, serializer):
        enrollment_id = _candidate_enrollment_id(self.request)
        if enrollment_id:
            session = serializer.validated_data["session"]
            if session.case.candidate_enrollment_id != enrollment_id:
                raise PermissionDenied("You cannot submit responses for this interview session.")
        response = serializer.save(answered_at=timezone.now())
        response.question.increment_usage()

    @action(detail=True, methods=["post"], url_path="analyze")
    def analyze(self, request, pk=None):
        response = self.get_object()
        analyze_response_task.delay(response.id)
        return Response({"message": "Response queued for analysis."}, status=status.HTTP_202_ACCEPTED)


class InterviewFeedbackViewSet(viewsets.ModelViewSet):
    serializer_class = InterviewFeedbackSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = InterviewFeedback.objects.select_related("session", "reviewer")
        session_id = self.request.query_params.get("session")
        if session_id:
            queryset = queryset.filter(session_id=session_id)
        return queryset.order_by("-created_at")

    def perform_create(self, serializer):
        serializer.save(reviewer=self.request.user)
