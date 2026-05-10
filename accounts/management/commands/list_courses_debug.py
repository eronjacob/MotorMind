"""Print course rows with owner and related counts (debug / cleanup)."""

from django.core.management.base import BaseCommand
from django.db.models import Count

from courses.models import Course
from quizzes.models import QuizAttempt


class Command(BaseCommand):
    help = "List courses with id, title, created_by, video/quiz/attempt counts."

    def handle(self, *args, **options):
        courses = (
            Course.objects.select_related("created_by")
            .annotate(
                n_videos=Count("videos", distinct=True),
                n_quizzes=Count("quizzes", distinct=True),
            )
            .order_by("pk")
        )
        for c in courses:
            n_attempts = QuizAttempt.objects.filter(quiz__course_id=c.pk).count()
            owner = getattr(c.created_by, "username", None) or "—"
            self.stdout.write(
                f"id={c.pk}\ttitle={c.title!r}\tcreated_by={owner}\t"
                f"videos={c.n_videos}\tquizzes={c.n_quizzes}\tattempts={n_attempts}"
            )
