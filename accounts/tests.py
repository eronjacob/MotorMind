import re

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import Profile
from courses.models import Course
from quizzes.models import Quiz, QuizAttempt
from resources.models import Resource
from solana_badges.models import SkillBadge


class CourseResourceAttachDetachTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="tres", password="pw")
        self.user.profile.role = Profile.Role.TEACHER
        self.user.profile.save(update_fields=["role"])
        self.course = Course.objects.create(
            title="Electrical 101",
            description="",
            created_by=self.user,
        )
        self.resource = Resource.objects.create(
            title="Shop manual",
            resource_type=Resource.ResourceType.PDF,
            uploaded_file=SimpleUploadedFile("m.pdf", b"%PDF-1.4"),
            status=Resource.Status.UPLOADED,
        )
        self.client = Client()
        self.client.login(username="tres", password="pw")

    def test_attach_and_detach(self):
        url_attach = reverse(
            "accounts:course_resource_attach",
            kwargs={"course_id": self.course.pk},
        )
        resp = self.client.post(
            url_attach,
            {"resource_id": str(self.resource.pk)},
            follow=False,
        )
        self.assertEqual(resp.status_code, 302)
        self.assertIn(self.resource, self.course.resources.all())

        url_detach = reverse(
            "accounts:course_resource_detach",
            kwargs={"course_id": self.course.pk, "resource_id": self.resource.pk},
        )
        resp2 = self.client.post(url_detach, follow=False)
        self.assertEqual(resp2.status_code, 302)
        self.assertNotIn(self.resource, self.course.resources.all())
        self.assertTrue(Resource.objects.filter(pk=self.resource.pk).exists())


class CourseDeleteTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="delteacher", password="pw")
        self.user.profile.role = Profile.Role.TEACHER
        self.user.profile.save(update_fields=["role"])
        self.course = Course.objects.create(
            title="To delete",
            description="",
            created_by=self.user,
        )
        self.resource = Resource.objects.create(
            title="Shared doc",
            resource_type=Resource.ResourceType.PDF,
            uploaded_file=SimpleUploadedFile("x.pdf", b"%PDF-1.4"),
            status=Resource.Status.UPLOADED,
        )
        self.resource.courses.add(self.course)
        self.client = Client()
        self.client.login(username="delteacher", password="pw")

    def test_delete_course_removes_course_keeps_resource(self):
        url = reverse("accounts:manage_course_delete", kwargs={"course_id": self.course.pk})
        r = self.client.post(url, follow=False)
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r["Location"], reverse("accounts:admin_panel"))
        self.assertFalse(Course.objects.filter(pk=self.course.pk).exists())
        self.resource.refresh_from_db()
        self.assertEqual(self.resource.courses.count(), 0)


class QuizAttemptDeleteTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(username="ownerteacher", password="pw")
        self.owner.profile.role = Profile.Role.TEACHER
        self.owner.profile.save(update_fields=["role"])
        self.other = User.objects.create_user(username="otherteacher", password="pw")
        self.other.profile.role = Profile.Role.TEACHER
        self.other.profile.save(update_fields=["role"])
        self.student = User.objects.create_user(username="stu", password="pw")
        self.course = Course.objects.create(
            title="Owned",
            description="",
            created_by=self.owner,
        )
        self.quiz = Quiz.objects.create(course=self.course, title="Q1")
        self.attempt = QuizAttempt.objects.create(
            quiz=self.quiz,
            student=self.student,
            score=80,
            passed=True,
            correct_answers=1,
            total_questions=1,
        )
        self.client = Client()

    def test_non_owner_forbidden(self):
        self.client.login(username="otherteacher", password="pw")
        url = reverse("accounts:quiz_attempt_delete", kwargs={"attempt_id": self.attempt.pk})
        r = self.client.post(url, follow=False)
        self.assertEqual(r.status_code, 403)
        self.assertTrue(QuizAttempt.objects.filter(pk=self.attempt.pk).exists())

    def test_owner_deletes_attempt(self):
        self.client.login(username="ownerteacher", password="pw")
        url = reverse("accounts:quiz_attempt_delete", kwargs={"attempt_id": self.attempt.pk})
        r = self.client.post(url, follow=False)
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r["Location"], reverse("accounts:admin_panel"))
        self.assertFalse(QuizAttempt.objects.filter(pk=self.attempt.pk).exists())

    def test_blocked_when_claimed_badge(self):
        SkillBadge.objects.create(
            course=self.course,
            quiz=self.quiz,
            quiz_attempt=self.attempt,
            student=self.student,
            title="Badge",
            status=SkillBadge.Status.CLAIMED,
        )
        self.client.login(username="ownerteacher", password="pw")
        url = reverse("accounts:quiz_attempt_delete", kwargs={"attempt_id": self.attempt.pk})
        r = self.client.post(url, follow=False)
        self.assertEqual(r.status_code, 302)
        self.assertTrue(QuizAttempt.objects.filter(pk=self.attempt.pk).exists())

    def test_claimable_badge_removed_with_attempt(self):
        badge = SkillBadge.objects.create(
            course=self.course,
            quiz=self.quiz,
            quiz_attempt=self.attempt,
            student=self.student,
            title="Badge",
            status=SkillBadge.Status.CLAIMABLE,
        )
        self.client.login(username="ownerteacher", password="pw")
        url = reverse("accounts:quiz_attempt_delete", kwargs={"attempt_id": self.attempt.pk})
        r = self.client.post(url, follow=False)
        self.assertEqual(r.status_code, 302)
        self.assertFalse(QuizAttempt.objects.filter(pk=self.attempt.pk).exists())
        self.assertFalse(SkillBadge.objects.filter(pk=badge.pk).exists())


class LoginCsrfTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="student1", password="student123")

    def test_login_post_succeeds_with_csrf(self):
        c = Client(enforce_csrf_checks=True)
        login_url = reverse("accounts:login")
        r = c.get(login_url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "csrfmiddlewaretoken")
        self.assertIn("csrftoken", c.cookies)
        m = re.search(
            r'name="csrfmiddlewaretoken" value="([^"]+)"',
            r.content.decode(),
        )
        self.assertIsNotNone(m, "csrf hidden field missing from login page")
        token = m.group(1)
        r2 = c.post(
            login_url,
            {
                "username": "student1",
                "password": "student123",
                "csrfmiddlewaretoken": token,
            },
            HTTP_REFERER="http://testserver" + login_url,
        )
        self.assertEqual(r2.status_code, 302, r2.content[:500])
