"""
Remove quiz attempts (and linked unclaimed/failed skill badges) for given usernames
and an exact quiz title. Defaults to dry-run; pass --confirm to delete.
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from quizzes.models import QuizAttempt


class Command(BaseCommand):
    help = (
        "List or delete quiz attempts for comma-separated usernames and exact quiz title. "
        "Skips attempts that have a claimed Solana skill badge."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--users",
            required=True,
            help="Comma-separated usernames (e.g. a,b).",
        )
        parser.add_argument(
            "--quiz-title",
            "--quizzes",
            dest="quiz_title",
            required=True,
            help="Exact quiz title to match (e.g. T).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print only (this is also the default when --confirm is omitted).",
        )
        parser.add_argument(
            "--confirm",
            action="store_true",
            help="Perform deletions.",
        )

    def handle(self, *args, **options):
        usernames = [u.strip() for u in options["users"].split(",") if u.strip()]
        if not usernames:
            raise CommandError("--users must list at least one username.")
        title = options["quiz_title"]
        confirm = options["confirm"]

        try:
            from solana_badges.models import SkillBadge
        except ImportError:
            SkillBadge = None  # type: ignore

        attempts = QuizAttempt.objects.filter(
            student__username__in=usernames,
            quiz__title=title,
        ).select_related("quiz", "student")

        self.stdout.write(
            f"Matching attempts (users={usernames!r}, quiz title={title!r}): "
            f"{attempts.count()}"
        )

        deletable = []
        blocked = []
        for attempt in attempts:
            if SkillBadge is not None:
                claimed = SkillBadge.objects.filter(
                    quiz_attempt=attempt,
                    status=SkillBadge.Status.CLAIMED,
                ).exists()
                if claimed:
                    blocked.append(attempt)
                    continue
            deletable.append(attempt)

        for attempt in blocked:
            self.stdout.write(
                self.style.WARNING(
                    f"  SKIP (claimed Solana badge): attempt id={attempt.pk} "
                    f"user={attempt.student.username} quiz={attempt.quiz.title!r}"
                )
            )

        for attempt in deletable:
            badge_qs = None
            if SkillBadge is not None:
                badge_qs = SkillBadge.objects.filter(quiz_attempt=attempt)
                n_badges = badge_qs.count()
            else:
                n_badges = 0
            self.stdout.write(
                f"  attempt id={attempt.pk} user={attempt.student.username} "
                f"quiz={attempt.quiz.title!r} score={attempt.score}% "
                f"linked_skill_badges={n_badges}"
            )

        if not confirm:
            self.stdout.write(
                self.style.WARNING(
                    "Dry run (default). Pass --confirm to delete the rows listed above "
                    "(skipped rows are never deleted)."
                )
            )
            return

        deleted_attempts = 0
        deleted_badges = 0
        with transaction.atomic():
            for attempt in deletable:
                if SkillBadge is not None:
                    bqs = SkillBadge.objects.filter(quiz_attempt=attempt)
                    deleted_badges += bqs.count()
                    bqs.delete()
                attempt.delete()
                deleted_attempts += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Deleted {deleted_attempts} attempt(s), {deleted_badges} skill badge row(s)."
            )
        )
