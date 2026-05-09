from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.generic import DetailView, View

from .models import ARTask, StudentARTaskProgress


class ARTaskDetailView(LoginRequiredMixin, DetailView):
    model = ARTask
    template_name = "ar_tasks/task_detail.html"
    context_object_name = "task"
    pk_url_kwarg = "task_id"

    def get_queryset(self):
        return ARTask.objects.select_related(
            "course",
            "linked_video_section",
            "linked_video_section__video",
        ).prefetch_related("steps")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        progress, _ = StudentARTaskProgress.objects.get_or_create(
            student=self.request.user,
            task=self.object,
            defaults={"status": StudentARTaskProgress.Status.NOT_STARTED},
        )
        ctx["progress"] = progress
        return ctx


class ARTaskProgressUpdateView(LoginRequiredMixin, View):
    """Mark AR task progress from the web UI (POST)."""

    http_method_names = ["post"]

    def post(self, request, course_id, task_id, *args, **kwargs):
        task = get_object_or_404(ARTask, pk=task_id, course_id=course_id)
        status = request.POST.get("status") or StudentARTaskProgress.Status.COMPLETED
        valid = {c[0] for c in StudentARTaskProgress.Status.choices}
        if status not in valid:
            status = StudentARTaskProgress.Status.COMPLETED
        notes = request.POST.get("notes", "")
        obj, _ = StudentARTaskProgress.objects.get_or_create(
            student=request.user,
            task=task,
        )
        obj.status = status
        obj.notes = notes
        obj.save()
        messages.success(request, "Progress updated.")
        return HttpResponseRedirect(
            reverse(
                "ar_tasks:task_detail",
                kwargs={"course_id": course_id, "task_id": task_id},
            )
        )
