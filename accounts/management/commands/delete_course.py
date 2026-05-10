"""Delete a single course from the shell (explicit --confirm only)."""

from django.core.management.base import BaseCommand, CommandError

from courses.models import Course


class Command(BaseCommand):
    help = "Delete one course by primary key. Requires --confirm."

    def add_arguments(self, parser):
        parser.add_argument("course_id", type=int)
        parser.add_argument(
            "--confirm",
            action="store_true",
            help="Actually delete the course and CASCADE-related rows.",
        )

    def handle(self, *args, **options):
        pk = options["course_id"]
        confirm = options["confirm"]
        try:
            course = Course.objects.select_related("created_by").get(pk=pk)
        except Course.DoesNotExist as exc:
            raise CommandError(f"No course with id={pk}") from exc
        owner = getattr(course.created_by, "username", "?")
        self.stdout.write(
            f"Course id={course.pk} title={course.title!r} owner={owner}"
        )
        if not confirm:
            self.stdout.write(
                self.style.WARNING("Dry run only. Re-run with --confirm to delete.")
            )
            return
        title = course.title
        course.delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted course id={pk} ({title!r})."))
