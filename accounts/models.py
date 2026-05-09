from django.conf import settings
from django.db import models


class Profile(models.Model):
    """Extended user info: Car-Hoot role (teacher vs student)."""

    class Role(models.TextChoices):
        TEACHER = "teacher", "Teacher"
        STUDENT = "student", "Student"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.STUDENT,
    )
    display_name = models.CharField(max_length=150, blank=True)

    def __str__(self):
        label = self.display_name or self.user.get_username()
        return f"{label} ({self.get_role_display()})"
