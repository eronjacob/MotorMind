from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ar_tasks.models import ARTask, StudentARTaskProgress
from courses.models import Course, TrainingVideo, VideoSection
from quizzes.models import Quiz

from .permissions import IsStudentUser
from .serializers import (
    ARTaskDetailSerializer,
    ARTaskListSerializer,
    CourseDetailSerializer,
    CourseListSerializer,
    QuizDetailSerializer,
    QuizListSerializer,
    StudentARTaskProgressReadSerializer,
    StudentARTaskProgressWriteSerializer,
    TrainingVideoListSerializer,
    VideoSectionSerializer,
)


class CourseListView(generics.ListAPIView):
    queryset = Course.objects.all().order_by("-created_at")
    serializer_class = CourseListSerializer
    permission_classes = [IsAuthenticated]


class CourseDetailView(generics.RetrieveAPIView):
    queryset = Course.objects.prefetch_related(
        "videos__sections",
        "quizzes",
        "ar_tasks",
    )
    serializer_class = CourseDetailSerializer
    permission_classes = [IsAuthenticated]


class CourseVideoListView(generics.ListAPIView):
    serializer_class = TrainingVideoListSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        cid = self.kwargs["course_id"]
        return TrainingVideo.objects.filter(course_id=cid).order_by("created_at")


class VideoSectionListView(generics.ListAPIView):
    serializer_class = VideoSectionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        vid = self.kwargs["video_id"]
        return VideoSection.objects.filter(video_id=vid).order_by("order", "pk")


class CourseQuizListView(generics.ListAPIView):
    serializer_class = QuizListSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        cid = self.kwargs["course_id"]
        return Quiz.objects.filter(course_id=cid).order_by("pk")


class QuizDetailView(generics.RetrieveAPIView):
    queryset = Quiz.objects.prefetch_related(
        "questions__choices",
    )
    serializer_class = QuizDetailSerializer
    permission_classes = [IsAuthenticated]


class CourseARTaskListView(generics.ListAPIView):
    serializer_class = ARTaskListSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        cid = self.kwargs["course_id"]
        return ARTask.objects.filter(course_id=cid).order_by("pk")


class ARTaskDetailView(generics.RetrieveAPIView):
    queryset = ARTask.objects.prefetch_related("steps").select_related(
        "linked_video_section",
    )
    serializer_class = ARTaskDetailSerializer
    permission_classes = [IsAuthenticated]


class ARTaskProgressPostView(APIView):
    """
    Record or update student progress for an AR task (companion app / web).
    """

    permission_classes = [IsAuthenticated, IsStudentUser]

    def post(self, request, task_id):
        task = get_object_or_404(ARTask, pk=task_id)
        ser = StudentARTaskProgressWriteSerializer(
            data=request.data,
            context={"request": request, "task": task},
        )
        ser.is_valid(raise_exception=True)
        instance = ser.save()
        out = StudentARTaskProgressReadSerializer(instance)
        return Response(out.data, status=status.HTTP_200_OK)
