from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView, LogoutView
from django.urls import reverse_lazy
from django.views.generic import TemplateView

from ar_tasks.models import StudentARTaskProgress
from courses.models import Course
from quizzes.models import QuizAttempt

from .forms import BootstrapAuthenticationForm
from .mixins import TeacherRequiredMixin


class CarHootLoginView(LoginView):
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
            ctx["recent_quiz_attempts"] = (
                QuizAttempt.objects.select_related("quiz", "student")
                .order_by("-created_at")[:15]
            )
            ctx["recent_ar_progress"] = (
                StudentARTaskProgress.objects.select_related("task", "student")
                .order_by("-updated_at")[:15]
            )
        else:
            ctx["courses_available"] = Course.objects.order_by("-created_at")
            ctx["my_quiz_attempts"] = (
                QuizAttempt.objects.filter(student=user)
                .select_related("quiz", "quiz__course")
                .order_by("-created_at")[:20]
            )
            ctx["my_ar_progress"] = (
                StudentARTaskProgress.objects.filter(student=user)
                .select_related("task", "task__course")
                .order_by("-updated_at")
            )
        return ctx


class AdminPanelView(TeacherRequiredMixin, TemplateView):
    """Teacher dashboard: quick links + light-weight create shortcuts."""

    template_name = "accounts/admin_panel.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        base = Course.objects.select_related("created_by").order_by("-created_at")
        if user.is_superuser or user.is_staff:
            ctx["courses"] = base[:30]
        else:
            ctx["courses"] = base.filter(created_by=user)[:30]
        ctx["recent_quiz_attempts"] = QuizAttempt.objects.select_related(
            "quiz", "student"
        ).order_by("-created_at")[:20]
        ctx["recent_ar_progress"] = StudentARTaskProgress.objects.select_related(
            "task", "student"
        ).order_by("-updated_at")[:20]
        return ctx
