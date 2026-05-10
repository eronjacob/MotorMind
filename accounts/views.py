from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView, LogoutView
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.generic import TemplateView

from courses.models import Course
from quizzes.models import QuizAttempt

from .forms import BootstrapAuthenticationForm
from .manage_views import (
    quiz_attempts_for_teacher_panel,
    user_can_delete_quiz_attempt,
    user_can_manage_course,
)
from .mixins import TeacherRequiredMixin


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CarHootLoginView(LoginView):
    """Ensure csrftoken cookie is always set on GET so POST login succeeds in all browsers."""

    template_name = "accounts/login.html"
    authentication_form = BootstrapAuthenticationForm
    redirect_authenticated_user = True


class CarHootLogoutView(LogoutView):
    next_page = reverse_lazy("courses:landing")


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "accounts/dashboard.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        profile = getattr(user, "profile", None)
        ctx["profile"] = profile

        if profile and profile.role == "teacher":
            ctx["courses_managed"] = Course.objects.filter(created_by=user).order_by(
                "-created_at"
            )[:10]
            ctx["recent_quiz_attempts"] = list(
                quiz_attempts_for_teacher_panel(user, limit=15)
            )
        else:
            ctx["courses_available"] = Course.objects.order_by("-created_at")
            ctx["my_quiz_attempts"] = (
                QuizAttempt.objects.filter(student=user)
                .select_related("quiz", "quiz__course")
                .order_by("-created_at")[:20]
            )
        return ctx


class AdminPanelView(TeacherRequiredMixin, TemplateView):
    """Teacher dashboard: quick links + light-weight create shortcuts."""

    template_name = "accounts/admin_panel.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        base = Course.objects.select_related("created_by").order_by("-created_at")[:200]
        ctx["courses_rows"] = [
            {"course": c, "can_manage": user_can_manage_course(user, c)}
            for c in base
        ]
        attempts = list(quiz_attempts_for_teacher_panel(user, limit=50))
        ctx["recent_quiz_attempt_rows"] = [
            {"attempt": a, "can_delete": user_can_delete_quiz_attempt(user, a)}
            for a in attempts
        ]
        return ctx
