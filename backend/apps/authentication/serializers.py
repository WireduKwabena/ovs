from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth import authenticate
from apps.users.models import User
from apps.users.serializers import UserSerializer, AdminUserSerializer
from apps.core.authz import ROLE_ADMIN, has_role

USER_TYPE_CHOICES = User.USER_TYPE_CHOICES


class UserRegistrationSerializer(serializers.ModelSerializer):
    """Serializer for firm registration"""
    password = serializers.CharField(
        write_only=True, 
        required=True, 
        validators=[validate_password]
    )
    password_confirm = serializers.CharField(write_only=True, required=True)
    # Legacy field retained for backward-compatible payload parsing; no longer used for registration decisions.
    subscription_reference = serializers.CharField(write_only=True, required=False, allow_blank=True)
    # Token is mandatory for organization-scoped onboarding.
    onboarding_token = serializers.CharField(write_only=True, required=True, allow_blank=False)
    # Legacy organization input is ignored to prevent manual org assignment at registration.
    organization = serializers.CharField(write_only=True, required=False, allow_blank=True, max_length=200)
    
    class Meta:
        model = User
        fields = [
            'email', 'password', 'password_confirm', 
            'first_name', 'last_name', 'phone_number', 'organization', 'department', 'subscription_reference', 'onboarding_token'
        ]
    
    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({
                "password": "Password fields didn't match."
            })
        return attrs
    
    def create(self, validated_data):
        validated_data.pop('password_confirm')
        validated_data.pop('subscription_reference', None)
        validated_data.pop('onboarding_token', None)
        validated_data.pop('organization', None)
        # Keep legacy identity default for backward compatibility.
        # Governance authority is resolved through roles/capabilities/memberships.
        validated_data.setdefault("user_type", "internal")
        user = User.objects.create_user(**validated_data)
        return user

class TokenPairSerializer(serializers.Serializer):
    access = serializers.CharField()
    refresh = serializers.CharField()


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')

        if email and password:
            user = authenticate(request=self.context.get('request'), email=email, password=password)
            if not user:
                raise serializers.ValidationError('Invalid credentials.', code='authorization')
        else:
            raise serializers.ValidationError('Email and password are required.', code='authorization')

        attrs['user'] = user
        return attrs

class LogoutRequestSerializer(serializers.Serializer):
    refresh = serializers.CharField(required=True)

class UserAuthResponseSerializer(serializers.Serializer):
    user = UserSerializer()
    tokens = TokenPairSerializer()
    user_type = serializers.ChoiceField(choices=USER_TYPE_CHOICES)
    backup_codes = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True,
    )


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

class PasswordResetConfirmSerializer(serializers.Serializer):
    new_password = serializers.CharField(min_length=10, write_only=True, style={'input_type': 'password'})
    token = serializers.CharField(write_only=True)
    new_password_confirm = serializers.CharField(min_length=10, write_only=True, style={'input_type': 'password'})

    def validate(self, data):
        if data['new_password'] != data['new_password_confirm']:
            raise serializers.ValidationError("New password and confirmation do not match.")
        from django.contrib.auth.password_validation import validate_password
        validate_password(data['new_password'])
        return data


class AdminLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')

        if email and password:
            user = authenticate(request=self.context.get('request'), email=email, password=password)
            if not user or not has_role(user, ROLE_ADMIN):
                raise serializers.ValidationError('Invalid credentials or not an admin user.', code='authorization')
        else:
            raise serializers.ValidationError('Email and password are required.', code='authorization')

        attrs['user'] = user
        return attrs


class AdminAuthResponseSerializer(serializers.Serializer):
    user = AdminUserSerializer()
    tokens = TokenPairSerializer()
    user_type = serializers.ChoiceField(choices=USER_TYPE_CHOICES)
    backup_codes = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True,
    )


class RegisterResponseSerializer(serializers.Serializer):
    user = UserSerializer()
    user_type = serializers.ChoiceField(choices=USER_TYPE_CHOICES)
    message = serializers.CharField()


class OrganizationAdminRegistrationSerializer(serializers.Serializer):
    """
    Public bootstrap registration for a brand-new organization administrator.

    Existing member onboarding stays token-gated through ``/auth/register/``.
    """

    ORGANIZATION_TYPE_CHOICES = (
        ("ministry", "Ministry"),
        ("agency", "Agency"),
        ("committee_secretariat", "Committee Secretariat"),
        ("executive_office", "Executive Office"),
        ("other", "Other"),
    )

    email = serializers.EmailField(required=True)
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True, required=True)
    first_name = serializers.CharField(required=True, max_length=150)
    last_name = serializers.CharField(required=True, max_length=150)
    phone_number = serializers.CharField(required=False, allow_blank=True, max_length=20)
    department = serializers.CharField(required=False, allow_blank=True, max_length=100)

    organization_name = serializers.CharField(required=True, max_length=200)
    organization_code = serializers.SlugField(required=False, allow_blank=True, max_length=80)
    organization_type = serializers.ChoiceField(
        required=False,
        choices=ORGANIZATION_TYPE_CHOICES,
        default="agency",
    )

    def validate_email(self, value):
        normalized = str(value or "").strip().lower()
        if User.objects.filter(email__iexact=normalized).exists():
            raise serializers.ValidationError("A user with that email already exists.")
        return normalized

    def validate_organization_name(self, value):
        normalized = str(value or "").strip()
        if not normalized:
            raise serializers.ValidationError("Organization name is required.")
        return normalized

    def validate(self, attrs):
        if attrs.get("password") != attrs.get("password_confirm"):
            raise serializers.ValidationError({"password": "Password fields didn't match."})
        return attrs


class OrganizationAdminRegistrationOrganizationSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    code = serializers.CharField()
    name = serializers.CharField()
    organization_type = serializers.CharField()


class OrganizationAdminRegistrationMembershipSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    membership_role = serializers.CharField()
    is_active = serializers.BooleanField()
    is_default = serializers.BooleanField()
    joined_at = serializers.DateTimeField(allow_null=True)


class OrganizationAdminRegistrationResponseSerializer(serializers.Serializer):
    message = serializers.CharField()
    user_type = serializers.ChoiceField(choices=USER_TYPE_CHOICES)
    user = UserSerializer()
    organization = OrganizationAdminRegistrationOrganizationSerializer()
    membership = OrganizationAdminRegistrationMembershipSerializer()


class MessageResponseSerializer(serializers.Serializer):
    message = serializers.CharField()


class ErrorResponseSerializer(serializers.Serializer):
    error = serializers.CharField()

class TwoFactorChallengeSerializer(serializers.Serializer):
    message = serializers.CharField()
    token = serializers.CharField()
    user_type = serializers.ChoiceField(choices=USER_TYPE_CHOICES, required=False)
    setup_required = serializers.BooleanField(required=False)
    expires_in_seconds = serializers.IntegerField(required=False)
    provisioning_uri = serializers.CharField(required=False, allow_null=True, allow_blank=True)


class ChangePasswordSerializer(serializers.Serializer):
    """Serializer for password change"""
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, validators=[validate_password])
    new_password_confirm = serializers.CharField(required=True)
    
    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError({
                "new_password": "Password fields didn't match."
            })
        return attrs


class TwoFactorVerificationSerializer(serializers.Serializer):
    token = serializers.CharField(required=True)
    otp = serializers.CharField(required=False, allow_blank=True)
    backup_code = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        otp = str(attrs.get("otp", "")).strip()
        backup_code = str(attrs.get("backup_code", "")).strip()

        if bool(otp) == bool(backup_code):
            raise serializers.ValidationError(
                "Provide exactly one verification factor: otp or backup_code."
            )

        attrs["otp"] = otp
        attrs["backup_code"] = backup_code
        return attrs


class TwoFactorEnableRequestSerializer(serializers.Serializer):
    otp = serializers.CharField(required=True)


class TwoFactorSetupResponseSerializer(serializers.Serializer):
    provisioning_uri = serializers.CharField()


class TwoFactorBackupCodesRegenerateSerializer(serializers.Serializer):
    otp = serializers.CharField(required=False, allow_blank=True)
    backup_code = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        otp = str(attrs.get("otp", "")).strip()
        backup_code = str(attrs.get("backup_code", "")).strip()

        if bool(otp) == bool(backup_code):
            raise serializers.ValidationError(
                "Provide exactly one verification factor: otp or backup_code."
            )

        attrs["otp"] = otp
        attrs["backup_code"] = backup_code
        return attrs


class TwoFactorBackupCodesResponseSerializer(serializers.Serializer):
    message = serializers.CharField()
    backup_codes = serializers.ListField(child=serializers.CharField())


class TwoFactorStatusResponseSerializer(serializers.Serializer):
    user_type = serializers.ChoiceField(choices=USER_TYPE_CHOICES)
    two_factor_required = serializers.BooleanField()
    applicant_exempt = serializers.BooleanField()
    is_two_factor_enabled = serializers.BooleanField()
    has_totp_secret = serializers.BooleanField()
    backup_codes_remaining = serializers.IntegerField(min_value=0)
