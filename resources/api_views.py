"""
JSON API for resource metadata + vector search (teacher tooling / future admin clients).
"""

from __future__ import annotations

import logging

from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from api.permissions import IsTeacherUser

from .models import Resource, ResourceIngestionJob, ResourceRetrievalLog
from .serializers_api import ResourceDetailSerializer, ResourceListSerializer, ResourceSearchSerializer
from .services.ingestion import ingest_resource
from .services.resource_upload import API_UPLOAD_ISBN_ERROR, build_resource_from_minimal_upload
from .services.search_format import format_api_results
from .services.vector_store import delete_resource_vectors, query_similar_chunks

logger = logging.getLogger(__name__)


class ResourceListAPIView(APIView):
    permission_classes = [IsAuthenticated, IsTeacherUser]

    def get(self, request):
        qs = Resource.objects.prefetch_related("courses").order_by("-created_at")
        return Response(ResourceListSerializer(qs, many=True).data)


class ResourceDetailAPIView(APIView):
    permission_classes = [IsAuthenticated, IsTeacherUser]

    def get(self, request, pk):
        obj = get_object_or_404(Resource.objects.prefetch_related("courses"), pk=pk)
        return Response(ResourceDetailSerializer(obj).data)

    def delete(self, request, pk):
        resource = get_object_or_404(Resource, pk=pk)
        rid = int(resource.id)
        try:
            delete_resource_vectors(rid, resource.vector_collection or None)
        except Exception as exc:
            logger.warning("Chroma delete failed: %s", exc)
        try:
            resource.uploaded_file.delete(save=False)
        except Exception:
            pass
        resource.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ResourceUploadAPIView(APIView):
    """
    Minimal multipart upload: `uploaded_file`, optional `course_ids`, optional `resource_type`.

    Book uploads require a valid ISBN in the filename; metadata is fetched automatically.
    """

    permission_classes = [IsAuthenticated, IsTeacherUser]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request):
        from courses.models import Course

        uploaded_file = request.data.get("uploaded_file") or request.FILES.get("uploaded_file")
        if not uploaded_file:
            return Response({"detail": "uploaded_file is required."}, status=400)

        course_ids = request.POST.getlist("course_ids")
        if not course_ids:
            raw = request.data.get("course_ids")
            if isinstance(raw, str):
                try:
                    import json

                    course_ids = json.loads(raw)
                except json.JSONDecodeError:
                    course_ids = []
            elif isinstance(raw, list):
                course_ids = raw
            else:
                course_ids = []

        from pathlib import Path

        from .forms import ALLOWED_EXTENSIONS

        name = getattr(uploaded_file, "name", "") or ""
        ext = Path(name).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            return Response({"detail": f"Unsupported file type: {ext}"}, status=400)

        explicit_type = (request.data.get("resource_type") or "").strip()

        try:
            resource = build_resource_from_minimal_upload(
                uploaded_file=uploaded_file,
                original_filename=name,
                explicit_resource_type=explicit_type,
                user=request.user if request.user.is_authenticated else None,
            )
            resource.uploaded_file = uploaded_file
            resource.save()
        except ValidationError:
            return Response({"error": API_UPLOAD_ISBN_ERROR}, status=400)

        if course_ids:
            ids = []
            for raw in course_ids:
                try:
                    ids.append(int(raw))
                except (TypeError, ValueError):
                    continue
            resource.courses.set(Course.objects.filter(pk__in=ids))

        job = ResourceIngestionJob.objects.create(resource=resource, status=ResourceIngestionJob.Status.QUEUED)
        try:
            ingest_resource(resource.id, job.id)
        except Exception as exc:
            logger.exception("API upload ingest failed")
            return Response({"detail": str(exc), "resource_id": resource.id}, status=500)
        resource.refresh_from_db()
        return Response({"resource": ResourceDetailSerializer(resource).data}, status=201)


class ResourceIngestAPIView(APIView):
    permission_classes = [IsAuthenticated, IsTeacherUser]

    def post(self, request, pk):
        resource = get_object_or_404(Resource, pk=pk)
        job = ResourceIngestionJob.objects.create(resource=resource, status=ResourceIngestionJob.Status.QUEUED)
        try:
            ingest_resource(resource.id, job.id)
        except Exception as exc:
            return Response({"detail": str(exc)}, status=500)
        return Response({"job_id": job.id, "resource": ResourceDetailSerializer(resource).data})


class ResourceSearchAPIView(APIView):
    permission_classes = [IsAuthenticated, IsTeacherUser]

    def post(self, request):
        ser = ResourceSearchSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        q = ser.validated_data["query"]
        top_k = ser.validated_data.get("top_k") or 5
        course_id = ser.validated_data.get("course_id")
        resource_type = ser.validated_data.get("resource_type") or None
        resource_id = ser.validated_data.get("resource_id")
        if resource_type == "":
            resource_type = None

        hits = query_similar_chunks(
            q,
            top_k=top_k,
            course_id=course_id,
            resource_type=resource_type,
            resource_id=resource_id,
        )
        formatted = format_api_results(hits, text_preview_chars=None)
        ResourceRetrievalLog.objects.create(
            query=q,
            top_k=top_k,
            results=formatted,
            searched_by=request.user if request.user.is_authenticated else None,
        )
        return Response({"query": q, "results": formatted})
