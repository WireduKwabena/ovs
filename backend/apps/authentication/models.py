"""
Authentication Models
=====================
User management models for the AI Vetting System.

Academic Note:
--------------
Implements role-based access control (RBAC) with three user types:
1. HR Managers (can create vetting processes, review results)
2. Applicants (can submit documents, take interviews)
3. System Admins (full access)
"""

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.core.validators import RegexValidator
from django.utils import timezone
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from datetime import timedelta
import uuid
try:
    import pyotp
except ImportError:  # pragma: no cover - dependency may be optional in some setups
    pyotp = None


class CustomUserManager(BaseUserManager):
    """Custom user manager for email-based authentication."""
    
    def create_user(self, email, password=None, **extra_fields):
        """Create and save a regular user."""
        if not email:
            raise ValueError(_('Email address is required'))
        
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, email, password=None, **extra_fields):
        """Create and save a superuser."""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('user_type', 'admin')
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError(_('Superuser must have is_staff=True'))
        if extra_fields.get('is_superuser') is not True:
            raise ValueError(_('Superuser must have is_superuser=True'))
        
        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    """
    Custom User model with email authentication.
    
    Extends Django's AbstractUser to use email as username field
    and add role-based access control.
    """
    
    USER_TYPE_CHOICES = [
        ('admin', 'System Administrator'),
        ('hr_manager', 'HR Manager'),
        ('applicant', 'Applicant'),
    ]
    
    # Override username field
    username = None
    email = models.EmailField(
        _('email address'),
        unique=True,
        db_index=True,
        error_messages={
            'unique': _('A user with that email already exists.'),
        }
    )
    
    # User type
    user_type = models.CharField(
        max_length=20,
        choices=USER_TYPE_CHOICES,
        default='applicant',
        db_index=True
    )
    
    # Profile information
    phone_number = models.CharField(
        max_length=20,
        blank=True,
        validators=[
            RegexValidator(
                regex=r'^\+?1?\d{9,15}$',
                message='Phone number must be in format: +999999999'
            )
        ]
    )
    organization = models.CharField(max_length=200, blank=True)
    department = models.CharField(max_length=100, blank=True)
    
    # Account status
    email_verified = models.BooleanField(default=False)
    email_verification_token = models.CharField(max_length=100, blank=True)
    
    # 2FA fields
    is_two_factor_enabled = models.BooleanField(default=False)
    two_factor_secret = models.CharField(max_length=32, blank=True, null=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)
    
    objects = CustomUserManager()
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['email', 'user_type']),
            models.Index(fields=['created_at']),
        ]
        verbose_name = _('User')
        verbose_name_plural = _('Users')
    
    def __str__(self):
        return f"{self.get_full_name()} ({self.email})"
    
    @property
    def is_hr_manager(self):
        """Check if user is HR manager."""
        return self.user_type in ['hr_manager', 'admin']
    
    @property
    def is_applicant(self):
        """Check if user is applicant."""
        return self.user_type == 'applicant'
    
    def get_full_name(self):
        """Return full name."""
        return f"{self.first_name} {self.last_name}".strip() or self.email

    def get_totp_uri(self, issuer_name="OVS-Redo"):
        if not self.two_factor_secret or pyotp is None:
            return None
        return pyotp.totp.TOTP(self.two_factor_secret).provisioning_uri(name=self.email, issuer_name=issuer_name)

    def verify_totp(self, token):
        if not self.two_factor_secret or pyotp is None:
            return False
        totp = pyotp.TOTP(self.two_factor_secret)
        return totp.verify(token)


class UserProfile(models.Model):
    """
    Extended user profile information.
    
    Stores additional information not directly related to authentication
    but useful for the vetting process.
    """
    
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='profile'
    )
    
    # Personal information
    date_of_birth = models.DateField(null=True, blank=True)
    nationality = models.CharField(max_length=100, blank=True)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    
    # Professional information
    current_job_title = models.CharField(max_length=200, blank=True)
    years_of_experience = models.IntegerField(null=True, blank=True)
    linkedin_url = models.URLField(blank=True)
    
    # Profile completion
    profile_completion_percentage = models.IntegerField(default=0)
    
    # Metadata
    bio = models.TextField(blank=True, max_length=500)
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _('User Profile')
        verbose_name_plural = _('User Profiles')
    
    def __str__(self):
        return f"Profile: {self.user.get_full_name()}"
    
    def calculate_completion(self):
        """Calculate profile completion percentage."""
        fields = [
            self.date_of_birth,
            self.nationality,
            self.address,
            self.city,
            self.country,
            self.current_job_title,
            self.years_of_experience,
            self.bio,
        ]
        filled = sum(1 for field in fields if field)
        self.profile_completion_percentage = int((filled / len(fields)) * 100)
        return self.profile_completion_percentage


class LoginHistory(models.Model):
    """
    Track user login history for security auditing.
    
    Academic Note:
    --------------
    Important for security analysis and anomaly detection
    in user behavior patterns.
    """
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='login_history'
    )
    
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    
    # Location (optional - can be derived from IP)
    country = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100, blank=True)
    
    # Success/Failure
    success = models.BooleanField(default=True)
    failure_reason = models.CharField(max_length=200, blank=True)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', '-timestamp']),
        ]
        verbose_name = _('Login History')
        verbose_name_plural = _('Login Histories')
    
    def __str__(self):
        return f"{self.user.email} - {self.timestamp}"


class PasswordResetToken(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    slug = models.SlugField("Slug Field", max_length=255, null=True, blank=False)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="password_reset_tokens", null=True
    )
    admin_user = models.ForeignKey(
        UserProfile, on_delete=models.CASCADE, related_name="password_reset_tokens", null=True
    )
    token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(
                hours=1
            )  # Token expires in 1 hour
        if not self.slug:
            self.slug = slugify(f"token - {str(self.id)[:8]}")
        super().save(*args, **kwargs)

    def is_valid(self):
        return timezone.now() <= self.expires_at

    class Meta:
        verbose_name = "Password Reset Token"
        verbose_name_plural = "Password Reset Tokens"
        indexes = [models.Index(fields=["user", "token"])]

    def __str__(self):
        return f"Token for {self.user.get_full_name()} (Expires: {self.expires_at})"
