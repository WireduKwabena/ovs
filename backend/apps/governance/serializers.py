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
