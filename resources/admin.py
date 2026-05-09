from django.contrib import admin

from .models import Resource, ResourceIngestionJob, ResourceRetrievalLog


class CourseListFilter(admin.SimpleListFilter):
    title = "Course"
    parameter_name = "course"

    def lookups(self, request, model_admin):
        from courses.models import Course

        return [(c.pk, c.title) for c in Course.objects.order_by("title")[:200]]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(courses__id=self.value()).distinct()
        return queryset


@admin.register(Resource)
class ResourceAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "isbn",
        "resource_type",
        "metadata_lookup_status",
        "status",
        "chunk_count",
        "uploaded_by",
        "created_at",
    )
    list_filter = ("status", "resource_type", CourseListFilter)
    search_fields = ("title", "author", "source_title", "original_filename")
    filter_horizontal = ("courses",)
    readonly_fields = ("created_at", "updated_at", "chunk_count")


@admin.register(ResourceIngestionJob)
class ResourceIngestionJobAdmin(admin.ModelAdmin):
    list_display = ("id", "resource", "status", "progress_percent", "created_at")
    list_filter = ("status",)


@admin.register(ResourceRetrievalLog)
class ResourceRetrievalLogAdmin(admin.ModelAdmin):
    list_display = ("id", "query", "top_k", "searched_by", "created_at")
    search_fields = ("query",)
