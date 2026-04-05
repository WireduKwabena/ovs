"""Compatibility aliases for legacy auth_actions.models imports."""

from apps.users.models import User

AdminUser = User

__all__ = ["User", "AdminUser"]
