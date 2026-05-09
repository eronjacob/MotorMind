from django.contrib import admin

from .models import Course, TrainingVideo, VideoSection


class VideoSectionInline(admin.TabularInline):
    model = VideoSection
    extra = 0


class TrainingVideoInline(admin.StackedInline):
    model = TrainingVideo
    extra = 0
    show_change_link = True


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("title", "created_by", "created_at")
    search_fields = ("title",)
    inlines = [TrainingVideoInline]


@admin.register(TrainingVideo)
class TrainingVideoAdmin(admin.ModelAdmin):
    list_display = ("title", "course", "created_at")
    list_filter = ("course",)
    inlines = [VideoSectionInline]


@admin.register(VideoSection)
class VideoSectionAdmin(admin.ModelAdmin):
    list_display = ("title", "video", "start_seconds", "end_seconds", "order")
    list_filter = ("video__course",)
