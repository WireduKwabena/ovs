import re

from rest_framework import serializers

from .models import Committee, CommitteeMembership, Organization, OrganizationMembership


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = [
            "id",
            "code",
            "name",
            "organization_type",
            "is_active",
            "metadata",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class OrganizationMembershipSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source="user.email", read_only=True)
    organization_name = serializers.CharField(source="organization.name", read_only=True)

    class Meta:
        model = OrganizationMembership
        fields = [
            "id",
            "user",
            "user_email",
            "organization",
            "organization_name",
            "title",
            "membership_role",
            "is_active",
            "is_default",
            "joined_at",
            "left_at",
            "metadata",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "user_email", "organization_name"]


class CommitteeSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    created_by_email = serializers.EmailField(source="created_by.email", read_only=True)

    class Meta:
        model = Committee
        fields = [
            "id",
            "organization",
            "organization_name",
            "code",
            "name",
            "committee_type",
            "description",
            "is_active",
            "created_by",
            "created_by_email",
            "metadata",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "organization_name", "created_by_email"]


class CommitteeMembershipSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source="user.email", read_only=True)
    committee_name = serializers.CharField(source="committee.name", read_only=True)
    organization_name = serializers.CharField(source="committee.organization.name", read_only=True)

    class Meta:
        model = CommitteeMembership
        fields = [
            "id",
            "committee",
            "committee_name",
            "organization_name",
            "user",
            "user_email",
            "organization_membership",
            "committee_role",
            "can_vote",
            "is_active",
            "joined_at",
            "left_at",
            "metadata",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
            "user_email",
            "committee_name",
            "organization_name",
        ]

    def validate(self, attrs):
        instance = getattr(self, "instance", None)

        committee = attrs.get("committee")
        if committee is None and instance is not None:
            committee = instance.committee

        user = attrs.get("user")
        if user is None and instance is not None:
            user = instance.user

        organization_membership = attrs.get("organization_membership")
        if organization_membership is None and instance is not None:
            organization_membership = instance.organization_membership

        committee_role = attrs.get("committee_role")
        if committee_role is None and instance is not None:
            committee_role = instance.committee_role

        is_active = attrs.get("is_active")
        if is_active is None:
            is_active = instance.is_active if instance is not None else True

        can_vote = attrs.get("can_vote")
        if can_vote is None:
            can_vote = instance.can_vote if instance is not None else True

        if committee_role == "observer" and bool(can_vote):
            raise serializers.ValidationError(
                {"can_vote": "Observer memberships must be non-voting."}
            )

        if organization_membership is not None:
            if user is not None and organization_membership.user_id != user.id:
                raise serializers.ValidationError(
                    {
                        "organization_membership": (
                            "Organization membership user must match committee membership user."
                        )
                    }
                )
            if committee is not None and organization_membership.organization_id != committee.organization_id:
                raise serializers.ValidationError(
                    {
                        "organization_membership": (
                            "Organization membership must belong to the same organization as the committee."
                        )
                    }
                )
            if not organization_membership.is_active:
                raise serializers.ValidationError(
                    {"organization_membership": "Organization membership must be active."}
                )

        if committee is not None and committee_role == "chair" and bool(is_active):
            chair_qs = CommitteeMembership.objects.filter(
                committee=committee,
                committee_role="chair",
                is_active=True,
            )
            if instance is not None:
                chair_qs = chair_qs.exclude(pk=instance.pk)
            if chair_qs.exists():
                raise serializers.ValidationError(
                    {
                        "committee_role": (
                            "This committee already has an active chair. "
                            "Use reassignment flow to promote a new chair safely."
                        )
                    }
                )

        return attrs


_SAFE_MEMBERSHIP_ROLE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _-]{0,79}$")


class MembershipRoleValidationMixin:
    """
    Keep ``membership_role`` backward-compatible while blocking unsafe edits.

    Existing persisted values remain valid unless edited. New edits are constrained
    to a safe alphanumeric/underscore/hyphen/space subset.
    """

    def validate_membership_role(self, value):
        normalized = str(value or "").strip()
        if not normalized:
            return ""
        if not _SAFE_MEMBERSHIP_ROLE_RE.fullmatch(normalized):
            raise serializers.ValidationError(
                "Use only letters, numbers, spaces, underscores, and hyphens."
            )
        return normalized


class OrganizationMembershipDetailSerializer(OrganizationMembershipSerializer):
    user_full_name = serializers.SerializerMethodField(read_only=True)

    class Meta(OrganizationMembershipSerializer.Meta):
        fields = [
            *OrganizationMembershipSerializer.Meta.fields,
            "user_full_name",
        ]
        read_only_fields = [
            *OrganizationMembershipSerializer.Meta.read_only_fields,
            "user_full_name",
        ]

    def get_user_full_name(self, obj) -> str:
        user = getattr(obj, "user", None)
        if user is None:
            return ""
        if hasattr(user, "get_full_name"):
            return str(user.get_full_name() or "").strip()
        return str(getattr(user, "email", "") or "").strip()


class OrganizationMembershipUpdateSerializer(MembershipRoleValidationMixin, serializers.ModelSerializer):
    class Meta:
        model = OrganizationMembership
        fields = [
            "title",
            "membership_role",
            "is_active",
            "is_default",
            "left_at",
            "metadata",
        ]

    def validate(self, attrs):
        instance = getattr(self, "instance", None)

        is_active = attrs.get("is_active")
        if is_active is None and instance is not None:
            is_active = instance.is_active

        is_default = attrs.get("is_default")
        if is_default is None and instance is not None:
            is_default = instance.is_default

        left_at = attrs.get("left_at")
        if left_at is None and instance is not None:
            left_at = instance.left_at

        if bool(is_default) and not bool(is_active):
            raise serializers.ValidationError(
                {"is_default": "Default membership must remain active."}
            )
        if left_at is not None and bool(is_active):
            raise serializers.ValidationError(
                {"left_at": "left_at requires inactive membership."}
            )
        return attrs


class CommitteeCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Committee
        fields = [
            "organization",
            "code",
            "name",
            "committee_type",
            "description",
            "is_active",
            "metadata",
        ]
        extra_kwargs = {
            "organization": {"required": False},
        }
        validators = []


class CommitteeUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Committee
        fields = [
            "code",
            "name",
            "committee_type",
            "description",
            "is_active",
            "metadata",
        ]


class CommitteeMembershipCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CommitteeMembership
        fields = [
            "committee",
            "user",
            "organization_membership",
            "committee_role",
            "can_vote",
            "is_active",
            "metadata",
        ]

    def validate(self, attrs):
        attrs = CommitteeMembershipSerializer.validate(self, attrs)
        if attrs.get("committee_role") == "chair":
            raise serializers.ValidationError(
                {
                    "committee_role": (
                        "Assigning chair through generic membership create is not allowed. "
                        "Use committee chair reassignment."
                    )
                }
            )
        return attrs


class CommitteeMembershipUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CommitteeMembership
        fields = [
            "committee_role",
            "can_vote",
            "is_active",
            "left_at",
            "metadata",
        ]

    def validate(self, attrs):
        instance = getattr(self, "instance", None)
        if instance is None:
            return attrs

        merged = {
            "committee": getattr(instance, "committee", None),
            "user": getattr(instance, "user", None),
            "organization_membership": attrs.get(
                "organization_membership",
                getattr(instance, "organization_membership", None),
            ),
            "committee_role": attrs.get("committee_role", instance.committee_role),
            "can_vote": attrs.get("can_vote", instance.can_vote),
            "is_active": attrs.get("is_active", instance.is_active),
            "left_at": attrs.get("left_at", instance.left_at),
        }
        CommitteeMembershipSerializer.validate(self, merged)

        if merged.get("committee_role") == "chair":
            raise serializers.ValidationError(
                {
                    "committee_role": (
                        "Chair assignment is restricted to dedicated reassignment flow."
                    )
                }
            )

        if merged.get("left_at") is not None and bool(merged.get("is_active")):
            raise serializers.ValidationError(
                {"left_at": "left_at requires inactive committee membership."}
            )
        return attrs


class GovernanceSummaryOrganizationSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    code = serializers.CharField()
    name = serializers.CharField()
    organization_type = serializers.CharField()
    is_active = serializers.BooleanField()


class GovernanceSummaryActorSerializer(serializers.Serializer):
    is_platform_admin = serializers.BooleanField()
    can_manage_registry = serializers.BooleanField()
    active_membership_id = serializers.CharField(allow_blank=True)
    active_membership_role = serializers.CharField(allow_blank=True)


class GovernanceSummaryStatsSerializer(serializers.Serializer):
    members_total = serializers.IntegerField(min_value=0)
    members_active = serializers.IntegerField(min_value=0)
    committees_total = serializers.IntegerField(min_value=0)
    committees_active = serializers.IntegerField(min_value=0)
    committee_memberships_active = serializers.IntegerField(min_value=0)
    active_chairs = serializers.IntegerField(min_value=0)


class OrganizationSummaryResponseSerializer(serializers.Serializer):
    organization = GovernanceSummaryOrganizationSerializer()
    actor = GovernanceSummaryActorSerializer()
    stats = GovernanceSummaryStatsSerializer()
    active_organization_source = serializers.CharField()


class PlatformOrganizationSubscriptionSummarySerializer(serializers.Serializer):
    id = serializers.UUIDField()
    source = serializers.ChoiceField(choices=("active", "latest"))
    provider = serializers.CharField()
    status = serializers.CharField()
    payment_status = serializers.CharField(allow_blank=True)
    plan_id = serializers.CharField()
    plan_name = serializers.CharField()
    billing_cycle = serializers.CharField()
    payment_method = serializers.CharField(allow_blank=True)
    amount_usd = serializers.DecimalField(max_digits=10, decimal_places=2)
    current_period_end = serializers.DateTimeField(allow_null=True)
    cancel_at_period_end = serializers.BooleanField()
    updated_at = serializers.DateTimeField()


class PlatformOrganizationOversightSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    code = serializers.CharField()
    name = serializers.CharField()
    organization_type = serializers.CharField()
    is_active = serializers.BooleanField()
    active_member_count = serializers.IntegerField(min_value=0)
    subscription = PlatformOrganizationSubscriptionSummarySerializer(allow_null=True)


class PlatformOrganizationOversightListResponseSerializer(serializers.Serializer):
    count = serializers.IntegerField(min_value=0)
    results = PlatformOrganizationOversightSerializer(many=True)


class PlatformOrganizationStatusUpdateSerializer(serializers.Serializer):
    is_active = serializers.BooleanField()


class GovernanceMemberOptionSerializer(serializers.Serializer):
    organization_membership_id = serializers.UUIDField()
    user_id = serializers.UUIDField()
    user_email = serializers.EmailField()
    user_full_name = serializers.CharField()
    membership_role = serializers.CharField(allow_blank=True)
    title = serializers.CharField(allow_blank=True)
    is_active = serializers.BooleanField()
    is_default = serializers.BooleanField()


class GovernanceChoicesSerializer(serializers.Serializer):
    organization_types = serializers.ListField(child=serializers.DictField())
    committee_types = serializers.ListField(child=serializers.DictField())
    committee_roles = serializers.ListField(child=serializers.DictField())


class CommitteeChairReassignSerializer(serializers.Serializer):
    target_committee_membership_id = serializers.UUIDField(required=False)
    target_user_id = serializers.UUIDField(required=False)
    organization_membership_id = serializers.UUIDField(required=False)
    can_vote = serializers.BooleanField(required=False, default=True)
    reason_note = serializers.CharField(required=False, allow_blank=True, max_length=500)

    def validate(self, attrs):
        target_membership_id = attrs.get("target_committee_membership_id")
        target_user_id = attrs.get("target_user_id")
        if bool(target_membership_id) == bool(target_user_id):
            raise serializers.ValidationError(
                "Provide exactly one of target_committee_membership_id or target_user_id."
            )
        return attrs


class OrganizationBootstrapSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200)
    code = serializers.SlugField(required=False, allow_blank=True, max_length=80)
    organization_type = serializers.ChoiceField(
        required=False,
        choices=Organization.ORGANIZATION_TYPE_CHOICES,
        default="other",
    )


class OrganizationBootstrapResponseSerializer(serializers.Serializer):
    status = serializers.CharField()
    message = serializers.CharField()
    organization = OrganizationSerializer()
    membership = OrganizationMembershipDetailSerializer()
