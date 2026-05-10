from django.conf import settings
from django.db import models
from django.db.models import Q


class SolanaWalletProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="solana_wallet_profile",
    )
    wallet_address = models.CharField(max_length=64, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user_id} wallet"


class SkillBadge(models.Model):
    class BadgeType(models.TextChoices):
        QUIZ_PASS = "quiz_pass", "Quiz pass"
        COURSE_COMPLETION = "course_completion", "Course completion"
        AR_TASK_COMPLETION = "ar_task_completion", "AR task completion"
        LEADERBOARD = "leaderboard", "Leaderboard"

    class Status(models.TextChoices):
        CLAIMABLE = "claimable", "Claimable"
        CLAIMED = "claimed", "Claimed"
        FAILED = "failed", "Failed"

    course = models.ForeignKey(
        "courses.Course",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="skill_badges",
    )
    quiz = models.ForeignKey(
        "quizzes.Quiz",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="skill_badges",
    )
    quiz_attempt = models.ForeignKey(
        "quizzes.QuizAttempt",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="skill_badges",
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="skill_badges",
    )
    wallet_address = models.CharField(max_length=64, blank=True, default="")
    badge_type = models.CharField(
        max_length=32,
        choices=BadgeType.choices,
        default=BadgeType.QUIZ_PASS,
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    score = models.PositiveIntegerField(null=True, blank=True)
    icon_name = models.CharField(max_length=80, default="diagnostic-apprentice")
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.CLAIMABLE,
    )
    solana_network = models.CharField(max_length=32, default="devnet")
    transaction_signature = models.CharField(max_length=128, blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    claimed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["quiz_attempt"],
                condition=Q(quiz_attempt__isnull=False),
                name="skillbadge_unique_quiz_attempt",
            ),
        ]

    def __str__(self):
        return f"{self.title} ({self.get_status_display()})"

    @property
    def explorer_url(self) -> str:
        if not self.transaction_signature:
            return ""
        return (
            "https://explorer.solana.com/tx/"
            f"{self.transaction_signature}?cluster=devnet"
        )

    @property
    def icon_static_path(self) -> str:
        return f"images/badges/{self.icon_name}.svg"
