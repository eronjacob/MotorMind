from django.urls import path

from . import views

app_name = "ar_tasks"

urlpatterns = [
    path(
        "courses/<int:course_id>/ar-tasks/<int:task_id>/",
        views.ARTaskDetailView.as_view(),
        name="task_detail",
    ),
    path(
        "courses/<int:course_id>/ar-tasks/<int:task_id>/progress/",
        views.ARTaskProgressUpdateView.as_view(),
        name="task_progress",
    ),
]
