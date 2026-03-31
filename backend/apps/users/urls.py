from django.urls import path

from apps.users import views

app_name = "users"

urlpatterns = [
    # User profile — also accessible at /auth/profile/ for backward compatibility
    path("profile/", views.profile_view, name="profile"),
    path("profile/update/", views.update_profile_view, name="update_profile"),
    path("profile/active-organization/", views.set_active_organization_view, name="set_active_organization"),
]