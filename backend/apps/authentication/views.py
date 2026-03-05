# backend/apps/authentication/views.py

import logging
import secrets

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core import signing
from django.core.cache import cache
from django.core.mail import send_mail
from django.core.signing import BadSignature, SignatureExpired, Signer
from django.db import transaction
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from apps.authentication.models import User, UserProfile
from apps.authentication.serializers import (
    AdminAuthResponseSerializer,
    AdminLoginSerializer,
    AdminUserSerializer,
    ChangePasswordSerializer,
    ErrorResponseSerializer,
    LoginSerializer,
    LogoutRequestSerializer,
    MessageResponseSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    ProfileResponseSerializer,
    ProfileUpdateSerializer,
    RegisterResponseSerializer,
    TwoFactorChallengeSerializer,
    TwoFactorBackupCodesRegenerateSerializer,
    TwoFactorBackupCodesResponseSerializer,
    TwoFactorStatusResponseSerializer,
    TwoFactorEnableRequestSerializer,
    TwoFactorSetupResponseSerializer,
    TwoFactorVerificationSerializer,
    UserAuthResponseSerializer,
    UserRegistrationSerializer,
    UserSerializer,
)
from apps.billing.models import BillingSubscription

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

try:
    import pyotp
except ImportError:  # pragma: no cover - dependency may be optional in some setups
    pyotp = None

logger = logging.getLogger(__name__)
TWO_FACTOR_CHALLENGE_SALT = 'auth.login.2fa.challenge'

def _two_factor_challenge_ttl_seconds() -> int:
    ttl = int(getattr(settings, 'AUTH_TWO_FACTOR_CHALLENGE_TTL_SECONDS', 300))
    return ttl if ttl > 0 else 300


def _consume_registration_subscription(reference: str, email: str) -> bool:
    """Validate and consume a billing subscription reference for one-time registration."""
    if not reference:
        return False

    subscription = (
        BillingSubscription.objects.select_for_update()
        .filter(reference=reference)
        .order_by("-created_at")
        .first()
    )
    if subscription is None:
        return False

    if subscription.status != "complete":
        return False

    if subscription.payment_status not in {"paid", "no_payment_required"}:
        return False

    if subscription.ticket_expires_at and subscription.ticket_expires_at <= timezone.now():
        return False

    if subscription.registration_consumed_at is not None:
        return False

    subscription.registration_consumed_at = timezone.now()
    subscription.registration_consumed_by_email = email
    subscription.save(update_fields=["registration_consumed_at", "registration_consumed_by_email", "updated_at"])
    return True


def _build_two_factor_challenge(user: User):
    """Builds a time-limited 2FA challenge payload for all non-applicant logins."""
    if pyotp is None:
        return Response(
            {"error": "2FA dependency is not installed."},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    setup_required = not user.is_two_factor_enabled

    if not user.two_factor_secret:
        user.two_factor_secret = pyotp.random_base32()
        user.save(update_fields=["two_factor_secret", "updated_at"])
        setup_required = True

    nonce = secrets.token_urlsafe(16)
    challenge_token = signing.dumps(
        {"email": user.email, "nonce": nonce, "purpose": "login_2fa"},
        salt=TWO_FACTOR_CHALLENGE_SALT,
    )
    ttl_seconds = _two_factor_challenge_ttl_seconds()

    payload = {
        "message": "Two-factor verification required.",
        "token": challenge_token,
        "user_type": user.user_type,
        "setup_required": setup_required,
        "expires_in_seconds": ttl_seconds,
    }

    if setup_required:
        payload["provisioning_uri"] = user.get_totp_uri()

    return Response(payload, status=status.HTTP_200_OK)

class RegisterView(generics.CreateAPIView):
    """
    Firm registration endpoint
    POST /api/auth/register/
    """
    queryset = User.objects.all()
    permission_classes = [AllowAny]
    serializer_class = UserRegistrationSerializer
    
    @extend_schema(
        request=UserRegistrationSerializer,
        responses={201: RegisterResponseSerializer, 400: ErrorResponseSerializer, 403: ErrorResponseSerializer},
    )
    def create(self, request, *args, **kwargs):
        public_registration_enabled = getattr(settings, "AUTH_PUBLIC_REGISTRATION_ENABLED", False)
        subscription_reference = str(request.data.get("subscription_reference", "")).strip()

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if not public_registration_enabled:
            email = serializer.validated_data.get("email", "")
            with transaction.atomic():
                if not _consume_registration_subscription(subscription_reference, email):
                    return Response(
                        {
                            "error": (
                                "Registration requires a valid subscription reference. "
                                "Confirm subscription first or contact support."
                            )
                        },
                        status=status.HTTP_403_FORBIDDEN,
                    )
                user = serializer.save()
        else:
            user = serializer.save()
        return Response({
            'user': UserSerializer(user).data,
            'user_type': user.user_type,
            'message': 'Registration successful. Please sign in to continue.',
        }, status=status.HTTP_201_CREATED)


@extend_schema(
    request=LoginSerializer,
    responses={
        200: PolymorphicProxySerializer(
            component_name="LoginResponse",
            serializers=[UserAuthResponseSerializer, TwoFactorChallengeSerializer],
            resource_type_field_name=None,
        ),
        400: ErrorResponseSerializer,
        503: ErrorResponseSerializer,
    },
)
@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    """
    User login endpoint
    POST /api/auth/login/
    Body: {"email": "user@example.com", "password": "password123"}

    Applicants receive direct JWT tokens.
    Non-applicant accounts must complete 2FA challenge before tokens are issued.
    """
    serializer = LoginSerializer(data=request.data, context={'request': request})
    serializer.is_valid(raise_exception=True)
    user = serializer.validated_data['user']

    if user.user_type == 'applicant':
        refresh = RefreshToken.for_user(user)
        return Response({
            'user': UserSerializer(user).data,
            'tokens': {
                'access': str(refresh.access_token),
                'refresh': str(refresh),
            },
            'user_type': user.user_type,
        })

    return _build_two_factor_challenge(user)

@extend_schema(
    request=AdminLoginSerializer,
    responses={
        200: PolymorphicProxySerializer(
            component_name="AdminLoginResponse",
            serializers=[AdminAuthResponseSerializer, TwoFactorChallengeSerializer],
            resource_type_field_name=None,
        ),
        400: ErrorResponseSerializer,
    },
)
@api_view(['POST'])
@permission_classes([AllowAny])
def admin_login_view(request):
    """
    Admin login endpoint
    POST /api/auth/admin/login/
    Body: {"email": "admin@example.com", "password": "password123"}

    Always returns a 2FA challenge for successful admin credential checks.
    """
    serializer = AdminLoginSerializer(data=request.data, context={'request': request})
    serializer.is_valid(raise_exception=True)
    user = serializer.validated_data['user']
    return _build_two_factor_challenge(user)

@extend_schema(
    request=TwoFactorVerificationSerializer,
    responses={
        200: PolymorphicProxySerializer(
            component_name="TwoFactorVerifyResponse",
            serializers=[UserAuthResponseSerializer, AdminAuthResponseSerializer],
            resource_type_field_name=None,
        ),
        400: ErrorResponseSerializer,
    },
)
@api_view(['POST'])
@permission_classes([AllowAny])
def two_factor_verification_view(request):
    """
    2FA verification endpoint
    POST /api/auth/login/verify/ (alias: /api/auth/admin/login/verify/)
    Body: {"token": "challenge_token", "otp": "123456"} or {"token": "challenge_token", "backup_code": "ABCD-EFGH"}
    """
    serializer = TwoFactorVerificationSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    try:
        challenge_payload = signing.loads(
            serializer.validated_data["token"],
            salt=TWO_FACTOR_CHALLENGE_SALT,
            max_age=_two_factor_challenge_ttl_seconds(),
        )
        email = str(challenge_payload.get("email", "")).strip().lower()
        nonce = str(challenge_payload.get("nonce", "")).strip()
        purpose = str(challenge_payload.get("purpose", "")).strip()
        if not email or not nonce or purpose != "login_2fa":
            raise BadSignature("Malformed challenge payload.")
    except SignatureExpired:
        return Response(
            {"error": "2FA challenge expired. Please sign in again."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    except BadSignature:
        return Response({"error": "Invalid token."}, status=status.HTTP_400_BAD_REQUEST)

    consumed_cache_key = f"auth:2fa:consumed:{nonce}"
    if cache.get(consumed_cache_key):
        return Response(
            {"error": "2FA challenge already used. Please sign in again."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        return Response({"error": "User not found."}, status=status.HTTP_400_BAD_REQUEST)

    otp = serializer.validated_data.get("otp", "")
    backup_code = serializer.validated_data.get("backup_code", "")
    using_backup_code = bool(backup_code)

    if otp:
        factor_verified = user.verify_totp(otp)
    else:
        factor_verified = user.verify_backup_code(backup_code)

    if not factor_verified:
        return Response({"error": "Invalid OTP or backup code."}, status=status.HTTP_400_BAD_REQUEST)

    if not cache.add(consumed_cache_key, True, timeout=_two_factor_challenge_ttl_seconds()):
        return Response(
            {"error": "2FA challenge already used. Please sign in again."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if using_backup_code and not user.consume_backup_code(backup_code):
        cache.delete(consumed_cache_key)
        return Response({"error": "Invalid OTP or backup code."}, status=status.HTTP_400_BAD_REQUEST)

    was_two_factor_enabled = user.is_two_factor_enabled
    if user.user_type != "applicant" and not user.is_two_factor_enabled:
        user.is_two_factor_enabled = True
        user.save(update_fields=["is_two_factor_enabled", "updated_at"])

    issued_backup_codes = None
    if user.user_type != "applicant" and not was_two_factor_enabled and not user.has_backup_codes():
        issued_backup_codes = user.generate_backup_codes()

    refresh = RefreshToken.for_user(user)

    user_serializer = (
        AdminUserSerializer(user)
        if (user.is_staff or user.user_type == "admin")
        else UserSerializer(user)
    )
    payload = {
        "user": user_serializer.data,
        "tokens": {
            "access": str(refresh.access_token),
            "refresh": str(refresh),
        },
        "user_type": user.user_type,
    }
    if issued_backup_codes:
        payload["backup_codes"] = issued_backup_codes
    return Response(payload)
@extend_schema(
    responses={
        200: TwoFactorSetupResponseSerializer,
        403: ErrorResponseSerializer,
        503: ErrorResponseSerializer,
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def two_factor_setup_view(request):
    """
    2FA setup endpoint
    GET /api/auth/admin/2fa/setup/
    """
    user = request.user
    if user.user_type == "applicant":
        return Response(
            {'error': 'Applicants are exempt from account 2FA setup.'},
            status=status.HTTP_403_FORBIDDEN,
        )
    if pyotp is None:
        return Response({'error': '2FA dependency is not installed.'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    secret = pyotp.random_base32()
    user.two_factor_secret = secret
    user.save()
    
    return Response({'provisioning_uri': user.get_totp_uri()})


@extend_schema(
    request=TwoFactorEnableRequestSerializer,
    responses={
        200: MessageResponseSerializer,
        400: ErrorResponseSerializer,
        403: ErrorResponseSerializer,
    },
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def two_factor_enable_view(request):
    """
    2FA enable endpoint
    POST /api/auth/admin/2fa/enable/
    Body: {"otp": "123456"}
    """
    user = request.user
    if user.user_type == "applicant":
        return Response(
            {'error': 'Applicants are exempt from account 2FA.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    otp = request.data.get('otp')
    if not otp:
        return Response({'error': 'OTP not provided.'}, status=status.HTTP_400_BAD_REQUEST)

    if not user.verify_totp(otp):
        return Response({'error': 'Invalid OTP.'}, status=status.HTTP_400_BAD_REQUEST)

    user.is_two_factor_enabled = True
    user.save()
    return Response({'message': '2FA enabled successfully.'})


@extend_schema(
    request=TwoFactorBackupCodesRegenerateSerializer,
    responses={
        200: TwoFactorBackupCodesResponseSerializer,
        400: ErrorResponseSerializer,
        403: ErrorResponseSerializer,
    },
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def two_factor_backup_codes_regenerate_view(request):
    """
    Regenerate account backup codes.
    POST /api/auth/2fa/backup-codes/regenerate/
    Body: {"otp": "123456"} or {"backup_code": "ABCD-EFGH"}
    """
    user = request.user
    if user.user_type == "applicant":
        return Response(
            {'error': 'Applicants are exempt from account 2FA.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    if not user.is_two_factor_enabled:
        return Response(
            {'error': 'Enable 2FA before regenerating backup codes.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    serializer = TwoFactorBackupCodesRegenerateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    otp = serializer.validated_data.get("otp", "")
    backup_code = serializer.validated_data.get("backup_code", "")

    if otp:
        verified = user.verify_totp(otp)
    else:
        verified = user.consume_backup_code(backup_code)

    if not verified:
        return Response(
            {'error': 'Invalid OTP or backup code.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    backup_codes = user.generate_backup_codes()
    return Response(
        {
            'message': 'Backup codes regenerated. Store them securely; they are shown once.',
            'backup_codes': backup_codes,
        }
    )


@extend_schema(
    responses={200: TwoFactorStatusResponseSerializer, 403: ErrorResponseSerializer},
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def two_factor_status_view(request):
    """
    Fetch account 2FA status for authenticated user.
    GET /api/auth/2fa/status/
    """
    user = request.user
    is_applicant = user.user_type == "applicant"
    return Response(
        {
            "user_type": user.user_type,
            "two_factor_required": not is_applicant,
            "applicant_exempt": is_applicant,
            "is_two_factor_enabled": bool(user.is_two_factor_enabled),
            "has_totp_secret": bool(user.two_factor_secret),
            "backup_codes_remaining": len(user.two_factor_backup_codes or []),
        }
    )


@extend_schema(
    request=LogoutRequestSerializer,
    responses={200: MessageResponseSerializer, 400: ErrorResponseSerializer},
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_view(request):
    """
    User logout endpoint
    POST /api/auth/logout/
    Body: {"refresh": "refresh_token"}
    """
    try:
        refresh_token = request.data.get('refresh')
        token = RefreshToken(refresh_token)
        token.blacklist()
        return Response({'message': 'Successfully logged out'})
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )


@extend_schema(responses={200: ProfileResponseSerializer})
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def profile_view(request):
    """
    Get current user profile
    GET /api/auth/profile/
    """
    UserProfile.objects.get_or_create(user=request.user)

    if request.user.is_staff or request.user.user_type in {"admin", "hr_manager"}:
        serializer = AdminUserSerializer(request.user, context={"request": request})
        user_type = request.user.user_type
    else:
        serializer = UserSerializer(request.user, context={"request": request})
        user_type = request.user.user_type
    
    return Response({
        'user': serializer.data,
        'user_type': user_type
    })


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

    if request.user.is_staff or request.user.user_type in {"admin", "hr_manager"}:
        response_serializer = AdminUserSerializer(user, context={"request": request})
    else:
        response_serializer = UserSerializer(user, context={"request": request})
    return Response(response_serializer.data)


@extend_schema(
    request=ChangePasswordSerializer,
    responses={200: MessageResponseSerializer, 400: ErrorResponseSerializer},
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password_view(request):
    """
    Change user password
    POST /api/auth/change-password/
    Body: {
        "old_password": "old_pass",
        "new_password": "new_pass",
        "new_password_confirm": "new_pass"
    }
    """
    serializer = ChangePasswordSerializer(data=request.data)
    
    if serializer.is_valid():
        user = request.user
        
        # Check old password
        if not user.check_password(serializer.data.get('old_password')):
            return Response(
                {'old_password': ['Wrong password.']},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Set new password
        user.set_password(serializer.data.get('new_password'))
        user.save()
        
        return Response({'message': 'Password changed successfully'})
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    request=PasswordResetRequestSerializer,
    responses={200: MessageResponseSerializer, 400: ErrorResponseSerializer},
)
@api_view(['POST'])
@permission_classes([AllowAny])
def password_reset_request_view(request):
    """
    Request password reset
    POST /api/auth/password-reset/
    Body: {"email": "user@example.com"}
    """
    serializer = PasswordResetRequestSerializer(data=request.data)
    
    if serializer.is_valid():
        email = serializer.data.get('email')
        
        try:
            user = User.objects.get(email=email)
            
            # Generate reset token
            token = default_token_generator.make_token(user)
            signed_token = Signer().sign(f"{user.pk}:{token}")
            
            # Send email
            reset_link = f"{settings.FRONTEND_URL}/reset-password/{signed_token}/"
            
            send_mail(
                subject='Password Reset Request',
                message=f'Click the link to reset your password: {reset_link}',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                fail_silently=False,
            )
            
            logger.info(f"Password reset email sent to {email}")
            
        except User.DoesNotExist:
            # Don't reveal that user doesn't exist
            logger.info("Password reset requested for non-existent email: %s", email)
        
        return Response({
            'message': 'If an account exists with this email, a password reset link has been sent.'
        })
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    request=PasswordResetConfirmSerializer,
    responses={200: MessageResponseSerializer, 400: ErrorResponseSerializer},
)
@api_view(['POST'])
@permission_classes([AllowAny])
def password_reset_confirm_view(request):
    """
    Confirm password reset
    POST /api/auth/password-reset-confirm/
    Body: {
        "token": "reset_token",
        "new_password": "new_pass",
        "new_password_confirm": "new_pass"
    }
    """
    serializer = PasswordResetConfirmSerializer(data=request.data)
    
    if serializer.is_valid():
        signed_token = serializer.validated_data['token']
        signer = Signer()

        try:
            payload = signer.unsign(signed_token)
            user_id_str, reset_token = payload.split(":", 1)
            user = User.objects.get(pk=user_id_str)
        except (BadSignature, User.DoesNotExist):
            return Response(
                {'error': 'Invalid or expired reset token.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not default_token_generator.check_token(user, reset_token):
            return Response(
                {'error': 'Invalid or expired reset token.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(serializer.validated_data['new_password'])
        user.save(update_fields=['password', 'updated_at'])
        return Response({'message': 'Password has been reset successfully'})
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)














