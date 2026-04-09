"""
Custom authentication backends that bypass tenant-scoped user lookups.

The TenantAwareUserManager on User.objects automatically restricts querysets
to members of the current tenant schema.  That's the right default for view
/service layer code, but authentication itself must be able to locate *any*
user by credentials or token — the authorization check (does this user have a
membership/role in the current tenant?) happens at the permission layer, not
during identity verification.

Both backends use User.all_objects, the unscoped manager, so that:
  • login works for users regardless of membership state
  • JWT token validation works even before OrganizationMembership is populated
  • tests that don't create memberships still pass
"""

from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model


class AllUsersModelBackend(ModelBackend):
    """
    Drop-in replacement for ModelBackend that resolves users via the
    unscoped ``all_objects`` manager.

    Without this override, Django's default ModelBackend calls
    ``User._default_manager.get_by_natural_key(username)``, which goes through
    TenantAwareUserManager and filters by OrganizationMembership — causing
    login to fail for any user who does not yet have a membership record
    (applicants, newly invited users, users during first-time setup).
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        UserModel = get_user_model()
        if username is None:
            username = kwargs.get(UserModel.USERNAME_FIELD)
        if username is None or password is None:
            return None
        try:
            user = UserModel.all_objects.get_by_natural_key(username)
        except UserModel.DoesNotExist:
            # Run the default password hasher to mitigate timing attacks.
            UserModel().set_password(password)
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None

    def get_user(self, user_id):
        UserModel = get_user_model()
        try:
            user = UserModel.all_objects.get(pk=user_id)
        except UserModel.DoesNotExist:
            return None
        return user if self.user_can_authenticate(user) else None


try:
    from rest_framework_simplejwt.authentication import JWTAuthentication

    class AllUsersJWTAuthentication(JWTAuthentication):
        """
        JWTAuthentication subclass that resolves the authenticated user via
        the unscoped ``all_objects`` manager.

        SimpleJWT's default ``get_user()`` calls ``User.objects.get(pk=…)``,
        which is now tenant-scoped.  Every authenticated API request in a
        tenant context would raise DoesNotExist for users without a
        matching OrganizationMembership — producing a spurious 401.
        """

        def get_user(self, validated_token):
            from rest_framework_simplejwt.settings import api_settings
            from rest_framework_simplejwt.exceptions import InvalidToken
            from django.utils.translation import gettext_lazy as _

            UserModel = get_user_model()
            try:
                user_id = validated_token[api_settings.USER_ID_CLAIM]
            except KeyError:
                raise InvalidToken(_("Token contained no recognisable user identification"))

            try:
                user = UserModel.all_objects.get(
                    **{api_settings.USER_ID_FIELD: user_id}
                )
            except UserModel.DoesNotExist:
                raise InvalidToken(_("User not found"))

            if not user.is_active:
                raise InvalidToken(_("User is inactive"))

            return user

except ImportError:  # pragma: no cover — simplejwt is an optional dependency
    pass
