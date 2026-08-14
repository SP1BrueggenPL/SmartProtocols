from django.contrib import admin
from .models import ServerAudit, AuditRequirement, AuditInspection, InspectionResult


class RequirementInline(admin.TabularInline):
    model = AuditRequirement
    extra = 1


class ResultInline(admin.TabularInline):
    model = InspectionResult
    extra = 0
    readonly_fields = ['requirement', 'is_met', 'comment']


@admin.register(ServerAudit)
class ServerAuditAdmin(admin.ModelAdmin):
    inlines = [RequirementInline]
    list_display = ['name', 'created_at']


@admin.register(AuditInspection)
class AuditInspectionAdmin(admin.ModelAdmin):
    inlines = [ResultInline]
    list_display = ['audit', 'user', 'created_at', 'completed_at', 'has_failures']
    readonly_fields = ['created_at', 'completed_at']
