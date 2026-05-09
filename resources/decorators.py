"""
Reusable teacher guard for function-based views.

Class-based views should prefer accounts.mixins.TeacherRequiredMixin.
"""

from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.http import HttpResponseForbidden

from accounts.models import Profile


def teacher_required(view_func):
    """Allow staff/superuser or profile.role == teacher only."""

    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        user = request.user
        if not user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if user.is_superuser or user.is_staff:
            return view_func(request, *args, **kwargs)
        profile = getattr(user, "profile", None)
        if profile and profile.role == Profile.Role.TEACHER:
            return view_func(request, *args, **kwargs)
        return HttpResponseForbidden("Teachers only.")

    return _wrapped
