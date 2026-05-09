from django.urls import path

from resources.api_views import (
    ResourceDetailAPIView,
    ResourceIngestAPIView,
    ResourceListAPIView,
    ResourceSearchAPIView,
    ResourceUploadAPIView,
)

from . import views

app_name = "api"

urlpatterns = [
    path("courses/", views.CourseListView.as_view(), name="course_list"),
    path("courses/<int:pk>/", views.CourseDetailView.as_view(), name="course_detail"),
    path(
        "courses/<int:course_id>/videos/",
        views.CourseVideoListView.as_view(),
        name="course_videos",
    ),
    path(
        "courses/<int:course_id>/quizzes/",
        views.CourseQuizListView.as_view(),
        name="course_quizzes",
    ),
    path(
        "courses/<int:course_id>/ar-tasks/",
        views.CourseARTaskListView.as_view(),
        name="course_ar_tasks",
    ),
    path(
        "videos/<int:video_id>/sections/",
        views.VideoSectionListView.as_view(),
        name="video_sections",
    ),
    path("quizzes/<int:pk>/", views.QuizDetailView.as_view(), name="quiz_detail"),
    path("ar-tasks/<int:pk>/", views.ARTaskDetailView.as_view(), name="ar_task_detail"),
    path(
        "ar-tasks/<int:task_id>/progress/",
        views.ARTaskProgressPostView.as_view(),
        name="ar_task_progress",
    ),
    path("resources/", ResourceListAPIView.as_view(), name="resource_list"),
    path("resources/upload/", ResourceUploadAPIView.as_view(), name="resource_upload"),
    path("resources/search/", ResourceSearchAPIView.as_view(), name="resource_search"),
    path("resources/<int:pk>/", ResourceDetailAPIView.as_view(), name="resource_detail"),
    path("resources/<int:pk>/ingest/", ResourceIngestAPIView.as_view(), name="resource_ingest"),
]
