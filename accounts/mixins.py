from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin

from .models import Profile


class TeacherRequiredMixin(UserPassesTestMixin):
    """Allow staff/superuser or users with teacher profile role."""

    def test_func(self):
        user = self.request.user
        if not user.is_authenticated:
            return False
        if user.is_superuser or user.is_staff:
            return True
        profile = getattr(user, "profile", None)
        return profile is not None and profile.role == Profile.Role.TEACHER
