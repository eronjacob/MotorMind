from django.contrib import admin

from .models import ARTask, ARTaskStep, StudentARTaskProgress


class ARTaskStepInline(admin.TabularInline):
    model = ARTaskStep
    extra = 0


@admin.register(ARTask)
class ARTaskAdmin(admin.ModelAdmin):
    list_display = ("title", "course", "target_object", "difficulty")
    list_filter = ("course", "target_object", "difficulty")
    inlines = [ARTaskStepInline]


@admin.register(ARTaskStep)
class ARTaskStepAdmin(admin.ModelAdmin):
    list_display = ("task", "order", "instruction")


@admin.register(StudentARTaskProgress)
class StudentARTaskProgressAdmin(admin.ModelAdmin):
    list_display = ("student", "task", "status", "updated_at")
    list_filter = ("status",)
