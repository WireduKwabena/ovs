from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import LoginHistory, PasswordResetToken, User, UserProfile


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ("email",)
    list_display = (
        "email",
        "first_name",
        "last_name",
        "user_type",
        "is_staff",
        "is_active",
        "email_verified",
        "is_two_factor_enabled",
        "created_at",
    )
    list_filter = (
        "user_type",
        "is_staff",
        "is_active",
        "email_verified",
        "is_two_factor_enabled",
        "created_at",
    )
    search_fields = ("email", "first_name", "last_name", "phone_number", "organization")
    readonly_fields = ("created_at", "updated_at", "last_login", "date_joined")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (
            "Personal Info",
            {"fields": ("first_name", "last_name", "phone_number", "organization", "department")},
        ),
        (
            "Account",
            {"fields": ("user_type", "email_verified", "email_verification_token")},
        ),
        (
            "Security",
            {"fields": ("is_two_factor_enabled", "two_factor_secret", "last_login_ip")},
        ),
        (
            "Permissions",
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        (
            "Important Dates",
            {"fields": ("last_login", "date_joined", "created_at", "updated_at")},
        ),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "password1",
                    "password2",
                    "first_name",
                    "last_name",
                    "user_type",
                    "is_staff",
                    "is_active",
                ),
            },
        ),
    )
    filter_horizontal = ("groups", "user_permissions")


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "nationality",
        "current_job_title",
        "years_of_experience",
        "profile_completion_percentage",
        "updated_at",
    )
    list_filter = ("nationality", "country", "updated_at")
    search_fields = ("user__email", "user__first_name", "user__last_name", "current_job_title")
    readonly_fields = ("created_at", "updated_at", "profile_completion_percentage")
    list_select_related = ("user",)


@admin.register(LoginHistory)
class LoginHistoryAdmin(admin.ModelAdmin):
    list_display = ("user", "timestamp", "ip_address", "country", "city", "success")
    list_filter = ("success", "timestamp", "country")
    search_fields = ("user__email", "ip_address", "user_agent", "failure_reason")
    readonly_fields = ("timestamp",)
    list_select_related = ("user",)


@admin.register(PasswordResetToken)
class PasswordResetTokenAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "admin_user", "token", "created_at", "expires_at")
    list_filter = ("created_at", "expires_at")
    search_fields = ("user__email", "admin_user__user__email", "slug")
    readonly_fields = ("id", "token", "created_at")
    list_select_related = ("user", "admin_user", "admin_user__user")
