import logging

from django.core.management.base import BaseCommand, CommandError

from resources.models import Resource
from resources.services.resource_upload import apply_metadata_lookup_to_resource

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Re-fetch book metadata from public APIs using Resource.isbn and update the Resource row."

    def add_arguments(self, parser):
        parser.add_argument("resource_id", type=int)

    def handle(self, *args, **options):
        rid = options["resource_id"]
        resource = Resource.objects.filter(pk=rid).first()
        if not resource:
            raise CommandError(f"Resource {rid} does not exist.")

        before = (
            resource.title,
            resource.author,
            resource.publisher,
            resource.year,
            resource.metadata_lookup_status,
        )
        self.stdout.write(
            f"Before: title={before[0]!r} author={before[1]!r} publisher={before[2]!r} year={before[3]!r} status={before[4]!r}"
        )

        apply_metadata_lookup_to_resource(resource)
        resource.save()

        resource.refresh_from_db()
        self.stdout.write(
            f"After:  title={resource.title!r} author={resource.author!r} publisher={resource.publisher!r} year={resource.year!r} status={resource.metadata_lookup_status!r}"
        )
        if resource.metadata_lookup_error:
            self.stdout.write(self.style.WARNING(f"lookup_error: {resource.metadata_lookup_error}"))
        self.stdout.write(self.style.SUCCESS(f"Updated metadata for resource {rid}."))
