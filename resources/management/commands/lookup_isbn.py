import json

from django.core.management.base import BaseCommand

from resources.services.book_metadata import lookup_book_metadata_by_isbn


class Command(BaseCommand):
    help = "Print normalized book metadata for an ISBN (Open Library + Google Books)."

    def add_arguments(self, parser):
        parser.add_argument("isbn", type=str)

    def handle(self, *args, **options):
        isbn = (options["isbn"] or "").strip()
        meta = lookup_book_metadata_by_isbn(isbn)
        self.stdout.write(self.style.NOTICE(f"metadata_source: {meta.get('metadata_source')}"))
        if meta.get("error"):
            self.stdout.write(self.style.WARNING(f"error: {meta['error']}"))
        self.stdout.write(json.dumps(meta, indent=2, ensure_ascii=False, default=str))
