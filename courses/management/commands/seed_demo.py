"""
Load demo users and sample Automotive Electrical Diagnostics content.

Safe to run multiple times: uses get_or_create / updates passwords.
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import Profile
from ar_tasks.models import ARTask, ARTaskStep
from courses.models import Course, TrainingVideo, VideoSection
from quizzes.models import AnswerChoice, Question, Quiz

User = get_user_model()


class Command(BaseCommand):
    help = "Seed Car-Hoot demo teacher/students, course, video, quiz, and AR task."

    @transaction.atomic
    def handle(self, *args, **options):
        teacher, _ = User.objects.get_or_create(username="teacher")
        teacher.set_password("teacher123")
        teacher.save()
        Profile.objects.filter(user=teacher).update(role=Profile.Role.TEACHER)

        s1, _ = User.objects.get_or_create(username="student1")
        s1.set_password("student123")
        s1.save()
        Profile.objects.filter(user=s1).update(role=Profile.Role.STUDENT)

        s2, _ = User.objects.get_or_create(username="student2")
        s2.set_password("student123")
        s2.save()
        Profile.objects.filter(user=s2).update(role=Profile.Role.STUDENT)

        course, _ = Course.objects.get_or_create(
            title="Automotive Electrical Diagnostics",
            defaults={
                "description": "Foundational electrical testing workflow using a multimeter and fuse box checks.",
                "created_by": teacher,
            },
        )
        if course.created_by_id != teacher.id:
            course.created_by = teacher
            course.save(update_fields=["created_by"])

        video, _ = TrainingVideo.objects.get_or_create(
            course=course,
            title="How to Test a Car Fuse",
            defaults={
                "description": "Measure voltage across a fuse to determine if it is open or intact.",
                "video_url": "https://www.youtube.com/watch?v=9bZkp7q19f0",
                "transcript": (
                    "Placeholder transcript: explain multimeter mode selection, probing both fuse "
                    "terminals, and interpreting 12V/0V patterns relative to ground references."
                ),
            },
        )

        sections_spec = [
            (0, 45, "Set the multimeter to DC volts", "Select an appropriate DCV range and confirm leads."),
            (46, 120, "Test both sides of the fuse", "Compare readings on each fuse element terminal."),
            (121, 180, "Interpret the readings", "Relate readings to fuse health and circuit loading."),
        ]
        section_objs = []
        for order, (start, end, title, summary) in enumerate(sections_spec):
            sec, _ = VideoSection.objects.get_or_create(
                video=video,
                title=title,
                defaults={
                    "start_seconds": start,
                    "end_seconds": end,
                    "summary": summary,
                    "order": order,
                },
            )
            # Keep timing in sync if re-run with same title
            sec.start_seconds = start
            sec.end_seconds = end
            sec.summary = summary
            sec.order = order
            sec.save()
            section_objs.append(sec)

        sec_volts, sec_test, sec_interpret = section_objs

        quiz, _ = Quiz.objects.get_or_create(
            course=course,
            title="Fuse testing fundamentals",
            defaults={
                "description": "Quick checks for understanding basic fuse voltage patterns.",
                "pass_mark": 70,
            },
        )

        def ensure_question(order, text, explanation, timestamp, section, choices_spec):
            q, _ = Question.objects.get_or_create(
                quiz=quiz,
                order=order,
                defaults={
                    "question_text": text,
                    "explanation": explanation,
                    "timestamp_seconds": timestamp,
                    "section": section,
                },
            )
            q.question_text = text
            q.explanation = explanation
            q.timestamp_seconds = timestamp
            q.section = section
            q.save()

            for idx, (answer, is_correct) in enumerate(choices_spec):
                ch, _ = AnswerChoice.objects.get_or_create(
                    question=q,
                    answer_text=answer,
                    defaults={"is_correct": is_correct},
                )
                ch.is_correct = is_correct
                ch.save()

        ensure_question(
            0,
            "What does 12V on both sides of a fuse usually mean?",
            "Same voltage on both terminals typically means the fuse element is intact and both "
            "sides are connected in the energized part of the circuit.",
            130,
            sec_interpret,
            [
                ("The fuse is blown open", False),
                ("Both sides are at the same potential; the fuse is likely good", True),
                ("You must always replace the fuse", False),
                ("The battery is dead", False),
            ],
        )
        ensure_question(
            1,
            "What does 12V on one side and 0V on the other suggest?",
            "A large difference across a good fuse is unusual; an open fuse often shows supply "
            "on one side and no voltage on the load side.",
            90,
            sec_test,
            [
                ("The headlight is too bright", False),
                ("A normal condition for all fuses", False),
                ("A likely open fuse or loss of continuity through the fuse", True),
                ("The alternator is overcharging", False),
            ],
        )
        ensure_question(
            2,
            "Why should you use a known good ground?",
            "A bad ground reference can make voltage readings look wrong even when the circuit is fine.",
            15,
            sec_volts,
            [
                ("It makes the meter read faster", False),
                ("It is only required for AC measurements", False),
                ("It avoids misleading readings caused by a poor reference point", True),
                ("It increases fuse current capacity", False),
            ],
        )

        ar_task, _ = ARTask.objects.get_or_create(
            course=course,
            title="Virtual Fault: Headlight Fuse Diagnosis",
            defaults={
                "description": "Simulated readings for a left headlight fuse circuit on a healthy vehicle.",
                "target_object": ARTask.TargetObject.FUSE_BOX,
                "scenario_text": (
                    "Customer complaint: left headlight does not work. The car is healthy, but the app "
                    "simulates the diagnostic readings."
                ),
                "expected_action": (
                    "Confirm supply and ground references, compare both sides of the fuse, and select "
                    "the most likely fault based on simulated meter readings."
                ),
                "linked_video_section": sec_test,
                "difficulty": ARTask.Difficulty.INTERMEDIATE,
            },
        )
        ar_task.linked_video_section = sec_test
        ar_task.save()

        steps = [
            ("Scan or locate the fuse box.", "N/A", "Use the vehicle layout to find the under-hood fuse panel."),
            ("Identify the headlight fuse.", "Label match", "Match the fuse position to the headlamp circuit."),
            ("Test both fuse tabs.", "12V / 0V simulated", "Compare readings to a virtual open-fuse pattern."),
            ("Interpret simulated readings.", "Open vs good", "Relate side-to-side differences to fuse state."),
            ("Choose the likely fault.", "Open fuse", "Select blown fuse vs bulb vs wiring based on evidence."),
        ]
        for order, (instr, reading, expl) in enumerate(steps):
            st, _ = ARTaskStep.objects.get_or_create(
                task=ar_task,
                order=order,
                defaults={
                    "instruction": instr,
                    "expected_reading": reading,
                    "explanation": expl,
                    "video_timestamp_seconds": 60 + order * 10,
                },
            )
            st.instruction = instr
            st.expected_reading = reading
            st.explanation = expl
            st.video_timestamp_seconds = 60 + order * 10
            st.save()

        # Optional: demo text resource for vector search (requires chromadb + sentence-transformers).
        try:
            from django.core.files.base import ContentFile

            from resources.models import Resource, ResourceIngestionJob
            from resources.services.ingestion import ingest_resource

            demo_body = (
                "Fuse testing quick notes:\n"
                "- Set the multimeter to DC volts.\n"
                "- Use a known good ground reference.\n"
                "- Test both tabs of the fuse.\n"
                "- 12V on both sides usually means the fuse element is intact and both sides share the same potential.\n"
                "- 12V on one side and 0V on the other often suggests a blown/open fuse.\n"
                "- 0V on both sides may mean no upstream supply or a measurement reference issue.\n"
            )
            demo = Resource.objects.filter(title="Demo Fuse Testing Notes").first()
            if not demo:
                demo = Resource(
                    title="Demo Fuse Testing Notes",
                    resource_type=Resource.ResourceType.NOTES,
                    description="Auto-seeded notes for semantic retrieval demo.",
                    uploaded_by=teacher,
                    original_filename="demo_fuse_notes.txt",
                    status=Resource.Status.UPLOADED,
                    isbn="",
                    metadata_lookup_status=Resource.MetadataLookupStatus.NOT_REQUIRED,
                    metadata_lookup_error="",
                    raw_metadata={},
                )
                demo.uploaded_file.save(
                    "demo_fuse_notes.txt",
                    ContentFile(demo_body.encode("utf-8")),
                )
                demo.save()
            demo.isbn = ""
            demo.metadata_lookup_status = Resource.MetadataLookupStatus.NOT_REQUIRED
            demo.metadata_lookup_error = ""
            demo.raw_metadata = {}
            demo.save(
                update_fields=[
                    "isbn",
                    "metadata_lookup_status",
                    "metadata_lookup_error",
                    "raw_metadata",
                    "updated_at",
                ]
            )
            demo.courses.add(course)
            if demo.status != Resource.Status.INGESTED or demo.chunk_count == 0:
                job = ResourceIngestionJob.objects.create(
                    resource=demo,
                    status=ResourceIngestionJob.Status.QUEUED,
                    message="seed_demo ingest",
                )
                ingest_resource(demo.id, job.id)
        except Exception as exc:
            self.stdout.write(self.style.WARNING(f"Demo resource / vector ingest skipped: {exc}"))

        self.stdout.write(self.style.SUCCESS("Demo data seeded successfully."))
