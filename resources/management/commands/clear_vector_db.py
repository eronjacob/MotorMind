import logging

from django.core.management.base import BaseCommand

from resources.services.vector_store import clear_collection

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Drop and recreate the empty Chroma collection (destructive to vectors)."

    def handle(self, *args, **options):
        clear_collection()
        self.stdout.write(self.style.WARNING("Chroma collection cleared and recreated."))
