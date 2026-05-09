from rest_framework.permissions import BasePermission

from accounts.models import Profile


class IsStudentUser(BasePermission):
    """Allow only student role (or staff for debugging)."""

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser or user.is_staff:
            return True
        profile = getattr(user, "profile", None)
        return profile is not None and profile.role == Profile.Role.STUDENT


class IsTeacherUser(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser or user.is_staff:
            return True
        profile = getattr(user, "profile", None)
        return profile is not None and profile.role == Profile.Role.TEACHER
