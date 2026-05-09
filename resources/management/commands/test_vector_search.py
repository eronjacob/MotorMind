import json
import logging

from django.core.management.base import BaseCommand, CommandError

from resources.services.vector_store import query_similar_chunks

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Run a quick semantic search against Chroma, e.g. test_vector_search "how do I test a fuse?"'

    def add_arguments(self, parser):
        parser.add_argument("query", type=str)
        parser.add_argument("--top-k", type=int, default=5)
        parser.add_argument("--course-id", type=int, default=None)
        parser.add_argument("--resource-type", type=str, default=None)
        parser.add_argument("--resource-id", type=int, default=None)

    def handle(self, *args, **options):
        q = options["query"].strip()
        if not q:
            raise CommandError("Query must be non-empty.")
        hits = query_similar_chunks(
            q,
            top_k=options["top_k"],
            course_id=options["course_id"],
            resource_type=options["resource_type"],
            resource_id=options["resource_id"],
        )
        self.stdout.write(json.dumps(hits, indent=2, default=str))
