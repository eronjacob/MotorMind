"""Create claimable skill badges when students pass quizzes."""

from __future__ import annotations

import re

from django.db import IntegrityError

from solana_badges.models import SkillBadge


def resolve_quiz_badge_icon(quiz_title: str, score_percent: int) -> str:
    """Pick a local SVG badge id from quiz title and score (see static/images/badges/)."""
    t = (quiz_title or "").lower()
    if score_percent == 100:
        return "perfect-score"
    if re.search(r"\bfuse\b", t):
        return "fuse-expert"
    if re.search(r"short\s+circuit", t):
        return "short-circuit-solver"
    return "diagnostic-apprentice"


def ensure_quiz_pass_skill_badge(attempt) -> SkillBadge | None:
    """
    When a quiz attempt passes, create at most one claimable quiz_pass badge
    linked to that attempt.
    """
    from quizzes.models import QuizAttempt

    if not isinstance(attempt, QuizAttempt) or not attempt.passed:
        return None

    attempt = QuizAttempt.objects.select_related("quiz", "quiz__course").filter(pk=attempt.pk).first()
    if not attempt or not attempt.quiz_id:
        return None

    course = attempt.quiz.course
    title = course.title if course else attempt.quiz.title
    description = "Successfully completed the diagnostic assessment."
    icon = resolve_quiz_badge_icon(attempt.quiz.title, int(attempt.score))

    try:
        badge, created = SkillBadge.objects.get_or_create(
            quiz_attempt=attempt,
            defaults={
                "student": attempt.student,
                "course_id": attempt.quiz.course_id,
                "quiz_id": attempt.quiz_id,
                "badge_type": SkillBadge.BadgeType.QUIZ_PASS,
                "title": title,
                "description": description,
                "score": int(attempt.score),
                "icon_name": icon,
                "status": SkillBadge.Status.CLAIMABLE,
                "metadata": {
                    "quiz_title": attempt.quiz.title,
                    "course_id": attempt.quiz.course_id,
                    "quiz_id": attempt.quiz_id,
                },
            },
        )
        return badge
    except IntegrityError:
        return SkillBadge.objects.filter(quiz_attempt=attempt).first()
