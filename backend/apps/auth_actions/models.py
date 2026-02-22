"""Compatibility aliases for legacy auth_actions.models imports."""

from apps.authentication.models import User

AdminUser = User

__all__ = ["User", "AdminUser"]
