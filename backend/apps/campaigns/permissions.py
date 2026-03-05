from apps.core.permissions import (
    IsHRManagerOrAdmin as BaseHRManagerOrAdminPermission,
    is_hr_or_admin_user,
)

class IsHRManagerOrAdmin(BaseHRManagerOrAdminPermission):
    message = "Only HR managers/admin users can access campaigns."
