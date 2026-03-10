from __future__ import annotations

from uuid import uuid4

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.text import slugify
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.authentication.models import User
from apps.core.authz import get_user_organization_by_id
from apps.core.permissions import get_request_active_organization_id, get_request_tenant_context, is_platform_admin_user
from apps.core.policies.registry_policy import can_manage_registry_governance

from .models import Committee, CommitteeMembership, Organization, OrganizationMembership
from .serializers import (
    CommitteeChairReassignSerializer,
    CommitteeCreateSerializer,
    CommitteeMembershipCreateSerializer,
    CommitteeMembershipSerializer,
    CommitteeMembershipUpdateSerializer,
    CommitteeSerializer,
    CommitteeUpdateSerializer,
    GovernanceChoicesSerializer,
    GovernanceMemberOptionSerializer,
    OrganizationMembershipDetailSerializer,
    OrganizationMembershipUpdateSerializer,
    OrganizationBootstrapResponseSerializer,
    OrganizationBootstrapSerializer,
    OrganizationSummaryResponseSerializer,
)


def _parse_bool_param(raw_value, *, default: bool = False) -> bool:
    if raw_value is None:
        return default
    if isinstance(raw_value, bool):
        return raw_value
    normalized = str(raw_value).strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    return default


class GovernanceScopeMixin:
    """
    Shared governance org-scope resolver.

    - Non-platform actors are constrained to active organization context and must
      satisfy registry governance capability for that org.
    - Platform admins can recover across orgs (with optional explicit org filter).
    """

    permission_classes = [permissions.IsAuthenticated]

    def _is_platform_admin(self) -> bool:
        return bool(is_platform_admin_user(getattr(self.request, "user", None)))

    def _read_request_value(self, key: str) -> str:
        query_value = str(self.request.query_params.get(key, "") or "").strip()
        if query_value:
            return query_value
        data = getattr(self.request, "data", None)
        if data is not None and hasattr(data, "get"):
            return str(data.get(key, "") or "").strip()
        return ""

    def _resolve_organization_by_id(self, organization_id: str, *, require_active: bool = True) -> Organization:
        queryset = Organization.objects.all()
        if require_active:
            queryset = queryset.filter(is_active=True)
        organization = queryset.filter(id=organization_id).first()
        if organization is None:
            raise NotFound("Organization was not found in governance scope.")
        return organization

    def _resolve_non_admin_active_organization(self) -> Organization:
        active_org_id = get_request_active_organization_id(self.request)
        if not active_org_id:
            raise ValidationError("Select an active organization before accessing governance resources.")

        organization = self._resolve_organization_by_id(active_org_id, require_active=True)
        if not can_manage_registry_governance(
            self.request.user,
            organization_id=organization.id,
            allow_membershipless_fallback=False,
        ):
            raise PermissionDenied("You do not have permission to manage governance resources for this organization.")
        return organization

    def _resolve_admin_target_organization(
        self,
        *,
        allow_payload: bool = False,
        require: bool = False,
    ) -> Organization | None:
        requested_org_id = str(self.request.query_params.get("organization_id", "") or "").strip()
        if not requested_org_id and allow_payload:
            requested_org_id = self._read_request_value("organization_id") or self._read_request_value("organization")

        if requested_org_id:
            return self._resolve_organization_by_id(requested_org_id, require_active=True)

        active_org_id = get_request_active_organization_id(self.request)
        if active_org_id:
            return self._resolve_organization_by_id(active_org_id, require_active=True)

        if require:
            raise ValidationError("Provide organization_id or select an active organization.")
        return None

    def _resolve_actor_organization(
        self,
        *,
        require: bool = True,
        allow_admin_payload: bool = False,
    ) -> Organization | None:
        if self._is_platform_admin():
            return self._resolve_admin_target_organization(
                allow_payload=allow_admin_payload,
                require=require,
            )
        return self._resolve_non_admin_active_organization()


def _resolve_bootstrap_organization_code(*, preferred_code: str, organization_name: str) -> str:
    base_code = slugify(preferred_code or organization_name).strip("-")
    if not base_code:
        base_code = f"organization-{uuid4().hex[:8]}"
    base_code = base_code[:80]
    candidate = base_code

    suffix = 2
    while Organization.objects.filter(code=candidate).exists():
        suffix_text = f"-{suffix}"
        candidate = f"{base_code[: max(1, 80 - len(suffix_text))]}{suffix_text}"
        suffix += 1
    return candidate


class OrganizationBootstrapAPIView(APIView):
    """
    Minimal first-organization bootstrap endpoint for org-less internal users.

    - Auth required
    - Applicant users are denied
    - Non-platform users can bootstrap only when they do not already have an
      active organization membership
    - Bootstrap assigns default organization admin membership_role
    """

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = OrganizationBootstrapSerializer

    @transaction.atomic
    def post(self, request):
        user = request.user
        if str(getattr(user, "user_type", "") or "").strip() == "applicant" and not is_platform_admin_user(user):
            raise PermissionDenied("Applicant accounts cannot bootstrap organizations.")

        has_active_membership = OrganizationMembership.objects.filter(
            user_id=user.id,
            is_active=True,
            organization__is_active=True,
        ).exists()
        if has_active_membership and not is_platform_admin_user(user):
            raise ValidationError(
                {
                    "detail": "Organization context already exists for this user. Use active-organization selection instead.",
                    "code": "ORGANIZATION_ALREADY_PROVISIONED",
                }
            )

        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        organization_name = str(serializer.validated_data["name"]).strip()
        preferred_code = str(serializer.validated_data.get("code", "") or "").strip()
        organization_code = _resolve_bootstrap_organization_code(
            preferred_code=preferred_code,
            organization_name=organization_name,
        )

        organization = Organization.objects.create(
            name=organization_name,
            code=organization_code,
            organization_type=serializer.validated_data.get("organization_type", "other"),
            is_active=True,
        )
        membership = OrganizationMembership.objects.create(
            user=user,
            organization=organization,
            membership_role="registry_admin",
            title=str(getattr(user, "department", "") or "").strip()[:120],
            is_active=True,
            is_default=True,
            joined_at=timezone.now(),
        )
        OrganizationMembership.objects.filter(
            user_id=user.id,
            is_default=True,
            is_active=True,
        ).exclude(
            id=membership.id
        ).update(
            is_default=False,
            updated_at=timezone.now(),
        )

        org_name = str(organization.name or "").strip()
        if org_name and str(getattr(user, "organization", "") or "").strip().lower() != org_name.lower():
            user.organization = org_name
            user.save(update_fields=["organization", "updated_at"])

        payload = {
            "status": "ok",
            "message": "Organization bootstrap completed.",
            "organization": organization,
            "membership": membership,
        }
        return Response(
            OrganizationBootstrapResponseSerializer(payload, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class OrganizationSummaryAPIView(GovernanceScopeMixin, APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        organization = self._resolve_actor_organization(require=True)
        if organization is None:  # pragma: no cover - guarded by require=True
            raise ValidationError("Organization context is required.")

        membership_context = get_user_organization_by_id(request.user, organization.id) or {}
        stats = {
            "members_total": OrganizationMembership.objects.filter(organization_id=organization.id).count(),
            "members_active": OrganizationMembership.objects.filter(
                organization_id=organization.id,
                is_active=True,
            ).count(),
            "committees_total": Committee.objects.filter(organization_id=organization.id).count(),
            "committees_active": Committee.objects.filter(
                organization_id=organization.id,
                is_active=True,
            ).count(),
            "committee_memberships_active": CommitteeMembership.objects.filter(
                committee__organization_id=organization.id,
                is_active=True,
            ).count(),
            "active_chairs": CommitteeMembership.objects.filter(
                committee__organization_id=organization.id,
                committee_role="chair",
                is_active=True,
            ).count(),
        }

        tenant_context = get_request_tenant_context(request)
        payload = {
            "organization": {
                "id": organization.id,
                "code": organization.code,
                "name": organization.name,
                "organization_type": organization.organization_type,
                "is_active": organization.is_active,
            },
            "actor": {
                "is_platform_admin": self._is_platform_admin(),
                "can_manage_registry": bool(
                    self._is_platform_admin()
                    or can_manage_registry_governance(
                        request.user,
                        organization_id=organization.id,
                        allow_membershipless_fallback=False,
                    )
                ),
                "active_membership_id": str(membership_context.get("membership_id", "") or ""),
                "active_membership_role": str(membership_context.get("membership_role", "") or ""),
            },
            "stats": stats,
            "active_organization_source": str(tenant_context.get("active_organization_source", "none")),
        }
        return Response(OrganizationSummaryResponseSerializer(payload).data, status=status.HTTP_200_OK)


class OrganizationMembershipViewSet(
    GovernanceScopeMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    queryset = OrganizationMembership.objects.select_related("organization", "user").all()
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = OrganizationMembershipDetailSerializer
    http_method_names = ["get", "patch", "head", "options"]

    def get_serializer_class(self):
        if self.action in {"partial_update", "update"}:
            return OrganizationMembershipUpdateSerializer
        return OrganizationMembershipDetailSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        search = str(self.request.query_params.get("search", "") or "").strip()
        membership_role = str(self.request.query_params.get("membership_role", "") or "").strip()
        if search:
            queryset = queryset.filter(
                Q(user__email__icontains=search)
                | Q(user__first_name__icontains=search)
                | Q(user__last_name__icontains=search)
                | Q(title__icontains=search)
            )
        if membership_role:
            queryset = queryset.filter(membership_role__iexact=membership_role)

        raw_is_active = self.request.query_params.get("is_active")
        if raw_is_active is not None:
            queryset = queryset.filter(is_active=_parse_bool_param(raw_is_active))

        raw_is_default = self.request.query_params.get("is_default")
        if raw_is_default is not None:
            queryset = queryset.filter(is_default=_parse_bool_param(raw_is_default))

        if self._is_platform_admin():
            scoped_org = self._resolve_admin_target_organization(require=False)
            if scoped_org is not None:
                queryset = queryset.filter(organization_id=scoped_org.id)
            return queryset.order_by("-is_default", "organization__name", "created_at")

        scoped_org = self._resolve_non_admin_active_organization()
        return queryset.filter(organization_id=scoped_org.id).order_by("-is_default", "created_at")

    @transaction.atomic
    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        if bool(serializer.validated_data.get("is_default")):
            OrganizationMembership.objects.select_for_update().filter(
                user_id=instance.user_id,
                is_active=True,
                is_default=True,
            ).exclude(pk=instance.pk).update(
                is_default=False,
                updated_at=timezone.now(),
            )

        updated = serializer.save()
        changed_fields: list[str] = []
        if not updated.is_active:
            if updated.left_at is None:
                updated.left_at = timezone.now()
                changed_fields.append("left_at")
            if updated.is_default:
                updated.is_default = False
                changed_fields.append("is_default")
        if changed_fields:
            updated.save(update_fields=[*changed_fields, "updated_at"])

        output = OrganizationMembershipDetailSerializer(updated, context=self.get_serializer_context())
        return Response(output.data, status=status.HTTP_200_OK)


class CommitteeViewSet(
    GovernanceScopeMixin,
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    queryset = Committee.objects.select_related("organization", "created_by").all()
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = CommitteeSerializer
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_serializer_class(self):
        if self.action == "create":
            return CommitteeCreateSerializer
        if self.action in {"partial_update", "update"}:
            return CommitteeUpdateSerializer
        return CommitteeSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        search = str(self.request.query_params.get("search", "") or "").strip()
        committee_type = str(self.request.query_params.get("committee_type", "") or "").strip()
        if search:
            queryset = queryset.filter(Q(name__icontains=search) | Q(code__icontains=search))
        if committee_type:
            queryset = queryset.filter(committee_type=committee_type)
        raw_is_active = self.request.query_params.get("is_active")
        if raw_is_active is not None:
            queryset = queryset.filter(is_active=_parse_bool_param(raw_is_active))

        if self._is_platform_admin():
            scoped_org = self._resolve_admin_target_organization(require=False)
            if scoped_org is not None:
                queryset = queryset.filter(organization_id=scoped_org.id)
            return queryset.order_by("organization__name", "name")

        scoped_org = self._resolve_non_admin_active_organization()
        return queryset.filter(organization_id=scoped_org.id).order_by("name")

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = request.user

        if self._is_platform_admin():
            requested_org = serializer.validated_data.get("organization")
            organization = requested_org or self._resolve_admin_target_organization(require=True)
            if organization is None:  # pragma: no cover - guarded by require=True
                raise ValidationError("Organization context is required.")
        else:
            organization = self._resolve_non_admin_active_organization()
            requested_org = serializer.validated_data.get("organization")
            if requested_org is not None and requested_org.id != organization.id:
                raise PermissionDenied("You cannot create committees for another organization.")

        code = str(serializer.validated_data.get("code", "") or "").strip()
        name = str(serializer.validated_data.get("name", "") or "").strip()
        if Committee.objects.filter(organization_id=organization.id, code=code).exists():
            raise ValidationError({"code": "Committee code must be unique within the organization."})
        if Committee.objects.filter(organization_id=organization.id, name=name).exists():
            raise ValidationError({"name": "Committee name must be unique within the organization."})

        committee = serializer.save(organization=organization, created_by=user)
        output = CommitteeSerializer(committee, context=self.get_serializer_context())
        headers = self.get_success_headers(output.data)
        return Response(output.data, status=status.HTTP_201_CREATED, headers=headers)

    @transaction.atomic
    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        committee = serializer.save()
        output = CommitteeSerializer(committee, context=self.get_serializer_context())
        return Response(output.data, status=status.HTTP_200_OK)

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        committee = self.get_object()
        if not committee.is_active:
            return Response(status=status.HTTP_204_NO_CONTENT)

        now = timezone.now()
        committee.is_active = False
        committee.save(update_fields=["is_active", "updated_at"])
        CommitteeMembership.objects.filter(committee_id=committee.id, is_active=True).update(
            is_active=False,
            updated_at=now,
        )
        CommitteeMembership.objects.filter(
            committee_id=committee.id,
            left_at__isnull=True,
        ).update(left_at=now, updated_at=now)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"], url_path="reassign-chair")
    @transaction.atomic
    def reassign_chair(self, request, pk=None):
        committee = self.get_object()
        serializer = CommitteeChairReassignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated = serializer.validated_data

        previous_chair = (
            CommitteeMembership.objects.select_related("user")
            .filter(
                committee_id=committee.id,
                committee_role="chair",
                is_active=True,
            )
            .first()
        )

        target_membership_id = validated.get("target_committee_membership_id")
        target_user_id = validated.get("target_user_id")
        org_membership_id = validated.get("organization_membership_id")
        can_vote = bool(validated.get("can_vote", True))

        target_membership = None
        target_user = None
        organization_membership = None

        if target_membership_id:
            target_membership = (
                CommitteeMembership.objects.select_related("user", "organization_membership")
                .filter(
                    id=target_membership_id,
                    committee_id=committee.id,
                )
                .first()
            )
            if target_membership is None:
                raise ValidationError("Target committee membership is invalid for this committee.")
            target_user = target_membership.user
            organization_membership = target_membership.organization_membership
        else:
            target_user = User.objects.filter(id=target_user_id).first()
            if target_user is None:
                raise ValidationError("Target user was not found.")
            if org_membership_id:
                organization_membership = (
                    OrganizationMembership.objects.select_for_update()
                    .filter(
                        id=org_membership_id,
                        user_id=target_user.id,
                        organization_id=committee.organization_id,
                        is_active=True,
                    )
                    .first()
                )
                if organization_membership is None:
                    raise ValidationError(
                        "organization_membership_id must reference an active membership for the target user in this committee organization."
                    )

        promoted = CommitteeMembership.assign_active_chair(
            committee=committee,
            user=target_user,
            organization_membership=organization_membership,
            can_vote=can_vote,
        )
        promoted = CommitteeMembership.objects.select_related("user").get(pk=promoted.pk)

        payload = {
            "committee_id": str(committee.id),
            "previous_chair": (
                {
                    "membership_id": str(previous_chair.id),
                    "user_id": str(previous_chair.user_id),
                    "user_email": str(previous_chair.user.email or ""),
                }
                if previous_chair is not None
                else None
            ),
            "new_chair": {
                "membership_id": str(promoted.id),
                "user_id": str(promoted.user_id),
                "user_email": str(promoted.user.email or ""),
                "committee_role": str(promoted.committee_role),
            },
            "changed_at": timezone.now().isoformat(),
        }
        return Response(payload, status=status.HTTP_200_OK)


class CommitteeMembershipViewSet(
    GovernanceScopeMixin,
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    queryset = CommitteeMembership.objects.select_related(
        "committee",
        "committee__organization",
        "user",
        "organization_membership",
    ).all()
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = CommitteeMembershipSerializer
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_serializer_class(self):
        if self.action == "create":
            return CommitteeMembershipCreateSerializer
        if self.action in {"partial_update", "update"}:
            return CommitteeMembershipUpdateSerializer
        return CommitteeMembershipSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        committee_id = str(self.request.query_params.get("committee", "") or "").strip()
        if committee_id:
            queryset = queryset.filter(committee_id=committee_id)

        role = str(self.request.query_params.get("committee_role", "") or "").strip()
        if role:
            queryset = queryset.filter(committee_role=role)

        raw_is_active = self.request.query_params.get("is_active")
        if raw_is_active is not None:
            queryset = queryset.filter(is_active=_parse_bool_param(raw_is_active))

        if self._is_platform_admin():
            scoped_org = self._resolve_admin_target_organization(require=False)
            if scoped_org is not None:
                queryset = queryset.filter(committee__organization_id=scoped_org.id)
            return queryset.order_by("committee__name", "committee_role", "created_at")

        scoped_org = self._resolve_non_admin_active_organization()
        return queryset.filter(committee__organization_id=scoped_org.id).order_by(
            "committee__name",
            "committee_role",
            "created_at",
        )

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated = serializer.validated_data
        committee: Committee = validated["committee"]

        if self._is_platform_admin():
            scoped_org = None
        else:
            scoped_org = self._resolve_non_admin_active_organization()
            if str(committee.organization_id) != str(scoped_org.id):
                raise PermissionDenied("You cannot manage committee memberships outside your active organization.")

        user = validated["user"]
        organization_membership = validated.get("organization_membership")
        if organization_membership is None:
            organization_membership = (
                OrganizationMembership.objects.select_for_update()
                .filter(
                    user_id=user.id,
                    organization_id=committee.organization_id,
                    is_active=True,
                )
                .order_by("-is_default", "created_at")
                .first()
            )
            if organization_membership is None:
                raise ValidationError(
                    {"organization_membership": "Active organization membership is required for committee assignment."}
                )

        membership = serializer.save(organization_membership=organization_membership)
        if membership.joined_at is None:
            membership.joined_at = timezone.now()
            membership.save(update_fields=["joined_at", "updated_at"])

        output = CommitteeMembershipSerializer(membership, context=self.get_serializer_context())
        headers = self.get_success_headers(output.data)
        return Response(output.data, status=status.HTTP_201_CREATED, headers=headers)

    @transaction.atomic
    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        membership = serializer.save()

        changed_fields: list[str] = []
        if not membership.is_active and membership.left_at is None:
            membership.left_at = timezone.now()
            changed_fields.append("left_at")
        if changed_fields:
            membership.save(update_fields=[*changed_fields, "updated_at"])

        output = CommitteeMembershipSerializer(membership, context=self.get_serializer_context())
        return Response(output.data, status=status.HTTP_200_OK)

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        membership = self.get_object()
        if not membership.is_active and membership.left_at is not None:
            return Response(status=status.HTTP_204_NO_CONTENT)

        membership.is_active = False
        if membership.left_at is None:
            membership.left_at = timezone.now()
        membership.save(update_fields=["is_active", "left_at", "updated_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class GovernanceMemberOptionsAPIView(GovernanceScopeMixin, APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        organization = self._resolve_actor_organization(require=True)
        if organization is None:  # pragma: no cover - guarded by require=True
            raise ValidationError("Organization context is required.")

        active_only = _parse_bool_param(request.query_params.get("active_only"), default=True)
        queryset = OrganizationMembership.objects.select_related("user").filter(organization_id=organization.id)
        if active_only:
            queryset = queryset.filter(is_active=True)
        queryset = queryset.order_by("-is_default", "user__email")

        payload = [
            {
                "organization_membership_id": membership.id,
                "user_id": membership.user_id,
                "user_email": str(membership.user.email or ""),
                "user_full_name": str(membership.user.get_full_name() or ""),
                "membership_role": str(membership.membership_role or ""),
                "title": str(membership.title or ""),
                "is_active": bool(membership.is_active),
                "is_default": bool(membership.is_default),
            }
            for membership in queryset
        ]
        return Response(
            GovernanceMemberOptionSerializer(payload, many=True).data,
            status=status.HTTP_200_OK,
        )


class GovernanceChoicesAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        payload = {
            "organization_types": [
                {"value": value, "label": label}
                for value, label in Organization.ORGANIZATION_TYPE_CHOICES
            ],
            "committee_types": [
                {"value": value, "label": label}
                for value, label in Committee.COMMITTEE_TYPE_CHOICES
            ],
            "committee_roles": [
                {"value": value, "label": label}
                for value, label in CommitteeMembership.COMMITTEE_ROLE_CHOICES
            ],
        }
        return Response(GovernanceChoicesSerializer(payload).data, status=status.HTTP_200_OK)
