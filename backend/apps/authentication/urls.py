# backend/apps/authentication/urls.py

from django.urls import path
try:
    from rest_framework_simplejwt.views import TokenRefreshView
except Exception:
    TokenRefreshView = None
from apps.authentication import views
from apps.users import views as users_views

app_name = 'authentication'

urlpatterns = [
    # Registration & Login
    path('register/', views.RegisterView.as_view(), name='register'),
    path('register/organization-admin/', views.OrganizationAdminRegisterView.as_view(), name='register_organization_admin'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('admin/login/', views.admin_login_view, name='admin_login'),
    path('login/verify/', views.two_factor_verification_view, name='login_verify'),
    path('admin/login/verify/', views.two_factor_verification_view, name='admin_login_verify'),

    # Profile Management (served from users app)
    path('profile/', users_views.profile_view, name='profile'),
    path('profile/update/', users_views.update_profile_view, name='update_profile'),
    path('profile/active-organization/', users_views.set_active_organization_view, name='set_active_organization'),
    
    # Password Management
    path('change-password/', views.change_password_view, name='change_password'),
    path('password-reset/', views.password_reset_request_view, name='password_reset'),
    path('password-reset-confirm/', views.password_reset_confirm_view, name='password_reset_confirm'),

    # Tenant resolution — accessible from both tenant and public URL confs
    path('resolve-tenant/', views.ResolveTenantView.as_view(), name='resolve_tenant'),

    # 2FA Management
    path('admin/2fa/setup/', views.two_factor_setup_view, name='admin_2fa_setup'),
    path('admin/2fa/enable/', views.two_factor_enable_view, name='admin_2fa_enable'),
    path('2fa/status/', views.two_factor_status_view, name='two_factor_status'),
    path(
        '2fa/backup-codes/regenerate/',
        views.two_factor_backup_codes_regenerate_view,
        name='two_factor_backup_codes_regenerate',
    ),
]

if TokenRefreshView:
    urlpatterns += [
        path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    ]
