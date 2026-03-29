"""User profile and management views."""

import logging
from django.db import transaction
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.users.models import User, UserProfile
from apps.users.serializers import (
    AdminUserSerializer,
    ProfileResponseSerializer,
    ProfileUpdateSerializer,
    UserSerializer,
    ActiveOrganizationSelectionSerializer,
    ActiveOrganizationSelectionResponseSerializer,
    ErrorResponseSerializer,
)
from apps.core.authz import (
    ROLE_ADMIN,
    get_user_capabilities,
    get_user_committees,
    get_user_roles,
    has_role,
    requires_two_factor_for_user,
)
from apps.core.permissions import (
    ACTIVE_ORGANIZATION_SESSION_KEY,
    clear_request_tenant_context_cache,
    get_request_tenant_context,
)

try:
    from drf_spectacular.utils import PolymorphicProxySerializer, extend_schema
except ModuleNotFoundError:  # pragma: no cover - optional in some setups
    class PolymorphicProxySerializer:  # pragma: no cover - docs-only fallback
        def __init__(self, *args, **kwargs):
            pass

    def extend_schema(*args, **kwargs):
        def decorator(func):
            return func
        return decorator

logger = logging.getLogger(__name__)


def _profile_governance_context(*, request, user) -> dict:
    """Build governance context for user profile response."""
    resolved = get_request_tenant_context(request)
    active_organization = resolved.get("active_organization")
    committees = get_user_committees(
        user,
        organization_id=str(active_organization.get("id")) if isinstance(active_organization, dict) else None,
    )
    return {
        "organizations": resolved.get("organizations", []),
        "organization_memberships": resolved.get("organization_memberships", []),
        "active_organization": active_organization,
        "active_organization_source": resolved.get("active_organization_source", "none"),
        "invalid_requested_organization_id": resolved.get("invalid_requested_organization_id", ""),
        "committees": committees,
    }


@extend_schema(responses={200: ProfileResponseSerializer})
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def profile_view(request):
    """
    Get current user profile
    GET /api/auth/profile/
    """
    UserProfile.objects.get_or_create(user=request.user)

    if has_role(request.user, ROLE_ADMIN):
        serializer = AdminUserSerializer(request.user, context={"request": request})
        user_type = request.user.user_type
    else:
        serializer = UserSerializer(request.user, context={"request": request})
        user_type = request.user.user_type

    governance_context = _profile_governance_context(request=request, user=request.user)
    return Response(
        {
            "user": serializer.data,
            "user_type": user_type,
            "roles": sorted(get_user_roles(request.user)),
            "capabilities": sorted(get_user_capabilities(request.user)),
            "is_internal_operator": requires_two_factor_for_user(request.user),
            **governance_context,
        }
    )


@extend_schema(
    request=ActiveOrganizationSelectionSerializer,
    responses={
        200: ActiveOrganizationSelectionResponseSerializer,
        400: ErrorResponseSerializer,
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def set_active_organization_view(request):
    """
    Persist selected active organization in session for subsequent requests.

    POST /api/auth/profile/active-organization/
    """
    payload = ActiveOrganizationSelectionSerializer(data=request.data)
    payload.is_valid(raise_exception=True)

    session = getattr(request, "session", None)
    if session is None:
        return Response({"error": "Session context unavailable."}, status=status.HTTP_400_BAD_REQUEST)

    clear = bool(payload.validated_data.get("clear", False))
    organization_id = payload.validated_data.get("organization_id")

    if clear or organization_id is None:
        session.pop(ACTIVE_ORGANIZATION_SESSION_KEY, None)
        session.modified = True
        clear_request_tenant_context_cache(request)
        context = _profile_governance_context(request=request, user=request.user)
        return Response(
            {
                "message": "Active organization cleared.",
                "active_organization": context.get("active_organization"),
                "active_organization_source": context.get("active_organization_source", "none"),
                "invalid_requested_organization_id": context.get("invalid_requested_organization_id", ""),
            },
            status=status.HTTP_200_OK,
        )

    requested_org_id = str(organization_id)
    organization_context = get_request_tenant_context(request)
    allowed_org_ids = {str(item.get("id")) for item in organization_context.get("organizations", [])}
    if requested_org_id not in allowed_org_ids:
        return Response(
            {"error": "Selected organization is not available for the authenticated user."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    session[ACTIVE_ORGANIZATION_SESSION_KEY] = requested_org_id
    session.modified = True
    clear_request_tenant_context_cache(request)
    context = _profile_governance_context(request=request, user=request.user)
    return Response(
        {
            "message": "Active organization updated.",
            "active_organization": context.get("active_organization"),
            "active_organization_source": context.get("active_organization_source", "none"),
            "invalid_requested_organization_id": context.get("invalid_requested_organization_id", ""),
        },
        status=status.HTTP_200_OK,
    )


@extend_schema(
    request=ProfileUpdateSerializer,
    responses={
        200: PolymorphicProxySerializer(
            component_name="ProfileUpdateResponse",
            serializers=[UserSerializer, AdminUserSerializer],
            resource_type_field_name=None,
        ),
        400: ErrorResponseSerializer,
    },
)
@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def update_profile_view(request):
    """
    Update user profile
    PUT/PATCH /api/auth/profile/
    """
    user = request.user
    serializer = ProfileUpdateSerializer(data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)

    validated = serializer.validated_data
    user_fields = {
        "email",
        "first_name",
        "last_name",
        "phone_number",
        "organization",
        "department",
    }
    profile_fields = {
        "date_of_birth",
        "nationality",
        "address",
        "city",
        "country",
        "postal_code",
        "current_job_title",
        "years_of_experience",
        "linkedin_url",
        "bio",
    }

    update_user_fields = [field for field in user_fields if field in validated]
    update_profile_fields = [field for field in profile_fields if field in validated]

    with transaction.atomic():
        if "email" in validated:
            user.email = str(validated["email"]).strip().lower()
        for field in update_user_fields:
            if field == "email":
                continue
            setattr(user, field, validated[field])
        if update_user_fields:
            user.save(update_fields=sorted(set(update_user_fields + ["updated_at"])))

        profile, _ = UserProfile.objects.get_or_create(user=user)
        for field in update_profile_fields:
            setattr(profile, field, validated[field])
        if update_profile_fields:
            profile.calculate_completion()
            profile.save(
                update_fields=sorted(
                    set(update_profile_fields + ["profile_completion_percentage", "updated_at"])
                )
            )

    user.refresh_from_db()

    if has_role(request.user, ROLE_ADMIN):
        response_serializer = AdminUserSerializer(user, context={"request": request})
    else:
        response_serializer = UserSerializer(user, context={"request": request})
    return Response(response_serializer.data)



