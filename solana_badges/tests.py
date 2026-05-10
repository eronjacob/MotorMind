from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from courses.models import Course
from quizzes.models import AnswerChoice, Question, Quiz, QuizAttempt
from solana_badges.models import SkillBadge
from solana_badges.services.quiz_badges import ensure_quiz_pass_skill_badge
from solana_badges.validators import is_valid_solana_address

User = get_user_model()


class QuizPassBadgeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="stu", password="pw")
        self.course = Course.objects.create(
            title="Short Circuit Lab",
            description="",
            created_by=self.user,
        )
        self.quiz = Quiz.objects.create(
            course=self.course,
            title="Fuse basics quiz",
            pass_mark=50,
        )
        self.q = Question.objects.create(
            quiz=self.quiz,
            question_text="One",
            order=0,
        )
        AnswerChoice.objects.create(question=self.q, answer_text="Y", is_correct=True)

    def test_pass_creates_claimable_badge(self):
        attempt = QuizAttempt.objects.create(
            quiz=self.quiz,
            student=self.user,
            score=100,
            passed=True,
            correct_answers=1,
            total_questions=1,
        )
        badge = ensure_quiz_pass_skill_badge(attempt)
        self.assertIsNotNone(badge)
        self.assertEqual(badge.status, SkillBadge.Status.CLAIMABLE)
        self.assertEqual(badge.quiz_attempt_id, attempt.pk)
        # 100% → perfect-score icon
        self.assertEqual(badge.icon_name, "perfect-score")

    def test_fail_does_not_create(self):
        attempt = QuizAttempt.objects.create(
            quiz=self.quiz,
            student=self.user,
            score=40,
            passed=False,
            correct_answers=0,
            total_questions=1,
        )
        self.assertIsNone(ensure_quiz_pass_skill_badge(attempt))


class WalletValidatorTests(TestCase):
    def test_valid_base58(self):
        self.assertTrue(
            is_valid_solana_address("11111111111111111111111111111111"),
        )

    def test_invalid(self):
        self.assertFalse(is_valid_solana_address("not-a-wallet"))
        self.assertFalse(is_valid_solana_address(""))


class ProfileViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="p1", password="pw")

    def test_profile_requires_login(self):
        r = self.client.get(reverse("solana_badges:profile"))
        self.assertEqual(r.status_code, 302)

    def test_profile_ok(self):
        self.client.login(username="p1", password="pw")
        r = self.client.get(reverse("solana_badges:profile"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "p1")
