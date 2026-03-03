from rest_framework.permissions import BasePermission


def is_hr_or_admin_user(user) -> bool:
    return bool(
        getattr(user, "is_authenticated", False)
        and (
            getattr(user, "is_staff", False)
            or getattr(user, "is_superuser", False)
            or getattr(user, "user_type", None) in {"admin", "hr_manager"}
        )
    )


class IsMeetingCreatorOrReadOnly(BasePermission):
    message = "Only HR/admin users can create or modify video meetings."

    def has_permission(self, request, view):
        if request.method in {"GET", "HEAD", "OPTIONS"}:
            return bool(getattr(request, "user", None) and request.user.is_authenticated)
        return is_hr_or_admin_user(getattr(request, "user", None))

    def has_object_permission(self, request, view, obj):
        user = getattr(request, "user", None)
        if request.method in {"GET", "HEAD", "OPTIONS"}:
            return (
                is_hr_or_admin_user(user)
                or obj.organizer_id == getattr(user, "id", None)
                or obj.has_participant(user)
            )

        return is_hr_or_admin_user(user) and (
            obj.organizer_id == getattr(user, "id", None) or getattr(user, "is_superuser", False)
        )

