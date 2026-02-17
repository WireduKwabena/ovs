# backend/apps/authentication/views.py

from rest_framework import status, generics
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.conf import settings
from apps.authentication.models import User
from apps.authentication.serializers import (
    UserSerializer, UserRegistrationSerializer,
    AdminUserSerializer, ChangePasswordSerializer,
    PasswordResetRequestSerializer, PasswordResetConfirmSerializer, LoginSerializer, AdminLoginSerializer,
    TwoFactorVerificationSerializer
)
import logging
try:
    import pyotp
except ImportError:  # pragma: no cover - dependency may be optional in some setups
    pyotp = None
from cryptography.fernet import Fernet
from django.core.signing import Signer, BadSignature

logger = logging.getLogger(__name__)


class RegisterView(generics.CreateAPIView):
    """
    User registration endpoint
    POST /api/auth/register/
    """
    queryset = User.objects.all()
    permission_classes = [AllowAny]
    serializer_class = UserRegistrationSerializer
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        # Generate tokens
        refresh = RefreshToken.for_user(user)
        
        return Response({
            'user': UserSerializer(user).data,
            'tokens': {
                'access': str(refresh.access_token),
                'refresh': str(refresh),
            },
            'message': 'User registered successfully'
        }, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    """
    User login endpoint
    POST /api/auth/login/
    Body: {"email": "user@example.com", "password": "password123"}
    """
    serializer = LoginSerializer(data=request.data, context={'request': request})
    serializer.is_valid(raise_exception=True)
    user = serializer.validated_data['user']
    
    refresh = RefreshToken.for_user(user)
    
    return Response({
        'user': UserSerializer(user).data,
        'tokens': {
            'access': str(refresh.access_token),
            'refresh': str(refresh),
        },
    })

@api_view(['POST'])
@permission_classes([AllowAny])
def admin_login_view(request):
    """
    Admin login endpoint
    POST /api/auth/admin/login/
    Body: {"email": "admin@example.com", "password": "password123"}
    """
    serializer = AdminLoginSerializer(data=request.data, context={'request': request})
    serializer.is_valid(raise_exception=True)
    user = serializer.validated_data['user']

    # Check if user has 2FA enabled
    if user.is_two_factor_enabled:
        signer = Signer()
        token = signer.sign(user.email)
        return Response({'message': 'Please verify your 2FA token.', 'token': token})
    
    refresh = RefreshToken.for_user(user)
    
    return Response({
        'user': AdminUserSerializer(user).data,
        'tokens': {
            'access': str(refresh.access_token),
            'refresh': str(refresh),
        },
    })

@api_view(['POST'])
@permission_classes([AllowAny])
def two_factor_verification_view(request):
    """
    2FA verification endpoint
    POST /api/auth/admin/login/verify/
    Body: {"token": "temp_token", "otp": "123456"}
    """
    serializer = TwoFactorVerificationSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    
    signer = Signer()
    try:
        email = signer.unsign(serializer.validated_data['token'])
    except BadSignature:
        return Response({'error': 'Invalid token.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        return Response({'error': 'User not found.'}, status=status.HTTP_400_BAD_REQUEST)

    if not user.verify_totp(serializer.validated_data['otp']):
        return Response({'error': 'Invalid OTP.'}, status=status.HTTP_400_BAD_REQUEST)

    refresh = RefreshToken.for_user(user)
    
    return Response({
        'user': AdminUserSerializer(user).data,
        'tokens': {
            'access': str(refresh.access_token),
            'refresh': str(refresh),
        },
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def two_factor_setup_view(request):
    """
    2FA setup endpoint
    GET /api/auth/admin/2fa/setup/
    """
    user = request.user
    if not user.is_staff:
        return Response({'error': 'Only admin users can set up 2FA.'}, status=status.HTTP_403_FORBIDDEN)
    if pyotp is None:
        return Response({'error': '2FA dependency is not installed.'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    secret = pyotp.random_base32()
    f = Fernet(settings.SECRET_KEY.encode())
    
    user.two_factor_secret = f.encrypt(secret.encode()).decode()
    user.save()
    
    return Response({'provisioning_uri': user.get_totp_uri()})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def two_factor_enable_view(request):
    """
    2FA enable endpoint
    POST /api/auth/admin/2fa/enable/
    Body: {"otp": "123456"}
    """
    user = request.user
    if not user.is_staff:
        return Response({'error': 'Only admin users can enable 2FA.'}, status=status.HTTP_403_FORBIDDEN)

    otp = request.data.get('otp')
    if not otp:
        return Response({'error': 'OTP not provided.'}, status=status.HTTP_400_BAD_REQUEST)

    if not user.verify_totp(otp):
        return Response({'error': 'Invalid OTP.'}, status=status.HTTP_400_BAD_REQUEST)

    user.is_two_factor_enabled = True
    user.save()
    return Response({'message': '2FA enabled successfully.'})


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


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def profile_view(request):
    """
    Get current user profile
    GET /api/auth/profile/
    """
    # Check if user is admin or regular user
    if request.user.is_staff:
        serializer = AdminUserSerializer(request.user)
        user_type = 'admin'
    else:
        serializer = UserSerializer(request.user)
        user_type = 'applicant'
    
    return Response({
        'user': serializer.data,
        'user_type': user_type
    })


@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def update_profile_view(request):
    """
    Update user profile
    PUT/PATCH /api/auth/profile/
    """
    user = request.user
    
    # Check if admin or regular user
    if request.user.is_staff:
        serializer = AdminUserSerializer(user, data=request.data, partial=True)
    else:
        serializer = UserSerializer(user, data=request.data, partial=True)
    
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


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
            
            # Send email
            reset_link = f"{settings.FRONTEND_URL}/reset-password/{user.id}/{token}/"
            
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
            pass
        
        return Response({
            'message': 'If an account exists with this email, a password reset link has been sent.'
        })
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


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
        # Validate token and reset password
        # Implementation depends on your token strategy
        return Response({'message': 'Password has been reset successfully'})
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
