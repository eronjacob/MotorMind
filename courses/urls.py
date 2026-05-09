from django.urls import path

from . import views

app_name = "courses"

urlpatterns = [
    path("", views.LandingView.as_view(), name="landing"),
    path("courses/", views.CourseListView.as_view(), name="course_list"),
    path("courses/<int:pk>/", views.CourseDetailView.as_view(), name="course_detail"),
    path(
        "courses/<int:course_id>/videos/<int:video_id>/",
        views.VideoDetailView.as_view(),
        name="video_detail",
    ),
]
