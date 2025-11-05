from django.contrib.auth.forms import UserCreationForm
from django.urls import path
from . import views
from django.contrib.auth.views import LoginView, LogoutView, PasswordChangeView, PasswordChangeDoneView, PasswordResetView,  PasswordResetDoneView, PasswordResetConfirmView, PasswordResetCompleteView



app_name = 'auth_actions'

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('signup/', views.register_view, name='signup'),

    # Password Actions
    path('password-change/', PasswordChangeView.as_view(template_name='auth_actions/password_change.html'), name='password_change'),
    path('password-change/done/', PasswordChangeDoneView.as_view(template_name='auth_actions/password_change_done.html'), name='password_change_done'),
    path('password-reset/', PasswordResetView.as_view(template_name='auth_actions/password_reset.html'), name='password_reset'),
    path('password-reset/done/', PasswordResetDoneView.as_view(template_name='auth_actions/password_reset_done.html'), name='password_reset_done'),
    path('password-reset/confirm/<uidb64>/<token>/', PasswordResetConfirmView.as_view(template_name='auth_actions/password_reset_confirm.html'), name='password_reset_confirm'),
    path('password-reset/complete/', PasswordResetCompleteView.as_view(template_name='auth_actions/password_reset_complete.html'), name='password_reset_complete'),

]