from rest_framework.permissions import BasePermission

from apps.core.permissions import (
    get_request_active_organization_id,
    is_admin_user,
    is_government_workflow_operator,
)


class IsMeetingCreatorOrReadOnly(BasePermission):
    message = "Only authorized internal actors can create or modify video meetings."

    def has_permission(self, request, view):
        if request.method in {"GET", "HEAD", "OPTIONS"}:
            return bool(getattr(request, "user", None) and request.user.is_authenticated)
        return is_government_workflow_operator(
            getattr(request, "user", None),
            organization_id=get_request_active_organization_id(request),
        )

    def has_object_permission(self, request, view, obj):
        user = getattr(request, "user", None)
        if request.method in {"GET", "HEAD", "OPTIONS"}:
            return (
                is_government_workflow_operator(user)
                or obj.organizer_id == getattr(user, "id", None)
                or obj.has_participant(user)
            )

        return is_government_workflow_operator(user) and (
            obj.organizer_id == getattr(user, "id", None) or getattr(user, "is_superuser", False)
        )
