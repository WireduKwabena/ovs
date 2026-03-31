from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.exceptions import PermissionDenied

import logging
import secrets
from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.tokens import default_token_generator
from django.core import signing
from django.core.cache import cache
from django.core.signing import BadSignature, SignatureExpired, Signer
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.text import slugify

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
from .serializers import (
    UserRegistrationSerializer,
    TokenPairSerializer,
    LoginSerializer,
    UserAuthResponseSerializer,
    PasswordResetRequestSerializer,
    PasswordResetConfirmSerializer,
    AdminLoginSerializer,
    AdminAuthResponseSerializer,
    OrganizationAdminRegistrationSerializer,
    OrganizationAdminRegistrationResponseSerializer,
    MessageResponseSerializer,
    ErrorResponseSerializer,
    TwoFactorChallengeSerializer,
    RegisterResponseSerializer,
    OrganizationAdminRegistrationOrganizationSerializer,
    OrganizationAdminRegistrationMembershipSerializer,
    ChangePasswordSerializer,
    TwoFactorVerificationSerializer,
    TwoFactorEnableRequestSerializer,
    TwoFactorSetupResponseSerializer,
    TwoFactorBackupCodesRegenerateSerializer,
    TwoFactorBackupCodesResponseSerializer,
    TwoFactorStatusResponseSerializer,
    LogoutRequestSerializer,
)
from .throttles import (
    LoginRateThrottle,
    PasswordResetRateThrottle,
    RegistrationRateThrottle,
    TwoFactorRateThrottle,
)

from apps.users.models import User, UserProfile
from apps.users.serializers import UserSerializer, AdminUserSerializer
from apps.users.permissions import RECENT_AUTH_SESSION_KEY, RECENT_AUTH_TOKEN_CLAIM
from apps.core.authz import ROLE_ADMIN, get_user_capabilities, get_user_roles, has_role, requires_two_factor_for_user
from apps.billing.models import BillingSubscription
from apps.billing.quotas import enforce_organization_seat_quota
from apps.billing.services import validate_organization_onboarding_token
from apps.governance.models import OrganizationMembership
from apps.tenants.models import Organization
from django_tenants.utils import schema_context

logger = logging.getLogger(__name__)

TWO_FACTOR_CHALLENGE_SALT = 'auth.login.2fa.challenge'
ONBOARDING_REGISTRATION_REASON_MESSAGES = {
    "missing_token": "Registration requires a valid organization onboarding token.",
    "not_found": "The onboarding token is invalid. Request a fresh invite link from your organization admin.",
    "inactive": "This onboarding token has been revoked. Request a fresh invite link from your organization admin.",
    "expired": "This onboarding token has expired. Request a fresh invite link from your organization admin.",
    "max_uses_reached": "This onboarding token has reached its usage limit. Request a fresh invite link.",
    "subscription_inactive": (
        "Registration is unavailable because the organization subscription is inactive. "
        "Contact your organization admin."
    ),
    "organization_mismatch": "The onboarding token is invalid for this organization context.",
    "email_required": "Registration email is required for this onboarding token.",
    "email_domain_not_allowed": "Your email domain is not allowed for this onboarding token.",
}


def _consume_registration_onboarding_token(*, raw_token: str, email: str):
    return validate_organization_onboarding_token(
        raw_token=raw_token,
        email=email,
        consume=True,
    )


def _two_factor_challenge_ttl_seconds() -> int:
    ttl = int(getattr(settings, 'AUTH_TWO_FACTOR_CHALLENGE_TTL_SECONDS', 300))
    return ttl if ttl > 0 else 300


def _mark_recent_auth(request, refresh_token: RefreshToken) -> int:
    """
    Stamp a recent-auth timestamp into token/session context for step-up checks.
    """
    epoch = int(timezone.now().timestamp())
    refresh_token[RECENT_AUTH_TOKEN_CLAIM] = epoch

    session = getattr(request, "session", None)
    if session is not None:
        session[RECENT_AUTH_SESSION_KEY] = epoch
        session.modified = True
    return epoch


def _registration_error_for_onboarding_reason(reason: str) -> dict:
    normalized_reason = str(reason or "invalid").strip().lower() or "invalid"
    return {
        "error": ONBOARDING_REGISTRATION_REASON_MESSAGES.get(
            normalized_reason,
            "Registration requires a valid organization onboarding token.",
        ),
        "code": "ONBOARDING_TOKEN_INVALID",
        "reason": normalized_reason,
    }

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



def _resolve_public_bootstrap_organization_code(*, preferred_code: str, organization_name: str) -> str:
    base_code = slugify(preferred_code or organization_name).strip("-")
    if not base_code:
        base_code = f"organization-{secrets.token_hex(4)}"
    base_code = base_code[:80]
    candidate = base_code
    suffix = 2

    while Organization.objects.filter(code=candidate).exists():
        suffix_text = f"-{suffix}"
        candidate = f"{base_code[: max(1, 80 - len(suffix_text))]}{suffix_text}"
        suffix += 1
    return candidate



def _attach_registered_user_to_organization(
    *,
    user: User,
    organization,
    subscription: BillingSubscription | None = None,
    membership_role: str = "member",
) -> None:
    if organization is None:
        return

    locked_organization = (
        Organization.objects.select_for_update()
        .filter(id=getattr(organization, "id", None), is_active=True)
        .first()
    )
    if locked_organization is None:
        raise PermissionDenied("Target organization is unavailable for onboarding.")

    if subscription is not None:
        enforce_organization_seat_quota(
            organization_id=str(locked_organization.id),
            subscription=subscription,
            additional=1,
        )

    organization_name = str(getattr(locked_organization, "name", "") or "").strip()
    if organization_name and str(getattr(user, "organization", "") or "").strip().lower() != organization_name.lower():
        user.organization = organization_name
        user.save(update_fields=["organization", "updated_at"])

    membership, _created = OrganizationMembership.objects.get_or_create(
        user=user,
        defaults={
            "membership_role": membership_role,
            "is_active": True,
            "is_default": True,
            "joined_at": timezone.now(),
        },
    )

    updated_fields: list[str] = []
    if not membership.is_active:
        membership.is_active = True
        updated_fields.append("is_active")
    if membership.left_at is not None:
        membership.left_at = None
        updated_fields.append("left_at")
    if not membership.membership_role:
        membership.membership_role = membership_role
        updated_fields.append("membership_role")

    has_default_membership = OrganizationMembership.objects.filter(
        user=user,
        is_active=True,
        is_default=True,
    ).exclude(pk=membership.pk).exists()
    if not has_default_membership and not membership.is_default:
        membership.is_default = True
        updated_fields.append("is_default")

    if updated_fields:
        membership.save(update_fields=updated_fields + ["updated_at"])



class OrganizationAdminRegisterView(generics.CreateAPIView):
    """
    Public bootstrap for a brand-new organization plus initial org-admin account.

    Member onboarding remains invite-token gated via /api/auth/register/.
    """

    queryset = User.objects.none()
    permission_classes = [AllowAny]
    throttle_classes = [RegistrationRateThrottle]
    serializer_class = OrganizationAdminRegistrationSerializer

    @extend_schema(
        request=OrganizationAdminRegistrationSerializer,
        responses={201: OrganizationAdminRegistrationResponseSerializer, 400: ErrorResponseSerializer},
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        validated = serializer.validated_data
        organization_name = str(validated.get("organization_name", "")).strip()
        preferred_code = str(validated.get("organization_code", "")).strip()

        if Organization.objects.filter(name__iexact=organization_name).exists():
            return Response(
                {"organization_name": ["An organization with this name already exists."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if preferred_code and Organization.objects.filter(code__iexact=preferred_code).exists():
            return Response(
                {"organization_code": ["This organization code is already in use."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        organization_code = _resolve_public_bootstrap_organization_code(
            preferred_code=preferred_code,
            organization_name=organization_name,
        )

        try:
            with transaction.atomic():
                # Step 1: create the Organization in the public schema.
                # TenantMixin.save() provisions the tenant schema automatically
                # (auto_create_schema = True) so the tenant tables are ready
                # before we switch into it below.
                organization = Organization.objects.create(
                    name=organization_name,
                    code=organization_code,
                    organization_type=str(validated.get("organization_type", "agency") or "agency"),
                    is_active=True,
                )

                # Step 2: create the admin User and OrganizationMembership inside
                # the new tenant's schema.  apps.users and apps.governance are
                # TENANT_APPS so their tables only exist per-schema.
                with schema_context(organization.schema_name):
                    user = User.objects.create_user(
                        email=validated["email"],
                        password=validated["password"],
                        first_name=str(validated.get("first_name", "")).strip(),
                        last_name=str(validated.get("last_name", "")).strip(),
                        phone_number=str(validated.get("phone_number", "")).strip(),
                        department=str(validated.get("department", "")).strip(),
                        user_type="internal",
                    )
                    membership = OrganizationMembership.objects.create(
                        user=user,
                        membership_role="registry_admin",
                        title=str(validated.get("department", "")).strip()[:120],
                        is_active=True,
                        is_default=True,
                        joined_at=timezone.now(),
                    )

                    if str(user.organization or "").strip().lower() != organization_name.lower():
                        user.organization = organization_name
                        user.save(update_fields=["organization", "updated_at"])
        except IntegrityError:
            return Response(
                {"error": "Organization bootstrap failed due to a conflicting record. Retry with different values."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        payload = {
            "message": "Organization admin account created. Sign in to continue setup.",
            "user_type": user.user_type,
            "user": UserSerializer(user, context={"request": request}).data,
            "organization": {
                "id": organization.id,
                "code": organization.code,
                "name": organization.name,
                "organization_type": organization.organization_type,
            },
            "membership": {
                "id": membership.id,
                "membership_role": membership.membership_role,
                "is_active": membership.is_active,
                "is_default": membership.is_default,
                "joined_at": membership.joined_at,
            },
        }
        return Response(
            OrganizationAdminRegistrationResponseSerializer(payload).data,
            status=status.HTTP_201_CREATED,
        )



class RegisterView(generics.CreateAPIView):
    """
    Firm registration endpoint
    POST /api/auth/register/
    """
    queryset = User.objects.all()
    permission_classes = [AllowAny]
    throttle_classes = [RegistrationRateThrottle]
    serializer_class = UserRegistrationSerializer
    
    @extend_schema(
        request=UserRegistrationSerializer,
        responses={201: RegisterResponseSerializer, 400: ErrorResponseSerializer, 403: ErrorResponseSerializer},
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data.get("email", "")
        onboarding_token = str(serializer.validated_data.get("onboarding_token", "")).strip()

        with transaction.atomic():
            onboarding_result = _consume_registration_onboarding_token(
                raw_token=onboarding_token,
                email=email,
            )
            if not onboarding_result.valid or onboarding_result.token_record is None:
                return Response(
                    _registration_error_for_onboarding_reason(onboarding_result.reason),
                    status=status.HTTP_403_FORBIDDEN,
                )

            consumed_org = getattr(onboarding_result.token_record, "organization", None)
            consumed_subscription = onboarding_result.subscription
            if consumed_org is None:
                return Response(
                    _registration_error_for_onboarding_reason("organization_mismatch"),
                    status=status.HTTP_403_FORBIDDEN,
                )

            user = serializer.save()
            _attach_registered_user_to_organization(
                user=user,
                organization=consumed_org,
                subscription=consumed_subscription,
                membership_role="member",
            )
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
@throttle_classes([LoginRateThrottle])
def login_view(request):
    """
    User login endpoint
    POST /api/auth/login/
    Body: {"email": "user@example.com", "password": "password123"}

    External users receive direct JWT tokens.
    Internal operator accounts must complete 2FA challenge before tokens are issued.
    """
    serializer = LoginSerializer(data=request.data, context={'request': request})
    serializer.is_valid(raise_exception=True)
    user = serializer.validated_data['user']

    if not requires_two_factor_for_user(user):
        refresh = RefreshToken.for_user(user)
        _mark_recent_auth(request=request, refresh_token=refresh)
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
@throttle_classes([LoginRateThrottle])
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


@extend_schema(
    request=PasswordResetRequestSerializer,
    responses={200: MessageResponseSerializer, 400: ErrorResponseSerializer},
)
@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([PasswordResetRateThrottle])
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
@throttle_classes([TwoFactorRateThrottle])
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
        # Do NOT delete the cache key here — fail-close to prevent replay
        # attacks that could exploit the window between verify and consume.
        return Response({"error": "Invalid OTP or backup code."}, status=status.HTTP_400_BAD_REQUEST)

    two_factor_required = requires_two_factor_for_user(user)
    was_two_factor_enabled = user.is_two_factor_enabled
    if two_factor_required and not user.is_two_factor_enabled:
        user.is_two_factor_enabled = True
        user.save(update_fields=["is_two_factor_enabled", "updated_at"])

    issued_backup_codes = None
    if two_factor_required and not was_two_factor_enabled and not user.has_backup_codes():
        issued_backup_codes = user.generate_backup_codes()

    refresh = RefreshToken.for_user(user)
    _mark_recent_auth(request=request, refresh_token=refresh)

    try:
        from apps.audit.events import log_event as _log_event  # noqa: PLC0415
        _log_event(
            request=request,
            action="login",
            entity_type="User",
            entity_id=str(user.pk),
            changes={
                "two_factor_method": "backup_code" if using_backup_code else "totp",
                "two_factor_enabled_on_login": not was_two_factor_enabled and user.is_two_factor_enabled,
            },
        )
    except Exception:  # noqa: BLE001
        pass  # Audit failure must never block authentication

    user_serializer = AdminUserSerializer(user) if has_role(user, ROLE_ADMIN) else UserSerializer(user)
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
    if not requires_two_factor_for_user(user):
        return Response(
            {'error': 'This account is exempt from operator 2FA setup.'},
            status=status.HTTP_403_FORBIDDEN,
        )
    if pyotp is None:
        return Response({'error': '2FA dependency is not installed.'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    secret = pyotp.random_base32()
    # Store in cache only — do NOT persist to DB until the user proves they
    # can generate a valid OTP (confirmed in two_factor_enable_view).
    cache.set(f"2fa:pending_secret:{user.pk}", secret, timeout=600)
    # Temporarily set on the model instance (not saved) so get_totp_uri() works.
    user.two_factor_secret = secret

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
    if not requires_two_factor_for_user(user):
        return Response(
            {'error': 'This account is exempt from operator 2FA.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    otp = request.data.get('otp')
    if not otp:
        return Response({'error': 'OTP not provided.'}, status=status.HTTP_400_BAD_REQUEST)

    pending_secret = cache.get(f"2fa:pending_secret:{user.pk}")
    if not pending_secret:
        return Response(
            {'error': 'No pending 2FA setup found. Call the setup endpoint first.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Temporarily apply the pending secret so verify_totp() uses it.
    user.two_factor_secret = pending_secret
    if not user.verify_totp(otp):
        return Response({'error': 'Invalid OTP.'}, status=status.HTTP_400_BAD_REQUEST)

    # OTP confirmed — now persist the secret and enable 2FA.
    user.is_two_factor_enabled = True
    user.save(update_fields=["two_factor_secret", "is_two_factor_enabled", "updated_at"])
    cache.delete(f"2fa:pending_secret:{user.pk}")

    try:
        from apps.audit.events import log_event as _log_event  # noqa: PLC0415
        _log_event(
            request=request,
            action="modify",
            entity_type="User",
            entity_id=str(user.pk),
            changes={"two_factor_enabled": True},
        )
    except Exception:  # noqa: BLE001
        pass

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
    if not requires_two_factor_for_user(user):
        return Response(
            {'error': 'This account is exempt from operator 2FA.'},
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
    two_factor_required = requires_two_factor_for_user(user)
    return Response(
        {
            "user_type": user.user_type,
            "two_factor_required": two_factor_required,
            "applicant_exempt": not two_factor_required,
            "is_two_factor_enabled": bool(user.is_two_factor_enabled),
            "has_totp_secret": bool(user.two_factor_secret),
            "backup_codes_remaining": len(user.two_factor_backup_codes or []),
        }
    )


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
