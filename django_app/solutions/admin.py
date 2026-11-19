from django.contrib import admin
from .models import Solution, SolutionLog


class SolutionLogInline(admin.TabularInline):
    model = SolutionLog
    extra = 0


@admin.register(Solution)
class SolutionAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'technology', 'status_label', 'progress_pct', 'created_at']
    list_filter  = ['category', 'technology']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'created_by']
    inlines = [SolutionLogInline]
