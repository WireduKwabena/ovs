"""Compatibility layer for legacy ``apps.auth_actions`` imports."""

from apps.authentication.models import User
from apps.authentication.permissions import IsAdminUser

# Backward-compatible alias. Current project uses a unified User model.
AdminUser = User

__all__ = ["User", "AdminUser", "IsAdminUser"]
