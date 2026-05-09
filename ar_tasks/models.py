from django.conf import settings
from django.db import models


class ARTask(models.Model):
    """Virtual fault / diagnostic practice scenario for AR companion workflows."""

    class TargetObject(models.TextChoices):
        BATTERY = "battery", "Battery"
        FUSE_BOX = "fuse_box", "Fuse box"
        RELAY_BOX = "relay_box", "Relay box"
        OBD_PORT = "obd_port", "OBD port"
        HEADLIGHT_CONNECTOR = "headlight_connector", "Headlight connector"
        GROUND_POINT = "ground_point", "Ground point"
        SENSOR_CONNECTOR = "sensor_connector", "Sensor connector"

    class Difficulty(models.TextChoices):
        BEGINNER = "beginner", "Beginner"
        INTERMEDIATE = "intermediate", "Intermediate"
        ADVANCED = "advanced", "Advanced"

    course = models.ForeignKey(
        "courses.Course",
        on_delete=models.CASCADE,
        related_name="ar_tasks",
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    target_object = models.CharField(
        max_length=50,
        choices=TargetObject.choices,
    )
    scenario_text = models.TextField(blank=True)
    expected_action = models.TextField(blank=True)
    linked_video_section = models.ForeignKey(
        "courses.VideoSection",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ar_tasks",
    )
    difficulty = models.CharField(
        max_length=20,
        choices=Difficulty.choices,
        default=Difficulty.BEGINNER,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["pk"]

    def __str__(self):
        return self.title


class ARTaskStep(models.Model):
    task = models.ForeignKey(
        ARTask,
        on_delete=models.CASCADE,
        related_name="steps",
    )
    order = models.PositiveIntegerField(default=0)
    instruction = models.TextField()
    expected_reading = models.CharField(max_length=255, blank=True)
    explanation = models.TextField(blank=True)
    video_timestamp_seconds = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["order", "pk"]

    def __str__(self):
        return f"Step {self.order}: {self.instruction[:40]}"


class StudentARTaskProgress(models.Model):
    class Status(models.TextChoices):
        NOT_STARTED = "not_started", "Not started"
        IN_PROGRESS = "in_progress", "In progress"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ar_task_progress",
    )
    task = models.ForeignKey(
        ARTask,
        on_delete=models.CASCADE,
        related_name="student_progress",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.NOT_STARTED,
    )
    notes = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["student", "task"],
                name="unique_student_ar_task_progress",
            )
        ]
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.student} — {self.task} ({self.get_status_display()})"
