# Ensure proper permissions for rubric management
from rest_framework.permissions import BasePermission

class IsHRManager(BasePermission):
    """Only HR managers can create/edit rubrics"""
    
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in ['hr_manager', 'admin']

class CanOverrideScores(BasePermission):
    """Only authorized users can override scores"""
    
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in ['hr_manager', 'reviewer', 'admin']