"""
End-to-end ingestion: extract → chunk → embed → Chroma upsert.

Designed so a future Celery task can call `ingest_resource` without changes.
"""

from __future__ import annotations

import logging

from django.db import transaction
from django.utils import timezone

from resources.models import Resource, ResourceIngestionJob
from resources.services.chunking import chunk_pages
from resources.services.extractors import extract_resource_text
from resources.services.vector_store import add_chunks, delete_resource_vectors

logger = logging.getLogger(__name__)

TOTAL_STEPS = 10


def _touch_job(job: ResourceIngestionJob, **fields):
    for k, v in fields.items():
        setattr(job, k, v)
    job.save(update_fields=list(fields.keys()) + ["updated_at"])


def _set_progress(job: ResourceIngestionJob, completed: int, message: str):
    completed = max(0, min(TOTAL_STEPS, completed))
    pct = int(round(100 * completed / TOTAL_STEPS))
    _touch_job(
        job,
        completed_steps=completed,
        total_steps=TOTAL_STEPS,
        progress_percent=pct,
        message=message,
    )


def ingest_resource(resource_id: int, job_id: int | None = None) -> ResourceIngestionJob:
    """
    Synchronous ingestion pipeline for one resource.

    - Clears any existing vectors for this resource_id first (idempotent re-ingest).
    - Updates Resource.status / chunk_count / error_message.
    """
    job = None
    with transaction.atomic():
        resource = (
            Resource.objects.select_for_update()
            .prefetch_related("courses")
            .get(pk=resource_id)
        )
        if job_id:
            job = ResourceIngestionJob.objects.select_for_update().get(pk=job_id, resource=resource)
        else:
            job = ResourceIngestionJob.objects.create(
                resource=resource,
                status=ResourceIngestionJob.Status.RUNNING,
                total_steps=TOTAL_STEPS,
                completed_steps=0,
                progress_percent=0,
                message="Starting…",
                started_at=timezone.now(),
            )
        resource.status = Resource.Status.INGESTING
        resource.error_message = ""
        resource.save(update_fields=["status", "error_message", "updated_at"])

    if job:
        _touch_job(
            job,
            status=ResourceIngestionJob.Status.RUNNING,
            started_at=job.started_at or timezone.now(),
        )
        _set_progress(job, 1, "Uploaded — preparing")

    try:
        if job:
            _set_progress(job, 2, "Extracting text…")
        pages = extract_resource_text(resource)

        if job:
            _set_progress(job, 4, "Chunking content…")
        chunks = chunk_pages(pages, chunk_size=1000, overlap=200)
        if not chunks:
            raise ValueError("No text chunks produced (empty document after extraction?).")
        logger.info(
            "Prepared %s text chunks for resource_id=%s (page-wise extract, ~1k chars/chunk, 200 overlap)",
            len(chunks),
            resource_id,
        )

        if job:
            _set_progress(job, 6, "Removing old vectors (if any)…")
        # Refresh M2M and scalar fields before writing vectors / metadata.
        resource = Resource.objects.prefetch_related("courses").get(pk=resource_id)
        delete_resource_vectors(int(resource.id), resource.vector_collection or None)
        resource.chunk_count = 0
        resource.save(update_fields=["chunk_count", "updated_at"])

        if job:
            _set_progress(job, 7, "Creating embeddings…")
        if job:
            _set_progress(job, 8, "Saving vector index…")
        add_chunks(resource, chunks)

        with transaction.atomic():
            resource = Resource.objects.select_for_update().get(pk=resource_id)
            resource.chunk_count = len(chunks)
            resource.status = Resource.Status.INGESTED
            resource.error_message = ""
            resource.save(update_fields=["chunk_count", "status", "error_message", "updated_at"])
            if job:
                j = ResourceIngestionJob.objects.select_for_update().get(pk=job.pk)
                j.status = ResourceIngestionJob.Status.COMPLETED
                j.completed_steps = TOTAL_STEPS
                j.progress_percent = 100
                j.message = "Complete"
                j.error_message = ""
                j.finished_at = timezone.now()
                j.save(
                    update_fields=[
                        "status",
                        "completed_steps",
                        "progress_percent",
                        "message",
                        "error_message",
                        "finished_at",
                        "updated_at",
                    ]
                )

        logger.info("Ingestion completed resource_id=%s chunks=%s", resource_id, len(chunks))
        return job or ResourceIngestionJob.objects.filter(resource_id=resource_id).order_by("-pk").first()

    except Exception as exc:  # pragma: no cover - broad for hackathon UX
        logger.exception("Ingestion failed resource_id=%s", resource_id)
        err = str(exc)
        with transaction.atomic():
            resource = Resource.objects.select_for_update().get(pk=resource_id)
            resource.status = Resource.Status.FAILED
            resource.error_message = err[:4000]
            resource.save(update_fields=["status", "error_message", "updated_at"])
            if job:
                j = ResourceIngestionJob.objects.select_for_update().get(pk=job.pk)
                j.status = ResourceIngestionJob.Status.FAILED
                j.error_message = err[:4000]
                j.message = "Failed"
                j.finished_at = timezone.now()
                j.save(update_fields=["status", "error_message", "message", "finished_at", "updated_at"])
        raise
