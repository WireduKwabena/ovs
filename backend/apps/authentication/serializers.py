# backend/apps/authentication/serializers.py
from django.contrib.auth import authenticate
from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from apps.authentication.models import User, UserProfile

USER_TYPE_CHOICES = User.USER_TYPE_CHOICES

class UserSerializer(serializers.ModelSerializer):
    """Serializer for regular users (applicants)"""
    full_name = serializers.CharField(source='get_full_name', read_only=True)
    profile = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = User
        fields = [
            'id', 'email', 'first_name', 'last_name', 'full_name', 'phone_number',
            'organization', 'department', 'user_type', 'is_active', 'is_staff', 'is_superuser', 'created_at', 'profile'
        ]
        read_only_fields = ['id', 'created_at', 'user_type', 'is_active', 'is_staff', 'is_superuser']

    def get_profile(self, obj):
        profile = getattr(obj, "profile", None)
        if profile is None:
            return None
        return UserProfileSerializer(profile, context=self.context).data


class UserRegistrationSerializer(serializers.ModelSerializer):
    """Serializer for firm registration"""
    password = serializers.CharField(
        write_only=True, 
        required=True, 
        validators=[validate_password]
    )
    password_confirm = serializers.CharField(write_only=True, required=True)
    subscription_reference = serializers.CharField(write_only=True, required=False, allow_blank=True)
    
    class Meta:
        model = User
        fields = [
            'email', 'password', 'password_confirm', 
            'first_name', 'last_name', 'phone_number', 'organization', 'department', 'subscription_reference'
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
        validated_data.setdefault("user_type", "hr_manager")
        user = User.objects.create_user(**validated_data)
        return user


class AdminUserSerializer(serializers.ModelSerializer):
    """Serializer for admin users"""
    role_display = serializers.CharField(source='get_user_type_display', read_only=True)
    full_name = serializers.CharField(source='get_full_name', read_only=True)
    profile = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = User
        fields = [
            'id', 'email', 'first_name', 'last_name', 'full_name', 'phone_number',
            'organization', 'department', 'user_type', 'role_display', 'is_active', 'is_staff', 'is_superuser', 'created_at', 'profile'
        ]
        read_only_fields = ['id', 'created_at', 'user_type', 'is_active', 'is_staff', 'is_superuser']

    def get_profile(self, obj):
        profile = getattr(obj, "profile", None)
        if profile is None:
            return None
        return UserProfileSerializer(profile, context=self.context).data


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


class PasswordResetRequestSerializer(serializers.Serializer):
    """Serializer for password reset request"""
    email = serializers.EmailField(required=True)


class PasswordResetConfirmSerializer(serializers.Serializer):
    """Serializer for password reset confirmation"""
    token = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, validators=[validate_password])
    new_password_confirm = serializers.CharField(required=True)
    
    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError({
                "new_password": "Password fields didn't match."
            })
        return attrs

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

class AdminLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')

        if email and password:
            user = authenticate(request=self.context.get('request'), email=email, password=password)
            if not user or not user.is_staff:
                raise serializers.ValidationError('Invalid credentials or not an admin user.', code='authorization')
        else:
            raise serializers.ValidationError('Email and password are required.', code='authorization')

        attrs['user'] = user
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


class LogoutRequestSerializer(serializers.Serializer):
    refresh = serializers.CharField(required=True)


class TokenPairSerializer(serializers.Serializer):
    access = serializers.CharField()
    refresh = serializers.CharField()


class UserAuthResponseSerializer(serializers.Serializer):
    user = UserSerializer()
    tokens = TokenPairSerializer()
    user_type = serializers.ChoiceField(choices=USER_TYPE_CHOICES)
    backup_codes = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True,
    )


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


class TwoFactorChallengeSerializer(serializers.Serializer):
    message = serializers.CharField()
    token = serializers.CharField()
    user_type = serializers.ChoiceField(choices=USER_TYPE_CHOICES, required=False)
    setup_required = serializers.BooleanField(required=False)
    expires_in_seconds = serializers.IntegerField(required=False)
    provisioning_uri = serializers.CharField(required=False, allow_null=True, allow_blank=True)


class MessageResponseSerializer(serializers.Serializer):
    message = serializers.CharField()


class ErrorResponseSerializer(serializers.Serializer):
    error = serializers.CharField()


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


class ProfileResponseSerializer(serializers.Serializer):
    user = serializers.DictField()
    user_type = serializers.ChoiceField(choices=USER_TYPE_CHOICES)








