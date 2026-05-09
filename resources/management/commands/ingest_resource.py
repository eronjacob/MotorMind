import logging

from django.core.management.base import BaseCommand, CommandError

from resources.models import Resource, ResourceIngestionJob
from resources.services.ingestion import ingest_resource

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Run ingestion pipeline for a single Resource ID."

    def add_arguments(self, parser):
        parser.add_argument("resource_id", type=int)

    def handle(self, *args, **options):
        rid = options["resource_id"]
        if not Resource.objects.filter(pk=rid).exists():
            raise CommandError(f"Resource {rid} does not exist.")
        job = ResourceIngestionJob.objects.create(
            resource_id=rid,
            status=ResourceIngestionJob.Status.QUEUED,
            message="CLI ingest",
        )
        try:
            ingest_resource(rid, job.id)
        except Exception as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS(f"Ingestion completed for resource {rid}."))
