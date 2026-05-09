from django.contrib import messages
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.generic import CreateView, UpdateView

from ar_tasks.models import ARTask, ARTaskStep
from courses.models import Course, TrainingVideo, VideoSection
from quizzes.models import AnswerChoice, Question, Quiz

from .forms import (
    AnswerChoiceForm,
    ARTaskForm,
    ARTaskStepForm,
    CourseForm,
    QuestionForm,
    QuizForm,
    TrainingVideoForm,
    VideoSectionForm,
)
from .mixins import TeacherRequiredMixin


class BaseManageCreateView(TeacherRequiredMixin, CreateView):
    """Teacher create views: default cancel returns to admin panel."""

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.setdefault("cancel_url", reverse("accounts:admin_panel"))
        return ctx


class NestedCourseManageMixin:
    """Require `course_pk` in URL; course must belong to the current teacher."""

    course_pk_url_kwarg = "course_pk"

    def dispatch(self, request, *args, **kwargs):
        cid = int(kwargs[self.course_pk_url_kwarg])
        qs = Course.objects.all()
        if not (request.user.is_superuser or request.user.is_staff):
            qs = qs.filter(created_by=request.user)
        self.nested_course = get_object_or_404(qs, pk=cid)
        self.nested_course_id = cid
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["cancel_url"] = reverse("accounts:manage_course", kwargs={"pk": self.nested_course_id})
        return ctx

    def get_success_url(self):
        return reverse("accounts:manage_course", kwargs={"pk": self.nested_course_id})


class CourseHubView(TeacherRequiredMixin, UpdateView):
    """
    Edit course metadata and jump off to add videos, sections, quizzes, AR tasks
    scoped to this course.
    """

    model = Course
    form_class = CourseForm
    template_name = "accounts/manage/course_hub.html"
    context_object_name = "course"

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser or user.is_staff:
            return Course.objects.all()
        return Course.objects.filter(created_by=user)

    def get_success_url(self):
        return reverse("accounts:manage_course", kwargs={"pk": self.object.pk})

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        course = self.object
        ctx["videos"] = course.videos.prefetch_related("sections").order_by("created_at")
        ctx["quizzes"] = course.quizzes.prefetch_related("questions").order_by("pk")
        ctx["ar_tasks"] = course.ar_tasks.order_by("pk")
        ctx["cancel_url"] = reverse("accounts:admin_panel")
        return ctx

    def form_valid(self, form):
        messages.success(self.request, "Course saved.")
        return super().form_valid(form)


class CourseCreateView(BaseManageCreateView):
    form_class = CourseForm
    template_name = "accounts/manage/course_form.html"

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, "Course created — add videos, quizzes, and AR tasks below.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("accounts:manage_course", kwargs={"pk": self.object.pk})


class TrainingVideoCreateView(BaseManageCreateView):
    form_class = TrainingVideoForm
    template_name = "accounts/manage/training_video_form.html"

    def get_success_url(self):
        return reverse("accounts:admin_panel")


class NestedTrainingVideoCreateView(NestedCourseManageMixin, BaseManageCreateView):
    form_class = TrainingVideoForm
    template_name = "accounts/manage/training_video_form.html"

    def get_initial(self):
        return {**super().get_initial(), "course": self.nested_course_id}

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields["course"].queryset = Course.objects.filter(pk=self.nested_course_id)
        return form

    def form_valid(self, form):
        messages.success(self.request, "Video added.")
        return super().form_valid(form)


class VideoSectionCreateView(BaseManageCreateView):
    form_class = VideoSectionForm
    template_name = "accounts/manage/video_section_form.html"

    def get_success_url(self):
        return reverse("accounts:admin_panel")


class NestedVideoSectionCreateView(NestedCourseManageMixin, BaseManageCreateView):
    form_class = VideoSectionForm
    template_name = "accounts/manage/video_section_form.html"

    def get_initial(self):
        initial = super().get_initial()
        vid = self.request.GET.get("video")
        if vid and str(vid).isdigit():
            vpk = int(vid)
            if TrainingVideo.objects.filter(pk=vpk, course_id=self.nested_course_id).exists():
                initial["video"] = vpk
        return initial

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields["video"].queryset = TrainingVideo.objects.filter(course_id=self.nested_course_id)
        return form

    def form_valid(self, form):
        messages.success(self.request, "Section added.")
        return super().form_valid(form)


class QuizCreateView(BaseManageCreateView):
    form_class = QuizForm
    template_name = "accounts/manage/quiz_form.html"

    def get_success_url(self):
        return reverse("accounts:admin_panel")


class NestedQuizCreateView(NestedCourseManageMixin, BaseManageCreateView):
    form_class = QuizForm
    template_name = "accounts/manage/quiz_form.html"

    def get_initial(self):
        return {**super().get_initial(), "course": self.nested_course_id}

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields["course"].queryset = Course.objects.filter(pk=self.nested_course_id)
        return form

    def form_valid(self, form):
        messages.success(self.request, "Quiz added.")
        return super().form_valid(form)


class QuestionCreateView(BaseManageCreateView):
    form_class = QuestionForm
    template_name = "accounts/manage/question_form.html"

    def get_success_url(self):
        return reverse("accounts:admin_panel")


class NestedQuestionCreateView(NestedCourseManageMixin, BaseManageCreateView):
    form_class = QuestionForm
    template_name = "accounts/manage/question_form.html"

    def get_initial(self):
        initial = super().get_initial()
        qid = self.request.GET.get("quiz")
        if qid and str(qid).isdigit():
            qpk = int(qid)
            if Quiz.objects.filter(pk=qpk, course_id=self.nested_course_id).exists():
                initial["quiz"] = qpk
        return initial

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields["quiz"].queryset = Quiz.objects.filter(course_id=self.nested_course_id)
        form.fields["section"].queryset = VideoSection.objects.filter(video__course_id=self.nested_course_id)
        return form

    def form_valid(self, form):
        messages.success(self.request, "Question added.")
        return super().form_valid(form)


class AnswerChoiceCreateView(BaseManageCreateView):
    form_class = AnswerChoiceForm
    template_name = "accounts/manage/answer_choice_form.html"

    def get_success_url(self):
        return reverse("accounts:admin_panel")


class NestedAnswerChoiceCreateView(NestedCourseManageMixin, BaseManageCreateView):
    form_class = AnswerChoiceForm
    template_name = "accounts/manage/answer_choice_form.html"

    def get_initial(self):
        initial = super().get_initial()
        qid = self.request.GET.get("question")
        if qid and str(qid).isdigit():
            qpk = int(qid)
            if Question.objects.filter(pk=qpk, quiz__course_id=self.nested_course_id).exists():
                initial["question"] = qpk
        return initial

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields["question"].queryset = Question.objects.filter(quiz__course_id=self.nested_course_id)
        return form

    def form_valid(self, form):
        messages.success(self.request, "Answer choice added.")
        return super().form_valid(form)


class ARTaskCreateView(BaseManageCreateView):
    form_class = ARTaskForm
    template_name = "accounts/manage/ar_task_form.html"

    def get_success_url(self):
        return reverse("accounts:admin_panel")


class NestedARTaskCreateView(NestedCourseManageMixin, BaseManageCreateView):
    form_class = ARTaskForm
    template_name = "accounts/manage/ar_task_form.html"

    def get_initial(self):
        return {**super().get_initial(), "course": self.nested_course_id}

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields["course"].queryset = Course.objects.filter(pk=self.nested_course_id)
        form.fields["linked_video_section"].queryset = VideoSection.objects.filter(
            video__course_id=self.nested_course_id
        )
        return form

    def form_valid(self, form):
        messages.success(self.request, "AR task added.")
        return super().form_valid(form)


class ARTaskStepCreateView(BaseManageCreateView):
    form_class = ARTaskStepForm
    template_name = "accounts/manage/ar_task_step_form.html"

    def get_success_url(self):
        return reverse("accounts:admin_panel")


class NestedARTaskStepCreateView(NestedCourseManageMixin, BaseManageCreateView):
    form_class = ARTaskStepForm
    template_name = "accounts/manage/ar_task_step_form.html"

    def get_initial(self):
        initial = super().get_initial()
        tid = self.request.GET.get("task")
        if tid and str(tid).isdigit():
            tpk = int(tid)
            if ARTask.objects.filter(pk=tpk, course_id=self.nested_course_id).exists():
                initial["task"] = tpk
        return initial

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields["task"].queryset = ARTask.objects.filter(course_id=self.nested_course_id)
        return form

    def form_valid(self, form):
        messages.success(self.request, "AR step added.")
        return super().form_valid(form)
