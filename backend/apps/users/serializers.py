"""User management serializers for profiles, organization context, and user data."""

from __future__ import annotations

from typing import Any

from rest_framework import serializers
from apps.users.models import User, UserProfile
from apps.core.authz import get_user_capabilities, get_user_roles, is_internal_operator

USER_TYPE_CHOICES = User.USER_TYPE_CHOICES

class UserSerializer(serializers.ModelSerializer):
    """Serializer for regular users (applicants)"""
    full_name = serializers.CharField(source='get_full_name', read_only=True)
    profile = serializers.SerializerMethodField(read_only=True)
    roles = serializers.SerializerMethodField(read_only=True)
    capabilities = serializers.SerializerMethodField(read_only=True)
    is_internal_operator = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = User
        fields = [
            'id', 'email', 'first_name', 'last_name', 'full_name', 'phone_number',
            'organization', 'department', 'user_type', 'is_active', 'is_staff', 'is_superuser', 'created_at',
            'profile', 'roles', 'capabilities', 'is_internal_operator'
        ]
        read_only_fields = ['id', 'created_at', 'user_type', 'is_active', 'is_staff', 'is_superuser']

    def get_profile(self, obj) -> dict[str, Any] | None:
        profile = getattr(obj, "profile", None)
        if profile is None:
            return None
        return UserProfileSerializer(profile, context=self.context).data

    def get_roles(self, obj) -> list[str]:
        return sorted(get_user_roles(obj))

    def get_capabilities(self, obj) -> list[str]:
        return sorted(get_user_capabilities(obj))

    def get_is_internal_operator(self, obj) -> bool:
        return bool(is_internal_operator(obj))



class AdminUserSerializer(serializers.ModelSerializer):
    """Serializer for admin users"""
    role_display = serializers.CharField(source='get_user_type_display', read_only=True)
    full_name = serializers.CharField(source='get_full_name', read_only=True)
    profile = serializers.SerializerMethodField(read_only=True)
    roles = serializers.SerializerMethodField(read_only=True)
    capabilities = serializers.SerializerMethodField(read_only=True)
    is_internal_operator = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = User
        fields = [
            'id', 'email', 'first_name', 'last_name', 'full_name', 'phone_number',
            'organization', 'department', 'user_type', 'role_display', 'is_active', 'is_staff', 'is_superuser',
            'created_at', 'profile', 'roles', 'capabilities', 'is_internal_operator'
        ]
        read_only_fields = ['id', 'created_at', 'user_type', 'is_active', 'is_staff', 'is_superuser']

    def get_profile(self, obj) -> dict[str, Any] | None:
        profile = getattr(obj, "profile", None)
        if profile is None:
            return None
        return UserProfileSerializer(profile, context=self.context).data

    def get_roles(self, obj) -> list[str]:
        return sorted(get_user_roles(obj))

    def get_capabilities(self, obj) -> list[str]:
        return sorted(get_user_capabilities(obj))

    def get_is_internal_operator(self, obj) -> bool:
        return bool(is_internal_operator(obj))


class UserProfileSerializer(serializers.ModelSerializer):
    """Read serializer for extended user profile fields."""
    avatar_url = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = UserProfile
        fields = [
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
            "profile_completion_percentage",
            "avatar_url",
        ]
        read_only_fields = ["profile_completion_percentage", "avatar_url"]

    def get_avatar_url(self, obj):
        if not obj.avatar:
            return ""
        request = self.context.get("request")
        if request is not None:
            return request.build_absolute_uri(obj.avatar.url)
        return obj.avatar.url


class ProfileUpdateSerializer(serializers.Serializer):
    """Serializer for user + extended profile update payload."""
    email = serializers.EmailField(required=False)
    first_name = serializers.CharField(required=False, allow_blank=True, max_length=150)
    last_name = serializers.CharField(required=False, allow_blank=True, max_length=150)
    phone_number = serializers.CharField(required=False, allow_blank=True, max_length=20)
    organization = serializers.CharField(required=False, allow_blank=True, max_length=200)
    department = serializers.CharField(required=False, allow_blank=True, max_length=100)

    date_of_birth = serializers.DateField(required=False, allow_null=True)
    nationality = serializers.CharField(required=False, allow_blank=True, max_length=100)
    address = serializers.CharField(required=False, allow_blank=True)
    city = serializers.CharField(required=False, allow_blank=True, max_length=100)
    country = serializers.CharField(required=False, allow_blank=True, max_length=100)
    postal_code = serializers.CharField(required=False, allow_blank=True, max_length=20)
    current_job_title = serializers.CharField(required=False, allow_blank=True, max_length=200)
    years_of_experience = serializers.IntegerField(required=False, allow_null=True, min_value=0)
    linkedin_url = serializers.URLField(required=False, allow_blank=True)
    bio = serializers.CharField(required=False, allow_blank=True, max_length=500)

    def validate_email(self, value: str) -> str:
        normalized = str(value or "").strip().lower()
        request = self.context.get("request")
        current_user_id = getattr(getattr(request, "user", None), "pk", None)

        existing_user_qs = User.all_objects.filter(email__iexact=normalized)
        if current_user_id is not None:
            existing_user_qs = existing_user_qs.exclude(pk=current_user_id)

        if existing_user_qs.exists():
            raise serializers.ValidationError("A user with that email already exists.")
        return normalized


class OrganizationSummarySerializer(serializers.Serializer):
    id = serializers.CharField()
    code = serializers.CharField()
    name = serializers.CharField()
    organization_type = serializers.CharField()


class OrganizationMembershipContextSerializer(serializers.Serializer):
    id = serializers.CharField()
    organization_id = serializers.CharField()
    organization_code = serializers.CharField()
    organization_name = serializers.CharField()
    organization_type = serializers.CharField()
    title = serializers.CharField(allow_blank=True)
    membership_role = serializers.CharField(allow_blank=True)
    is_default = serializers.BooleanField()
    is_active = serializers.BooleanField()
    joined_at = serializers.CharField(allow_null=True, required=False)
    left_at = serializers.CharField(allow_null=True, required=False)


class CommitteeContextSerializer(serializers.Serializer):
    id = serializers.CharField()
    committee_id = serializers.CharField()
    committee_code = serializers.CharField()
    committee_name = serializers.CharField()
    committee_type = serializers.CharField()
    organization_id = serializers.CharField()
    organization_code = serializers.CharField()
    organization_name = serializers.CharField()
    committee_role = serializers.CharField()
    can_vote = serializers.BooleanField()
    joined_at = serializers.CharField(allow_null=True, required=False)
    left_at = serializers.CharField(allow_null=True, required=False)


class ActiveOrganizationSelectionSerializer(serializers.Serializer):
    organization_id = serializers.UUIDField(required=False, allow_null=True)
    clear = serializers.BooleanField(required=False, default=False)

    def validate(self, attrs):
        clear = bool(attrs.get("clear", False))
        organization_id = attrs.get("organization_id")
        if clear:
            return attrs
        if organization_id is None:
            raise serializers.ValidationError("organization_id is required unless clear=true.")
        return attrs


class ActiveOrganizationSelectionResponseSerializer(serializers.Serializer):
    message = serializers.CharField()
    active_organization = OrganizationSummarySerializer(allow_null=True)
    active_organization_source = serializers.CharField()
    invalid_requested_organization_id = serializers.CharField(required=False, allow_blank=True)


class ProfileResponseSerializer(serializers.Serializer):
    user = serializers.DictField()
    user_type = serializers.ChoiceField(choices=USER_TYPE_CHOICES)
    roles = serializers.ListField(child=serializers.CharField(), required=False)
    capabilities = serializers.ListField(child=serializers.CharField(), required=False)
    is_internal_operator = serializers.BooleanField(required=False)
    organizations = OrganizationSummarySerializer(many=True, required=False)
    organization_memberships = OrganizationMembershipContextSerializer(many=True, required=False)
    committees = CommitteeContextSerializer(many=True, required=False)
    active_organization = OrganizationSummarySerializer(allow_null=True, required=False)
    active_organization_source = serializers.CharField(required=False)
    invalid_requested_organization_id = serializers.CharField(required=False, allow_blank=True)









