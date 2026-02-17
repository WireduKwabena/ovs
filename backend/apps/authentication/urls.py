# backend/apps/authentication/urls.py

from django.urls import path
try:
    from rest_framework_simplejwt.views import TokenRefreshView
except Exception:
    TokenRefreshView = None
from apps.authentication.views import views
try:
    from apps.authentication.views import oauth_views
except Exception:
    oauth_views = None

app_name = 'authentication'

urlpatterns = [
    # Registration & Login
    path('register/', views.RegisterView.as_view(), name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('admin/login/', views.admin_login_view, name='admin_login'),
    path('admin/login/verify/', views.two_factor_verification_view, name='admin_login_verify'),
    
    # Profile Management
    path('profile/', views.profile_view, name='profile'),
    path('profile/update/', views.update_profile_view, name='update_profile'),
    
    # Password Management
    path('change-password/', views.change_password_view, name='change_password'),
    path('password-reset/', views.password_reset_request_view, name='password_reset'),
    path('password-reset-confirm/', views.password_reset_confirm_view, name='password_reset_confirm'),

    # 2FA Management
    path('admin/2fa/setup/', views.two_factor_setup_view, name='admin_2fa_setup'),
    path('admin/2fa/enable/', views.two_factor_enable_view, name='admin_2fa_enable'),
]

if TokenRefreshView:
    urlpatterns += [
        path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    ]

if oauth_views:
    urlpatterns += [
        path("google/login/", oauth_views.GoogleLoginView.as_view(), name="google-login"),
        path("github/login/", oauth_views.GitHubLoginView.as_view(), name="github-login"),
    ]
