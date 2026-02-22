from rest_framework.permissions import BasePermission

from apps.core.security import has_valid_service_token

from .services import resolve_candidate_access_session


class HasCandidateAccessSession(BasePermission):
    message = "Candidate access session is required."

    def has_permission(self, request, view):
        session_key = request.session.get("candidate_access_session_key")
        candidate_session = resolve_candidate_access_session(session_key)
        if candidate_session is None:
            request.session.pop("candidate_access_session_key", None)
            return False
        request.candidate_access_session = candidate_session
        return True


class IsAuthenticatedOrCandidateAccessSession(BasePermission):
    message = "Authentication, service token, or candidate access session is required."

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        if user and user.is_authenticated:
            return True
        if has_valid_service_token(request):
            request.service_authenticated = True
            return True
        return HasCandidateAccessSession().has_permission(request, view)
